
import ledger.metrics.aggregator as aggregator_module


def _make_aggregator(max_tags=20):
    agg = aggregator_module.Aggregator(window_s=3600, max_tags_per_metric=max_tags)
    agg.stop()
    return agg


def test_counter_sums():
    agg = _make_aggregator()
    for _ in range(10):
        agg.counter("hits", 1.0)
    payloads = agg.flush()
    assert len(payloads) == 1
    assert payloads[0]["type"] == "counter"
    assert payloads[0]["sum"] == 10.0


def test_gauge_keeps_last():
    agg = _make_aggregator()
    agg.gauge("depth", 100.0)
    agg.gauge("depth", 200.0)
    agg.gauge("depth", 50.0)
    payloads = agg.flush()
    assert len(payloads) == 1
    assert payloads[0]["type"] == "gauge"
    assert payloads[0]["value"] == 50.0


def test_histogram_stats():
    agg = _make_aggregator()
    agg.histogram("latency", 1.0)
    agg.histogram("latency", 5.0)
    agg.histogram("latency", 50.0)
    agg.histogram("latency", 500.0)
    payloads = agg.flush()
    assert len(payloads) == 1
    p = payloads[0]
    assert p["type"] == "histogram"
    assert p["count"] == 4
    assert p["sum"] == 556.0
    assert p["min"] == 1.0
    assert p["max"] == 500.0
    assert len(p["buckets"]) > 0


def test_tags_separate_series():
    agg = _make_aggregator()
    agg.counter("req", 1.0, tags={"env": "prod"})
    agg.counter("req", 2.0, tags={"env": "staging"})
    payloads = agg.flush()
    assert len(payloads) == 2
    sums = {p["tags"]["env"]: p["sum"] for p in payloads}
    assert sums["prod"] == 1.0
    assert sums["staging"] == 2.0


def test_flush_clears_data():
    agg = _make_aggregator()
    agg.counter("c", 1.0)
    agg.flush()
    payloads = agg.flush()
    assert payloads == []


def test_cardinality_cap_drops_excess(caplog):
    import logging

    agg = _make_aggregator(max_tags=2)
    agg.counter("m", 1.0, tags={"k": "v1"})
    agg.counter("m", 1.0, tags={"k": "v2"})
    with caplog.at_level(logging.WARNING, logger="ledger"):
        agg.counter("m", 1.0, tags={"k": "v3"})
    payloads = agg.flush()
    assert len(payloads) == 2
    assert any("cardinality cap" in r.message for r in caplog.records)


def test_cardinality_warning_emitted_once(caplog):
    import logging

    agg = _make_aggregator(max_tags=1)
    agg.counter("m", 1.0, tags={"k": "v1"})
    with caplog.at_level(logging.WARNING, logger="ledger"):
        for i in range(5):
            agg.counter("m", 1.0, tags={"k": f"extra{i}"})
    warning_count = sum(1 for r in caplog.records if "cardinality cap" in r.message)
    assert warning_count == 1


def test_on_flush_callback_called():
    received = []

    def on_flush(payloads):
        received.extend(payloads)

    agg = aggregator_module.Aggregator(window_s=3600, on_flush=on_flush)
    agg.stop()
    agg.counter("x", 5.0)
    agg.flush()
    assert len(received) == 1
    assert received[0]["sum"] == 5.0


def test_histogram_bucket_counts():
    agg = _make_aggregator()
    agg.histogram("val", 1.0)
    agg.histogram("val", 5.0)
    agg.histogram("val", 50.0)
    agg.histogram("val", 500.0)
    payloads = agg.flush()
    buckets = {b["le"]: b["n"] for b in payloads[0]["buckets"]}
    assert buckets[1] == 1
    assert buckets[5] == 2
    assert buckets[50] == 3
    assert buckets[500] == 4
