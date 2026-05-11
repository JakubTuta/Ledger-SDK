from unittest.mock import MagicMock

import ledger.tracing.buffer as trace_buffer_module
import ledger.tracing.sampler as sampler_module
import ledger.tracing.span as span_module
import ledger.tracing.tracer as tracer_module


def _make_tracer(rate=1.0, on_span_end=None):
    if on_span_end is None:
        on_span_end = MagicMock()
    sampler = sampler_module.ErrorBiasedHeadSampler(rate=rate)
    decision_buffer = trace_buffer_module.TraceDecisionBuffer(window_ms=2000)
    return (
        tracer_module.Tracer(
            service_name="test-svc",
            sampler=sampler,
            on_span_end=on_span_end,
            decision_buffer=decision_buffer,
        ),
        on_span_end,
    )


def test_start_span_creates_span():
    tracer, _ = _make_tracer()
    span = tracer.start_span("my-op")
    assert span.name == "my-op"
    assert span.service_name == "test-svc"
    assert span.parent_span_id is None
    assert span.end_ns is None


def test_start_span_with_parent():
    tracer, _ = _make_tracer()
    parent = tracer.start_span("parent")
    child = tracer.start_span("child", parent=parent)
    assert child.trace_id == parent.trace_id
    assert child.parent_span_id == parent.span_id


def test_start_as_current_span_calls_on_span_end():
    tracer, on_end = _make_tracer(rate=1.0)
    with tracer.start_as_current_span("op") as span:
        assert span.name == "op"
    on_end.assert_called_once_with(span)


def test_start_as_current_span_sets_current():
    tracer, _ = _make_tracer()
    assert tracer.get_current_span() is None
    with tracer.start_as_current_span("op") as span:
        assert tracer.get_current_span() is span
    assert tracer.get_current_span() is None


def test_nested_spans_set_parent():
    tracer, _ = _make_tracer()
    with (
        tracer.start_as_current_span("outer") as outer,
        tracer.start_as_current_span("inner") as inner,
    ):
        assert inner.parent_span_id == outer.span_id
        assert inner.trace_id == outer.trace_id


def test_record_only_held_in_buffer():
    tracer, on_end = _make_tracer(rate=0.0)
    with tracer.start_as_current_span("op"):
        pass
    on_end.assert_not_called()


def test_error_upgrades_record_only_trace():
    tracer, on_end = _make_tracer(rate=0.0)
    with tracer.start_as_current_span("op") as span:
        span.set_status(span_module.SpanStatus.ERROR)
    on_end.assert_called_once()


def test_exception_event_upgrades_trace():
    tracer, on_end = _make_tracer(rate=0.0)
    with tracer.start_as_current_span("op") as span:
        try:
            raise ValueError("boom")
        except ValueError as exc:
            span.record_exception(exc)
    on_end.assert_called_once()


def test_activate_deactivate_span():
    tracer, on_end = _make_tracer(rate=1.0)
    span = tracer.start_span("manual")
    token = tracer.activate_span(span)
    assert tracer.get_current_span() is span
    tracer.deactivate_span(span, token)
    assert tracer.get_current_span() is None
    on_end.assert_called_once_with(span)
