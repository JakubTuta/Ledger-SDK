import pytest

import ledger.core.client as client_module
from tests.conftest import flush_client


class _FakeMetricExporter(client_module.metrics_export.MetricExporter):
    def export(self, *_args, **_kwargs):
        return client_module.metrics_export.MetricExportResult.SUCCESS

    def force_flush(self, *_args, **_kwargs):
        return True

    def shutdown(self, *_args, **_kwargs):
        return None


class TestClientValidation:
    def test_rejects_missing_api_key(self, base_url):
        with pytest.raises(ValueError, match="api_key"):
            client_module.LedgerClient(api_key="", base_url=base_url)

    def test_rejects_api_key_without_prefix(self, base_url):
        with pytest.raises(ValueError, match="ledger_"):
            client_module.LedgerClient(api_key="not_prefixed", base_url=base_url)

    def test_rejects_invalid_base_url_scheme(self, api_key):
        with pytest.raises(ValueError, match="base_url"):
            client_module.LedgerClient(api_key=api_key, base_url="ftp://example.com")

    def test_rejects_non_positive_flush_interval(self, api_key, base_url):
        with pytest.raises(ValueError, match="flush_interval"):
            client_module.LedgerClient(api_key=api_key, base_url=base_url, flush_interval=0)

    def test_rejects_removed_constructor_params(self, api_key, base_url):
        with pytest.raises(TypeError):
            client_module.LedgerClient(api_key=api_key, base_url=base_url, http_pool_size=10)

    def test_rejects_non_positive_metrics_export_interval(self, api_key, base_url):
        with pytest.raises(ValueError, match="metrics_export_interval"):
            client_module.LedgerClient(
                api_key=api_key, base_url=base_url, metrics_export_interval=0
            )


class TestMetricsExportInterval:
    def test_config_defaults(self):
        import ledger.core.config as config_module

        config = config_module.LedgerConfig()
        assert config.trace_sample_rate == 0.1
        assert config.metrics_export_interval == 60.0

    def _make_capturing_reader_class(self, captured_kwargs: dict):
        real_reader = client_module.metrics_export.PeriodicExportingMetricReader

        class _CapturingReader(real_reader):
            def __init__(self, exporter, **kwargs):
                captured_kwargs.update(kwargs)
                # Export far in the future so the background export thread never
                # fires a real HTTP request against the fake exporter during tests.
                kwargs["export_interval_millis"] = 3_600_000
                super().__init__(exporter, **kwargs)

        return _CapturingReader

    def test_default_export_interval_passed_to_reader(self, monkeypatch, make_client):
        captured_kwargs: dict = {}

        monkeypatch.setattr(
            client_module, "OTLPMetricExporter", lambda **_kwargs: _FakeMetricExporter()
        )
        monkeypatch.setattr(
            client_module.metrics_export,
            "PeriodicExportingMetricReader",
            self._make_capturing_reader_class(captured_kwargs),
        )

        client = make_client()
        client.shutdown_sync(timeout=1.0)

        assert captured_kwargs["export_interval_millis"] == 60000

    def test_custom_export_interval_passed_to_reader(self, monkeypatch, make_client):
        captured_kwargs: dict = {}

        monkeypatch.setattr(
            client_module, "OTLPMetricExporter", lambda **_kwargs: _FakeMetricExporter()
        )
        monkeypatch.setattr(
            client_module.metrics_export,
            "PeriodicExportingMetricReader",
            self._make_capturing_reader_class(captured_kwargs),
        )

        client = make_client(metrics_export_interval=7.5)
        client.shutdown_sync(timeout=1.0)

        assert captured_kwargs["export_interval_millis"] == 7500


