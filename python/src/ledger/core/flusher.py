import asyncio
import enum
import time
from typing import Any

import httpx

import ledger._logging as logging_module
import ledger.core.buffer as buffer_module
import ledger.core.http_client as http_client_module
import ledger.core.rate_limiter as rate_limiter_module


class SendResult(enum.Enum):
    OK = "ok"
    DROPPED = "dropped"
    RETRY_EXHAUSTED = "retry_exhausted"


class BackgroundFlusher:
    def __init__(
        self,
        buffer: "buffer_module.LogBuffer",
        http_client: "http_client_module.HTTPClient",
        rate_limiter: "rate_limiter_module.RateLimiter",
        flush_interval: float = 5.0,
        flush_size: int = 100,
        max_batch_size: int = 1000,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
    ):
        self.buffer = buffer
        self.http_client = http_client
        self.rate_limiter = rate_limiter
        self.flush_interval = flush_interval
        self.flush_size = flush_size
        self.max_batch_size = max_batch_size
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base

        self._task: asyncio.Task[Any] | None = None
        self._shutdown_event = asyncio.Event()
        self._wakeup_event = asyncio.Event()

        self._metrics: dict[str, Any] = {
            "total_flushes": 0,
            "successful_flushes": 0,
            "failed_flushes": 0,
            "total_logs_sent": 0,
            "total_logs_failed": 0,
            "total_logs_rejected": 0,
            "consecutive_failures": 0,
            "last_flush_time": None,
            "last_error": None,
            "errors_by_type": {},
        }

        self._circuit_breaker_open = False
        self._circuit_breaker_opened_at: float = 0.0
        self._circuit_breaker_half_open = False
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60.0

    def start(self) -> None:
        if self._task is None or self._task.done():
            try:
                asyncio.get_running_loop()
                self._task = asyncio.create_task(self._run())
            except RuntimeError:
                self._task = None

    def ensure_started(self) -> None:
        if self._task is None or self._task.done():
            self.start()

    def notify(self) -> None:
        self._wakeup_event.set()

    async def _run(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                try:
                    await asyncio.wait_for(
                        self._wakeup_event.wait(),
                        timeout=self.flush_interval,
                    )
                except asyncio.TimeoutError:
                    pass
                self._wakeup_event.clear()

                while not self.buffer.is_empty() and not self._shutdown_event.is_set():
                    if self._circuit_breaker_open and not self._circuit_breaker_try_recover():
                        break
                    if not await self._flush_once():
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging_module.get_logger().error("Unexpected error in flusher: %s", e)
                await asyncio.sleep(1.0)

    async def _flush_once(self) -> bool:
        batch = self.buffer.get_batch(self.max_batch_size)
        if not batch:
            return False

        self._metrics["total_flushes"] += 1
        result = await self._send_with_retries(batch)

        if result is SendResult.OK:
            self._metrics["successful_flushes"] += 1
            self._metrics["consecutive_failures"] = 0
            self._metrics["last_flush_time"] = time.time()
            if self._circuit_breaker_half_open:
                self._close_circuit_breaker()
            return True

        if result is SendResult.DROPPED:
            self._metrics["total_logs_rejected"] += len(batch)
            return True

        self.buffer.requeue(batch)
        self._metrics["failed_flushes"] += 1
        self._metrics["total_logs_failed"] += len(batch)
        self._metrics["consecutive_failures"] += 1
        if self._metrics["consecutive_failures"] >= self._circuit_breaker_threshold:
            self._open_circuit_breaker()
        return False

    async def _send_with_retries(self, batch: list[dict[str, Any]]) -> SendResult:
        for attempt in range(self.max_retries):
            try:
                await self.rate_limiter.wait_if_needed()
                result = await self._send_batch(batch)

                if result in (SendResult.OK, SendResult.DROPPED):
                    return result

                if attempt < self.max_retries - 1:
                    backoff = self.retry_backoff_base**attempt
                    await asyncio.sleep(backoff)

            except httpx.TimeoutException as e:
                self._handle_network_error("Timeout", e, attempt)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_backoff_base**attempt * 5.0)

            except httpx.ConnectError as e:
                self._handle_network_error("Connection refused", e, attempt)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_backoff_base**attempt * 5.0)

            except Exception as e:
                self._handle_network_error("Unexpected error", e, attempt)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_backoff_base**attempt)

        return SendResult.RETRY_EXHAUSTED

    async def _send_batch(self, batch: list[dict[str, Any]]) -> SendResult:
        try:
            response = await self.http_client.post(
                "/api/v1/ingest/batch",
                json_data={"logs": batch},
            )

            status = response.status_code

            if status == 202:
                data = response.json()
                accepted = int(data.get("accepted", len(batch)))
                rejected = int(data.get("rejected", 0))
                self._metrics["total_logs_sent"] += accepted
                if rejected > 0:
                    self._metrics["total_logs_rejected"] += rejected
                    for err in data.get("errors", [])[:5]:
                        logging_module.get_logger().warning("Rejected log: %s", err)
                return SendResult.OK

            if status in (429, 503):
                retry_after = int(response.headers.get("Retry-After", 60))
                kind = "rate_limit" if status == 429 else "queue_full"
                logging_module.get_logger().warning(
                    "%s (%d), sleeping %ds", kind, status, retry_after
                )
                self._increment_error_count(kind)
                await asyncio.sleep(retry_after)
                return SendResult.RETRY_EXHAUSTED

            if status == 401:
                logging_module.get_logger().error("Invalid API key (401), stopping ingestion")
                self._increment_error_count("auth_failure")
                self._shutdown_event.set()
                return SendResult.DROPPED

            if status == 400:
                logging_module.get_logger().error("Bad request (400): %s", response.text[:500])
                self._increment_error_count("validation_error")
                return SendResult.DROPPED

            logging_module.get_logger().error(
                "Unexpected response: %d - %s", status, response.text[:500]
            )
            self._increment_error_count("server_error")
            return SendResult.RETRY_EXHAUSTED

        except Exception:
            raise

    def _handle_network_error(self, error_type: str, error: Exception, attempt: int) -> None:
        logging_module.get_logger().error(
            "%s (attempt %d/%d): %s", error_type, attempt + 1, self.max_retries, error
        )
        self._increment_error_count("network_error")
        self._metrics["last_error"] = f"{error_type}: {error}"

    def _increment_error_count(self, error_type: str) -> None:
        if error_type not in self._metrics["errors_by_type"]:
            self._metrics["errors_by_type"][error_type] = 0
        self._metrics["errors_by_type"][error_type] += 1

    def _open_circuit_breaker(self) -> None:
        self._circuit_breaker_open = True
        self._circuit_breaker_half_open = False
        self._circuit_breaker_opened_at = time.time()
        logging_module.get_logger().error(
            "Circuit breaker OPEN: %d consecutive failures",
            self._metrics["consecutive_failures"],
        )

    def _close_circuit_breaker(self) -> None:
        self._circuit_breaker_open = False
        self._circuit_breaker_half_open = False
        self._metrics["consecutive_failures"] = 0
        logging_module.get_logger().info("Circuit breaker CLOSED: recovery successful")

    def _circuit_breaker_try_recover(self) -> bool:
        if time.time() - self._circuit_breaker_opened_at < self._circuit_breaker_timeout:
            return False
        if not self._circuit_breaker_half_open:
            logging_module.get_logger().info("Circuit breaker: half-open, trying probe")
            self._circuit_breaker_half_open = True
        return True

    async def shutdown(self, timeout: float = 10.0) -> None:
        logging_module.get_logger().info("Shutting down, flushing remaining logs...")
        deadline = time.monotonic() + timeout
        self._shutdown_event.set()
        self._wakeup_event.set()

        if self._task and not self._task.done():
            remaining = max(0.0, deadline - time.monotonic())
            try:
                await asyncio.wait_for(self._task, timeout=min(remaining, 2.0))
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        self._circuit_breaker_open = False
        self._circuit_breaker_half_open = False

        while not self.buffer.is_empty():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            batch = self.buffer.get_batch(self.max_batch_size)
            if not batch:
                break
            try:
                await asyncio.wait_for(self._send_with_retries(batch), timeout=remaining)
            except asyncio.TimeoutError:
                logging_module.get_logger().warning("Flush timeout during shutdown")
                self.buffer.requeue(batch)
                break
            except Exception as e:
                logging_module.get_logger().error("Shutdown flush error: %s", e)
                self.buffer.requeue(batch)
                break

        if not self.buffer.is_empty():
            logging_module.get_logger().warning(
                "Shutdown: %d logs still in buffer (not sent)", self.buffer.size()
            )

        logging_module.get_logger().info("Shutdown complete")

    def get_metrics(self) -> dict[str, Any]:
        return {
            "total_flushes": self._metrics["total_flushes"],
            "successful_flushes": self._metrics["successful_flushes"],
            "failed_flushes": self._metrics["failed_flushes"],
            "total_logs_sent": self._metrics["total_logs_sent"],
            "total_logs_failed": self._metrics["total_logs_failed"],
            "total_logs_rejected": self._metrics["total_logs_rejected"],
            "consecutive_failures": self._metrics["consecutive_failures"],
            "circuit_breaker_open": self._circuit_breaker_open,
            "last_flush_time": self._metrics["last_flush_time"],
            "last_error": self._metrics["last_error"],
            "errors_by_type": self._metrics["errors_by_type"],
        }
