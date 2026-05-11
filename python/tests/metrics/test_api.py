from unittest.mock import MagicMock

import ledger.metrics.api as api_module
import ledger.metrics.aggregator as aggregator_module


def _make_api():
    agg = MagicMock(spec=aggregator_module.Aggregator)
    return api_module.MetricsAPI(aggregator=agg), agg


def test_counter_delegates():
    api, agg = _make_api()
    api.counter("hits", 5.0, tags={"env": "prod"})
    agg.counter.assert_called_once_with("hits", 5.0, {"env": "prod"})


def test_gauge_delegates():
    api, agg = _make_api()
    api.gauge("depth", 42.0)
    agg.gauge.assert_called_once_with("depth", 42.0, None)


def test_histogram_delegates():
    api, agg = _make_api()
    api.histogram("latency", 12.5)
    agg.histogram.assert_called_once_with("latency", 12.5, None)


def test_module_level_functions_no_op_without_default():
    import ledger.metrics as metrics_module

    original = metrics_module._metrics_holder[0]
    metrics_module._metrics_holder[0] = None
    try:
        metrics_module.counter("x", 1.0)
        metrics_module.gauge("x", 1.0)
        metrics_module.histogram("x", 1.0)
    finally:
        metrics_module._metrics_holder[0] = original
