import ledger.tracing.propagation as propagation_module


def _make_span_stub(trace_id: str, span_id: str):
    class SpanStub:
        pass

    s = SpanStub()
    s.trace_id = trace_id
    s.span_id = span_id
    return s


def test_extract_valid_traceparent():
    headers = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
    ctx = propagation_module.extract(headers)
    assert ctx is not None
    assert ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert ctx.span_id == "00f067aa0ba902b7"
    assert ctx.sampled is True


def test_extract_unsampled():
    headers = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00"}
    ctx = propagation_module.extract(headers)
    assert ctx is not None
    assert ctx.sampled is False


def test_extract_missing_header():
    assert propagation_module.extract({}) is None


def test_extract_none_value():
    assert propagation_module.extract({"traceparent": None}) is None


def test_extract_wrong_version():
    headers = {"traceparent": "01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
    assert propagation_module.extract(headers) is None


def test_extract_all_zero_trace_id():
    headers = {"traceparent": f"00-{'0' * 32}-00f067aa0ba902b7-01"}
    assert propagation_module.extract(headers) is None


def test_extract_all_zero_span_id():
    headers = {"traceparent": f"00-4bf92f3577b34da6a3ce929d0e0e4736-{'0' * 16}-01"}
    assert propagation_module.extract(headers) is None


def test_extract_malformed():
    assert propagation_module.extract({"traceparent": "not-a-traceparent"}) is None


def test_inject():
    span = _make_span_stub("4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7")
    headers: dict[str, str] = {}
    propagation_module.inject(headers, span)
    assert "traceparent" in headers
    assert headers["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
