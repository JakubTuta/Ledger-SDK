import threading
import time

import ledger.tracing.span as span_module


class TraceDecisionBuffer:
    def __init__(self, window_ms: float = 2000.0) -> None:
        self._window_ms = window_ms
        self._traces: dict[str, list[span_module.Span]] = {}
        self._trace_timestamps: dict[str, float] = {}
        self._lock = threading.Lock()

    def hold(self, span: span_module.Span) -> None:
        with self._lock:
            if span.trace_id not in self._traces:
                self._traces[span.trace_id] = []
                self._trace_timestamps[span.trace_id] = time.monotonic()
            self._traces[span.trace_id].append(span)

    def upgrade_and_flush(self, trace_id: str) -> list[span_module.Span]:
        with self._lock:
            spans = self._traces.pop(trace_id, [])
            self._trace_timestamps.pop(trace_id, None)
            return spans

    def has_trace(self, trace_id: str) -> bool:
        with self._lock:
            return trace_id in self._traces

    def add_to_existing(self, span: span_module.Span) -> None:
        with self._lock:
            if span.trace_id in self._traces:
                self._traces[span.trace_id].append(span)

    def expire_old_traces(self) -> None:
        cutoff = time.monotonic() - (self._window_ms / 1000.0)
        with self._lock:
            expired = [tid for tid, ts in self._trace_timestamps.items() if ts < cutoff]
            for tid in expired:
                self._traces.pop(tid, None)
                self._trace_timestamps.pop(tid, None)
