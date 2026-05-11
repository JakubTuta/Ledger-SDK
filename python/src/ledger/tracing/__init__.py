from ledger.tracing.span import Span, SpanEvent, SpanKind, SpanStatus
from ledger.tracing.tracer import Tracer, get_current_span

_tracer_holder: list[Tracer | None] = [None]


def _set_default_tracer(tracer: Tracer | None) -> None:
    _tracer_holder[0] = tracer


def get_tracer() -> Tracer | None:
    return _tracer_holder[0]


__all__ = [
    "Span",
    "SpanEvent",
    "SpanKind",
    "SpanStatus",
    "Tracer",
    "get_current_span",
    "get_tracer",
]
