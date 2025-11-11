import asyncio
import sys
from collections import deque
from typing import Any


class LogBuffer:
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue: deque[dict[str, Any]] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
        self._dropped_count = 0

    def add(self, log_entry: dict[str, Any]) -> None:
        if len(self._queue) >= self.max_size:
            self._queue.popleft()
            self._dropped_count += 1
            sys.stderr.write(
                f"[Ledger SDK] WARNING: Buffer full ({self.max_size} logs), "
                f"dropped oldest log (total dropped: {self._dropped_count})\n"
            )
            sys.stderr.flush()

        self._queue.append(log_entry)

    async def get_batch(self, max_batch_size: int) -> list[dict[str, Any]]:
        async with self._lock:
            batch_size = min(len(self._queue), max_batch_size)
            if batch_size == 0:
                return []

            batch = [self._queue.popleft() for _ in range(batch_size)]
            return batch

    def size(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def clear(self) -> None:
        self._queue.clear()

    def get_dropped_count(self) -> int:
        return self._dropped_count