class TestLoggingMethods:
    def test_log_info_exports_expected_severity_and_body(self, make_client, log_exporter):
        client = make_client()
        client.log_info("hello world", {"user_id": "123"})
        flush_client(client)

        records = log_exporter.get_finished_logs()
        assert len(records) == 1
        record = records[0].log_record
        assert record.severity_number.value == 9
        assert record.body == "hello world"
        assert record.attributes["user_id"] == "123"
        assert record.attributes["ledger.log_type"] == "console"
        assert record.attributes["ledger.importance"] == "standard"

    def test_log_error_sets_high_importance(self, make_client, log_exporter):
        client = make_client()
        client.log_error("payment failed")
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.severity_number.value == 17
        assert record.attributes["ledger.importance"] == "high"

    def test_log_exception_captures_type_message_stacktrace(self, make_client, log_exporter):
        client = make_client()
        try:
            raise ValueError("bad value")
        except ValueError as exc:
            client.log_exception(exc, attributes={"order_id": "abc"})
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.attributes["exception.type"] == "ValueError"
        assert record.attributes["exception.message"] == "bad value"
        assert "Traceback" in record.attributes["exception.stacktrace"]
        assert record.attributes["ledger.log_type"] == "exception"
        assert record.attributes["order_id"] == "abc"

    def test_log_exception_message_truncated(self, make_client, log_exporter):
        client = make_client()
        try:
            raise ValueError("x" * 6000)
        except ValueError as exc:
            client.log_exception(exc)
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert len(record.attributes["exception.message"]) <= 5000

    def test_log_endpoint_emits_semconv_attributes(self, make_client, log_exporter):
        client = make_client()
        client.log_endpoint(
            "GET",
            "/users/{id}",
            200,
            12.5,
            query_params="a=1",
            path_params={"id": "123"},
        )
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.attributes["http.request.method"] == "GET"
        assert record.attributes["http.route"] == "/users/{id}"
        assert record.attributes["http.response.status_code"] == 200
        assert record.attributes["ledger.duration_ms"] == 12.5
        assert record.attributes["url.query"] == "a=1"
        assert record.attributes["ledger.log_type"] == "endpoint"

    def test_log_endpoint_5xx_is_error_level(self, make_client, log_exporter):
        client = make_client()
        client.log_endpoint("GET", "/boom", 500, 1.0)
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.severity_number.value == 17
        assert record.attributes["ledger.importance"] == "high"


class TestTraceLogCorrelation:
    def test_log_inside_span_includes_trace_and_span_id(self, make_client, log_exporter):
        client = make_client()
        with client.tracer.start_as_current_span("test-span") as span:
            client.log_info("inside span")
            expected_trace_id = format(span.get_span_context().trace_id, "032x")
            expected_span_id = format(span.get_span_context().span_id, "016x")
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.attributes["trace_id"] == expected_trace_id
        assert record.attributes["span_id"] == expected_span_id

    def test_log_outside_span_has_no_trace_id(self, make_client, log_exporter):
        client = make_client()
        client.log_info("no span active")
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert "trace_id" not in record.attributes


class TestTracingDisabled:
    def test_tracer_is_none_when_disabled(self, make_client):
        client = make_client(tracing_enabled=False)
        assert client.tracer is None

    def test_logging_still_works_when_tracing_disabled(self, make_client, log_exporter):
        client = make_client(tracing_enabled=False)
        client.log_info("still logs")
        flush_client(client)

        assert len(log_exporter.get_finished_logs()) == 1


class TestHealthAndMetrics:
    def test_is_healthy_before_shutdown(self, make_client):
        client = make_client()
        assert client.is_healthy() is True

    def test_is_unhealthy_after_shutdown(self, make_client):
        client = make_client()
        client.shutdown_sync(timeout=1.0)
        assert client.is_healthy() is False

    def test_get_metrics_reports_version(self, make_client):
        client = make_client()
        metrics = client.get_metrics()
        assert "sdk" in metrics
        assert metrics["sdk"]["version"]

    def test_get_health_status_shape(self, make_client):
        client = make_client()
        status = client.get_health_status()
        assert status == {"status": "healthy", "healthy": True}


class TestSpanExport:
    def test_span_exported_with_service_resource(self, make_client, span_exporter):
        # Force full sampling: this test asserts on export/resource behavior,
        # not sampling, and the SDK default trace_sample_rate is 0.1.
        client = make_client(service_name="my-service", trace_sample_rate=1.0)
        with client.tracer.start_as_current_span("op"):
            pass
        flush_client(client)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].resource.attributes["service.name"] == "my-service"


@pytest.mark.asyncio
class TestAsyncShutdown:
    async def test_shutdown_flushes_and_marks_unhealthy(self, make_client, log_exporter):
        client = make_client()
        client.log_info("before shutdown")
        await client.shutdown(timeout=1.0)

        assert client.is_healthy() is False
        assert len(log_exporter.get_finished_logs()) == 1
