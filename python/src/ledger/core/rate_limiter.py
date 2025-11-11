import asyncio
import time
from collections import deque


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int,
        requests_per_hour: int = 50000,
        buffer: float = 0.9,
    ):
        self.limit_per_minute = int(requests_per_minute * buffer)
        self.limit_per_hour = int(requests_per_hour * buffer)
        self.buffer_ratio = buffer

        self.timestamps_minute: deque[float] = deque()
        self.timestamps_hour: deque[float] = deque()

    async def wait_if_needed(self) -> None:
        now = time.time()

        self._cleanup_timestamps(now)

        sleep_time = self._calculate_sleep_time(now)

        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
            now = time.time()
            self._cleanup_timestamps(now)

        self.timestamps_minute.append(now)
        self.timestamps_hour.append(now)

    def _cleanup_timestamps(self, now: float) -> None:
        minute_ago = now - 60
        while self.timestamps_minute and self.timestamps_minute[0] < minute_ago:
            self.timestamps_minute.popleft()

        hour_ago = now - 3600
        while self.timestamps_hour and self.timestamps_hour[0] < hour_ago:
            self.timestamps_hour.popleft()

    def _calculate_sleep_time(self, now: float) -> float:
        sleep_times = []

        if len(self.timestamps_minute) >= self.limit_per_minute:
            oldest_minute = self.timestamps_minute[0]
            sleep_until_minute = oldest_minute + 60
            sleep_times.append(sleep_until_minute - now)

        if len(self.timestamps_hour) >= self.limit_per_hour:
            oldest_hour = self.timestamps_hour[0]
            sleep_until_hour = oldest_hour + 3600
            sleep_times.append(sleep_until_hour - now)

        if sleep_times:
            return max(0, max(sleep_times))

        return 0

    def get_current_rate(self) -> int:
        now = time.time()
        self._cleanup_timestamps(now)
        return len(self.timestamps_minute)

    def get_current_hourly_rate(self) -> int:
        now = time.time()
        self._cleanup_timestamps(now)
        return len(self.timestamps_hour)

    def is_at_limit(self) -> bool:
        now = time.time()
        self._cleanup_timestamps(now)
        return (
            len(self.timestamps_minute) >= self.limit_per_minute
            or len(self.timestamps_hour) >= self.limit_per_hour
        )
