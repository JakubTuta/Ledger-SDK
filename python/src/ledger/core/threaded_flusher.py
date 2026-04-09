import asyncio
import threading
from collections.abc import Callable
from typing import Any

import ledger._logging as logging_module
import ledger.core.buffer as buffer_module
import ledger.core.flusher as flusher_module
import ledger.core.rate_limiter as rate_limiter_module


class ThreadedFlusher:
    """Runs a BackgroundFlusher inside a dedicated thread with its own asyncio loop.
    Used when the host application is synchronous (Flask, Django WSGI)."""

    def __init__(
        self,
        buffer: "buffer_module.LogBuffer",
        http_client_factory: Callable[[], Any],
        rate_limiter: "rate_limiter_module.RateLimiter",
        flush_interval: float,
        flush_size: int,
        max_batch_size: int,
    ) -> None:
        self._buffer = buffer
        self._rate_limiter = rate_limiter
        self._http_client_factory = http_client_factory
        self._flush_interval = flush_interval
        self._flush_size = flush_size
        self._max_batch_size = max_batch_size

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._inner: flusher_module.BackgroundFlusher | None = None
        self._http_client: Any | None = None
        self._ready = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._thread_main, name="ledger-flusher", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def _thread_main(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._http_client = self._http_client_factory()
            self._inner = flusher_module.BackgroundFlusher(
                buffer=self._buffer,
                http_client=self._http_client,
                rate_limiter=self._rate_limiter,
                flush_interval=self._flush_interval,
                flush_size=self._flush_size,
                max_batch_size=self._max_batch_size,
            )
            self._inner.start()
            self._ready.set()
            self._loop.run_forever()
        except Exception as e:
            logging_module.get_logger().error("Threaded flusher crashed: %s", e)
            self._ready.set()

    def ensure_started(self) -> None:
        self.start()

    def notify(self) -> None:
        if self._loop and self._inner:
            self._loop.call_soon_threadsafe(self._inner.notify)

    def get_metrics(self) -> dict[str, Any]:
        if self._inner:
            return self._inner.get_metrics()
        return {
            "total_flushes": 0,
            "successful_flushes": 0,
            "failed_flushes": 0,
            "total_logs_sent": 0,
            "total_logs_failed": 0,
            "total_logs_rejected": 0,
            "consecutive_failures": 0,
            "circuit_breaker_open": False,
            "last_flush_time": None,
            "last_error": None,
            "errors_by_type": {},
        }

    def shutdown(self, timeout: float = 10.0) -> None:
        if not self._loop or not self._inner:
            return
        future = asyncio.run_coroutine_threadsafe(
            self._inner.shutdown(timeout=timeout), self._loop
        )
        try:
            future.result(timeout=timeout + 2.0)
        except Exception as e:
            logging_module.get_logger().error("Error during threaded shutdown: %s", e)
        finally:
            if self._http_client is not None:
                close_future = asyncio.run_coroutine_threadsafe(
                    self._http_client.close(), self._loop
                )
                try:
                    close_future.result(timeout=2.0)
                except Exception as close_err:
                    logging_module.get_logger().debug("HTTP client close error: %s", close_err)
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=2.0)
