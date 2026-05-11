import dataclasses
from typing import Any


@dataclasses.dataclass
class SpanContext:
    trace_id: str
    span_id: str
    sampled: bool


def extract(headers: Any) -> SpanContext | None:
    traceparent: str | None = None
    if hasattr(headers, "get"):
        traceparent = headers.get("traceparent")

    if not traceparent:
        return None

    parts = traceparent.split("-")
    if len(parts) != 4:
        return None

    version, trace_id, span_id, flags = parts

    if version != "00":
        return None
    if len(trace_id) != 32 or trace_id == "0" * 32:
        return None
    if len(span_id) != 16 or span_id == "0" * 16:
        return None

    return SpanContext(trace_id=trace_id, span_id=span_id, sampled=flags == "01")


def inject(headers: dict[str, str], span: Any) -> None:
    headers["traceparent"] = f"00-{span.trace_id}-{span.span_id}-01"
