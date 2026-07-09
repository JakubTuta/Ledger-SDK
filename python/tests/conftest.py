import opentelemetry._logs._internal as logs_internal
import opentelemetry.trace as trace_api
import pytest
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import ledger.core.client as client_module


def _reset_otel_globals() -> None:
    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE._done = False
    logs_internal._LOGGER_PROVIDER = None
    logs_internal._LOGGER_PROVIDER_SET_ONCE._done = False


@pytest.fixture(autouse=True)
def reset_otel_globals():
    _reset_otel_globals()
    yield
    _reset_otel_globals()


@pytest.fixture
def api_key():
    return "ledger_proj_1_test_key_12345"


@pytest.fixture
def base_url():
    return "http://localhost:8000"


@pytest.fixture
def span_exporter():
    return InMemorySpanExporter()


@pytest.fixture
def log_exporter():
    return InMemoryLogRecordExporter()


@pytest.fixture
def make_client(monkeypatch, api_key, base_url, span_exporter, log_exporter):
    def _make(**overrides):
        monkeypatch.setattr(client_module, "OTLPSpanExporter", lambda **_kwargs: span_exporter)
        monkeypatch.setattr(client_module, "OTLPLogExporter", lambda **_kwargs: log_exporter)
        kwargs = {"api_key": api_key, "base_url": base_url, "flush_interval": 60}
        kwargs.update(overrides)
        return client_module.LedgerClient(**kwargs)

    return _make


def flush_client(client: "client_module.LedgerClient") -> None:
    if client._tracer_provider is not None:
        client._tracer_provider.force_flush()
    client._logger_provider.force_flush()
