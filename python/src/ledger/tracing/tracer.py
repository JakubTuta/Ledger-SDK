import contextlib
import time
from collections.abc import Callable, Generator
from contextvars import ContextVar, Token
from typing import Any

import ledger.tracing.buffer as trace_buffer_module
import ledger.tracing.ids as ids_module
import ledger.tracing.propagation as propagation_module
import ledger.tracing.sampler as sampler_module
import ledger.tracing.span as span_module

_current_span: ContextVar[span_module.Span | None] = ContextVar("_current_span", default=None)


class Tracer:
    def __init__(
        self,
        service_name: str,
        sampler: sampler_module.ErrorBiasedHeadSampler,
        on_span_end: Callable[[span_module.Span], None],
        decision_buffer: trace_buffer_module.TraceDecisionBuffer,
    ) -> None:
        self._service_name = service_name
        self._sampler = sampler
        self._on_span_end = on_span_end
        self._decision_buffer = decision_buffer

    def start_span(
        self,
        name: str,
        kind: span_module.SpanKind = span_module.SpanKind.INTERNAL,
        parent: span_module.Span | propagation_module.SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> span_module.Span:
        current = _current_span.get()
        resolved_parent: span_module.Span | propagation_module.SpanContext | None = (
            parent if parent is not None else current
        )

        if isinstance(resolved_parent, span_module.Span):
            trace_id = resolved_parent.trace_id
            parent_span_id: str | None = resolved_parent.span_id
        elif isinstance(resolved_parent, propagation_module.SpanContext):
            trace_id = resolved_parent.trace_id
            parent_span_id = resolved_parent.span_id
        else:
            trace_id = ids_module.generate_trace_id()
            parent_span_id = None

        return span_module.Span(
            trace_id=trace_id,
            span_id=ids_module.generate_span_id(),
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_ns=time.time_ns(),
            end_ns=None,
            status=span_module.SpanStatus.UNSET,
            status_message=None,
            attributes=dict(attributes) if attributes else {},
            events=[],
            service_name=self._service_name,
        )

    @contextlib.contextmanager
    def start_as_current_span(
        self,
        name: str,
        kind: span_module.SpanKind = span_module.SpanKind.INTERNAL,
        parent: span_module.Span | propagation_module.SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[span_module.Span, None, None]:
        span = self.start_span(name, kind=kind, parent=parent, attributes=attributes)
        token = _current_span.set(span)
        try:
            yield span
        finally:
            span.end()
            _current_span.reset(token)
            self._finish_span(span)

    def activate_span(self, span: span_module.Span) -> Token[span_module.Span | None]:
        return _current_span.set(span)

    def deactivate_span(
        self,
        span: span_module.Span,
        token: Token[span_module.Span | None],
    ) -> None:
        span.end()
        _current_span.reset(token)
        self._finish_span(span)

    def get_current_span(self) -> span_module.Span | None:
        return _current_span.get()

    def _finish_span(self, span: span_module.Span) -> None:
        decision = self._sampler.should_sample(span.trace_id)
        has_error = span.status == span_module.SpanStatus.ERROR or any(
            e.name == "exception" for e in span.events
        )

        if decision == sampler_module.SamplingDecision.RECORD_AND_SEND:
            held_spans = self._decision_buffer.upgrade_and_flush(span.trace_id)
            for held in held_spans:
                self._on_span_end(held)
            self._on_span_end(span)
        elif has_error:
            held_spans = self._decision_buffer.upgrade_and_flush(span.trace_id)
            for held in held_spans:
                self._on_span_end(held)
            self._on_span_end(span)
        elif self._decision_buffer.has_trace(span.trace_id):
            self._decision_buffer.add_to_existing(span)
        else:
            self._decision_buffer.hold(span)


def get_current_span() -> span_module.Span | None:
    return _current_span.get()
