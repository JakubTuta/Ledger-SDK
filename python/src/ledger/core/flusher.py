import asyncio
import sys
import time
from typing import Any

import httpx

import ledger.core.buffer as buffer_module
import ledger.core.http_client as http_client_module
import ledger.core.rate_limiter as rate_limiter_module


class BackgroundFlusher:
    def __init__(
        self,
        buffer: "buffer_module.LogBuffer",
        http_client: "http_client_module.HTTPClient",
        rate_limiter: "rate_limiter_module.RateLimiter",
        flush_interval: float = 5.0,
        max_batch_size: int = 1000,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
    ):
        self.buffer = buffer
        self.http_client = http_client
        self.rate_limiter = rate_limiter
        self.flush_interval = flush_interval
        self.max_batch_size = max_batch_size
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base

        self._task: asyncio.Task[Any] | None = None
        self._shutdown_event = asyncio.Event()

        self._metrics = {
            "total_flushes": 0,
            "successful_flushes": 0,
            "failed_flushes": 0,
            "total_logs_sent": 0,
            "total_logs_failed": 0,
            "consecutive_failures": 0,
            "last_flush_time": None,
            "last_error": None,
            "errors_by_type": {},
        }

        self._circuit_breaker_open = False
        self._circuit_breaker_opened_at = None
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60.0

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.flush_interval)

                if self.buffer.is_empty():
                    continue

                await self._flush_with_retry()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log_error(f"Unexpected error in flusher: {e}")

    async def _flush_with_retry(self) -> None:
        if self._circuit_breaker_open:
            if time.time() - self._circuit_breaker_opened_at < self._circuit_breaker_timeout:
                return

            self._log_info("Circuit breaker: attempting recovery")
            self._circuit_breaker_open = False

        batch = await self.buffer.get_batch(self.max_batch_size)
        if not batch:
            return

        self._metrics["total_flushes"] += 1

        for attempt in range(self.max_retries):
            try:
                await self.rate_limiter.wait_if_needed()

                success = await self._send_batch(batch)

                if success:
                    self._metrics["successful_flushes"] += 1
                    self._metrics["total_logs_sent"] += len(batch)
                    self._metrics["consecutive_failures"] = 0
                    self._metrics["last_flush_time"] = time.time()
                    return

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

        self._metrics["failed_flushes"] += 1
        self._metrics["total_logs_failed"] += len(batch)
        self._metrics["consecutive_failures"] += 1

        if self._metrics["consecutive_failures"] >= self._circuit_breaker_threshold:
            self._circuit_breaker_open = True
            self._circuit_breaker_opened_at = time.time()
            self._log_error(
                f"Circuit breaker OPEN: {self._metrics['consecutive_failures']} consecutive failures"
            )

    async def _send_batch(self, batch: list[dict[str, Any]]) -> bool:
        try:
            response = await self.http_client.post(
                "/api/v1/ingest/batch",
                json_data={"logs": batch},
            )

            if response.status_code == 202:
                data = response.json()
                accepted = data.get("accepted", 0)
                rejected = data.get("rejected", 0)

                if rejected > 0:
                    self._log_warning(f"Batch: {accepted} accepted, {rejected} rejected")
                    errors = data.get("errors", [])
                    for error in errors[:5]:
                        self._log_warning(f"  - {error}")

                return True

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self._log_warning(f"Rate limit exceeded, sleeping {retry_after}s")
                self._increment_error_count("rate_limit")
                await asyncio.sleep(retry_after)
                return False

            if response.status_code == 503:
                retry_after = int(response.headers.get("Retry-After", 60))
                self._log_warning(f"Queue full (503), sleeping {retry_after}s")
                self._increment_error_count("queue_full")
                await asyncio.sleep(retry_after)
                return False

            if response.status_code == 401:
                self._log_error("Invalid API key (401), stopping ingestion")
                self._increment_error_count("auth_failure")
                self._shutdown_event.set()
                return False

            if response.status_code == 400:
                self._log_error(f"Bad request (400): {response.text}")
                self._increment_error_count("validation_error")
                return True

            self._log_error(f"Unexpected response: {response.status_code} - {response.text}")
            self._increment_error_count("server_error")
            return False

        except Exception:
            raise

    def _handle_network_error(self, error_type: str, error: Exception, attempt: int) -> None:
        self._log_error(f"{error_type} (attempt {attempt + 1}/{self.max_retries}): {error}")
        self._increment_error_count("network_error")
        self._metrics["last_error"] = f"{error_type}: {error}"

    def _increment_error_count(self, error_type: str) -> None:
        if error_type not in self._metrics["errors_by_type"]:
            self._metrics["errors_by_type"][error_type] = 0
        self._metrics["errors_by_type"][error_type] += 1

    def _log_info(self, message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        sys.stderr.write(f"[{timestamp}] [Ledger SDK] [INFO] {message}\n")
        sys.stderr.flush()

    def _log_warning(self, message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        sys.stderr.write(f"[{timestamp}] [Ledger SDK] [WARNING] {message}\n")
        sys.stderr.flush()

    def _log_error(self, message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        sys.stderr.write(f"[{timestamp}] [Ledger SDK] [ERROR] {message}\n")
        sys.stderr.flush()

    async def shutdown(self, timeout: float = 10.0) -> None:
        self._log_info("Shutting down, flushing remaining logs...")
        self._shutdown_event.set()

        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        remaining_attempts = 3
        while not self.buffer.is_empty() and remaining_attempts > 0:
            try:
                await asyncio.wait_for(self._flush_with_retry(), timeout=timeout / 3)
                remaining_attempts -= 1
            except asyncio.TimeoutError:
                self._log_warning("Flush timeout during shutdown")
                break
            except Exception as e:
                self._log_error(f"Shutdown flush error: {e}")
                break

        if not self.buffer.is_empty():
            dropped = self.buffer.size()
            self._log_warning(f"Shutdown: {dropped} logs still in buffer (not sent)")

        self._log_info("Shutdown complete")

    def get_metrics(self) -> dict[str, Any]:
        return {
            "total_flushes": self._metrics["total_flushes"],
            "successful_flushes": self._metrics["successful_flushes"],
            "failed_flushes": self._metrics["failed_flushes"],
            "total_logs_sent": self._metrics["total_logs_sent"],
            "total_logs_failed": self._metrics["total_logs_failed"],
            "consecutive_failures": self._metrics["consecutive_failures"],
            "circuit_breaker_open": self._circuit_breaker_open,
            "last_flush_time": self._metrics["last_flush_time"],
            "last_error": self._metrics["last_error"],
            "errors_by_type": self._metrics["errors_by_type"],
        }
