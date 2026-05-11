import ledger.tracing.ids as ids_module


def test_generate_trace_id_is_32_hex_chars():
    tid = ids_module.generate_trace_id()
    assert len(tid) == 32
    assert all(c in "0123456789abcdef" for c in tid)


def test_generate_span_id_is_16_hex_chars():
    sid = ids_module.generate_span_id()
    assert len(sid) == 16
    assert all(c in "0123456789abcdef" for c in sid)


def test_trace_ids_are_unique():
    ids = {ids_module.generate_trace_id() for _ in range(100)}
    assert len(ids) == 100


def test_span_ids_are_unique():
    ids = {ids_module.generate_span_id() for _ in range(100)}
    assert len(ids) == 100
