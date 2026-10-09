import io

import opentelemetry._logs as logs_api
import opentelemetry.sdk._logs as sdk_logs
import opentelemetry.sdk._logs.export as logs_export
import opentelemetry.sdk.metrics.export as metrics_export
import opentelemetry.sdk.trace as sdk_trace
import opentelemetry.trace as trace_api

import ledger.core.client as client_module
import ledger.integrations.common as common_module
from tests.conftest import flush_client


def _install_foreign_otel_setup() -> None:
    """What `opentelemetry-instrument` or another vendor's SDK does at startup."""
    trace_api.set_tracer_provider(sdk_trace.TracerProvider())
    logs_api.set_logger_provider(sdk_logs.LoggerProvider())


def test_logs_and_spans_reach_ledger_when_otel_is_already_configured(
    make_client, span_exporter, log_exporter
):
    _install_foreign_otel_setup()
    client = make_client(trace_sample_rate=1.0)

    client.log_info("hello")
    with client.tracer.start_as_current_span("work"):
        pass
    flush_client(client)

    assert [r.log_record.body for r in log_exporter.get_finished_logs()] == ["hello"]
    assert [s.name for s in span_exporter.get_finished_spans()] == ["work"]


def test_integration_spans_use_the_ledger_provider(make_client, span_exporter):
    _install_foreign_otel_setup()
    client = make_client(trace_sample_rate=1.0)

    with common_module.http_server_span("GET", "/items", "http://x/items?token=s3cr3t", {}):
        pass
    flush_client(client)

    (span,) = span_exporter.get_finished_spans()
    assert span.attributes["url.full"] == "http://x/items"


def test_a_second_client_still_exports(make_client, monkeypatch):
    # shutdown_sync() flushes metrics; keep that export in-process.
    monkeypatch.setattr(
        client_module,
        "OTLPMetricExporter",
        lambda **_kwargs: metrics_export.ConsoleMetricExporter(out=io.StringIO()),
    )
    first = make_client()
    first.shutdown_sync(timeout=1)
    # Each real client owns its exporter; the fixture's was stopped by `first`.
    second_exporter = logs_export.InMemoryLogRecordExporter()
    monkeypatch.setattr(client_module, "OTLPLogExporter", lambda **_kwargs: second_exporter)
    second = client_module.LedgerClient(
        api_key=first.api_key, base_url=first.base_url, flush_interval=60
    )

    second.log_info("from the second client")
    flush_client(second)

    assert [r.log_record.body for r in second_exporter.get_finished_logs()] == [
        "from the second client"
    ]


def test_url_without_query_keeps_only_the_location():
    assert (
        common_module.url_without_query("https://api.example.com/reset?code=abc#frag")
        == "https://api.example.com/reset"
    )
