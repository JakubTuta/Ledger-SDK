import threading
import time
from collections.abc import Callable
from typing import Any

import ledger._logging as logging_module


class CounterAggValue:
    def __init__(self) -> None:
        self.sum: float = 0.0


class GaugeAggValue:
    def __init__(self) -> None:
        self.value: float = 0.0


class HistogramAggValue:
    BUCKETS: list[float] = [
        1,
        2,
        5,
        10,
        25,
        50,
        100,
        250,
        500,
        1000,
        2500,
        5000,
        10000,
        float("inf"),
    ]

    def __init__(self) -> None:
        self.count: int = 0
        self.sum: float = 0.0
        self.min: float = float("inf")
        self.max: float = float("-inf")
        self.bucket_counts: list[int] = [0] * len(self.BUCKETS)

    def observe(self, value: float) -> None:
        self.count += 1
        self.sum += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        for i, bound in enumerate(self.BUCKETS):
            if value <= bound:
                self.bucket_counts[i] += 1


class Aggregator:
    def __init__(
        self,
        window_s: float = 10.0,
        on_flush: Callable[[list[dict[str, Any]]], None] | None = None,
        max_tags_per_metric: int = 20,
    ) -> None:
        self._window_s = window_s
        self._on_flush = on_flush
        self._max_tags = max_tags_per_metric
        self._counters: dict[tuple[str, frozenset], CounterAggValue] = {}
        self._gauges: dict[tuple[str, frozenset], GaugeAggValue] = {}
        self._histograms: dict[tuple[str, frozenset], HistogramAggValue] = {}
        self._tag_counts: dict[str, set[frozenset]] = {}
        self._warned_metrics: set[str] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._start_timer()

    def _start_timer(self) -> None:
        self._timer = threading.Timer(self._window_s, self._flush_and_restart)
        self._timer.daemon = True
        self._timer.start()

    def _flush_and_restart(self) -> None:
        self.flush()
        self._start_timer()

    def counter(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        frozen_tags = frozenset((tags or {}).items())
        if not self._check_cardinality(name, frozen_tags):
            return
        key = (name, frozen_tags)
        with self._lock:
            if key not in self._counters:
                self._counters[key] = CounterAggValue()
            self._counters[key].sum += value

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        frozen_tags = frozenset((tags or {}).items())
        if not self._check_cardinality(name, frozen_tags):
            return
        key = (name, frozen_tags)
        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = GaugeAggValue()
            self._gauges[key].value = value

    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        frozen_tags = frozenset((tags or {}).items())
        if not self._check_cardinality(name, frozen_tags):
            return
        key = (name, frozen_tags)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = HistogramAggValue()
            self._histograms[key].observe(value)

    def _check_cardinality(self, name: str, frozen_tags: frozenset) -> bool:
        should_warn = False
        over_cap = False

        with self._lock:
            if name not in self._tag_counts:
                self._tag_counts[name] = set()

            existing = self._tag_counts[name]
            if frozen_tags not in existing:
                if len(existing) >= self._max_tags:
                    if name not in self._warned_metrics:
                        self._warned_metrics.add(name)
                        should_warn = True
                    over_cap = True
                else:
                    existing.add(frozen_tags)

        if should_warn:
            logging_module.get_logger().warning(
                "Ledger: metric '%s' exceeded cardinality cap; extra tag combinations dropped.",
                name,
            )

        return not over_cap

    def flush(self) -> list[dict[str, Any]]:
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            histograms = dict(self._histograms)
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._tag_counts.clear()

        now = int(time.time())
        payloads: list[dict[str, Any]] = []

        for (name, frozen_tags), agg in counters.items():
            payloads.append(
                {
                    "name": name,
                    "tags": dict(frozen_tags),
                    "ts": now,
                    "type": "counter",
                    "sum": agg.sum,
                }
            )

        for (name, frozen_tags), agg in gauges.items():
            payloads.append(
                {
                    "name": name,
                    "tags": dict(frozen_tags),
                    "ts": now,
                    "type": "gauge",
                    "value": agg.value,
                }
            )

        for (name, frozen_tags), agg in histograms.items():
            if agg.count > 0:
                payloads.append(
                    {
                        "name": name,
                        "tags": dict(frozen_tags),
                        "ts": now,
                        "type": "histogram",
                        "count": agg.count,
                        "sum": agg.sum,
                        "min": agg.min,
                        "max": agg.max,
                        "buckets": [
                            {
                                "le": b if b != float("inf") else "+Inf",
                                "n": n,
                            }
                            for b, n in zip(
                                HistogramAggValue.BUCKETS, agg.bucket_counts, strict=False
                            )
                        ],
                    }
                )

        if payloads and self._on_flush is not None:
            self._on_flush(payloads)

        return payloads

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
