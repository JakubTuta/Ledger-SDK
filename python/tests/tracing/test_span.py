import time

import ledger.tracing.span as span_module


def _make_span(**kwargs):
    defaults = {
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "parent_span_id": None,
        "name": "test",
        "kind": span_module.SpanKind.INTERNAL,
        "start_ns": time.time_ns(),
        "end_ns": None,
        "status": span_module.SpanStatus.UNSET,
        "status_message": None,
        "attributes": {},
        "events": [],
        "service_name": "svc",
    }
    defaults.update(kwargs)
    return span_module.Span(**defaults)


def test_set_attr():
    span = _make_span()
    span.set_attr("key", "value")
    assert span.attributes["key"] == "value"


def test_set_status():
    span = _make_span()
    span.set_status(span_module.SpanStatus.ERROR, "something failed")
    assert span.status == span_module.SpanStatus.ERROR
    assert span.status_message == "something failed"


def test_end_sets_end_ns():
    span = _make_span()
    assert span.end_ns is None
    span.end()
    assert span.end_ns is not None
    assert span.end_ns >= span.start_ns


def test_end_is_idempotent():
    span = _make_span()
    span.end()
    first_end_ns = span.end_ns
    span.end()
    assert span.end_ns == first_end_ns


def test_record_exception():
    span = _make_span()
    exc = ValueError("test error")
    span.record_exception(exc)
    assert len(span.events) == 1
    event = span.events[0]
    assert event.name == "exception"
    assert event.attributes["exception.type"] == "ValueError"
    assert event.attributes["exception.message"] == "test error"
    assert "exception.stacktrace" in event.attributes


def test_to_dict():
    span = _make_span()
    span.set_attr("http.method", "GET")
    span.end()
    d = span.to_dict()
    assert d["trace_id"] == "a" * 32
    assert d["span_id"] == "b" * 16
    assert d["kind"] == "internal"
    assert d["status"] == "unset"
    assert d["attributes"]["http.method"] == "GET"
    assert d["end_ns"] is not None
