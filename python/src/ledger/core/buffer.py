import threading
import time
from collections import deque
from typing import Any

import ledger._logging as logging_module


class LogBuffer:
    _WARN_INTERVAL_SECONDS = 5.0

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue: deque[dict[str, Any]] = deque()
        self._lock = threading.Lock()
        self._dropped_count = 0
        self._last_warn_time = 0.0

    def add(self, log_entry: dict[str, Any]) -> None:
        with self._lock:
            if len(self._queue) >= self.max_size:
                self._queue.popleft()
                self._dropped_count += 1
                self._maybe_warn_dropped()
            self._queue.append(log_entry)

    def get_batch(self, max_batch_size: int) -> list[dict[str, Any]]:
        with self._lock:
            n = min(len(self._queue), max_batch_size)
            return [self._queue.popleft() for _ in range(n)]

    def requeue(self, batch: list[dict[str, Any]]) -> int:
        with self._lock:
            space = self.max_size - len(self._queue)
            fit = batch[:space] if space < len(batch) else batch
            self._queue.extendleft(reversed(fit))
            dropped = len(batch) - len(fit)
            if dropped > 0:
                self._dropped_count += dropped
                self._maybe_warn_dropped()
            return len(fit)

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        return self.size() == 0

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def get_dropped_count(self) -> int:
        return self._dropped_count

    def _maybe_warn_dropped(self) -> None:
        now = time.monotonic()
        if now - self._last_warn_time >= self._WARN_INTERVAL_SECONDS:
            self._last_warn_time = now
            logging_module.get_logger().warning(
                "Buffer full (%d), dropped oldest log (total dropped: %d)",
                self.max_size,
                self._dropped_count,
            )
