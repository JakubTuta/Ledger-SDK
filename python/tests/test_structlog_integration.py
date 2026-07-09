import pytest

structlog = pytest.importorskip("structlog")

from ledger.integrations.structlog import ledger_structlog_processor  # noqa: E402
from tests.conftest import flush_client  # noqa: E402


class TestStructlogIntegration:
    def test_processor_forwards_event_and_returns_original_dict(self, make_client, log_exporter):
        client = make_client()
        processor = ledger_structlog_processor(client)

        event_dict = {"event": "user logged in", "level": "info", "user_id": 42}
        result = processor(None, "info", event_dict)

        # Original event dict must come back unmodified so downstream
        # processors (renderers) keep working normally.
        assert result is event_dict
        assert event_dict == {"event": "user logged in", "level": "info", "user_id": 42}

        flush_client(client)
        records = log_exporter.get_finished_logs()
        assert len(records) == 1
        record = records[0].log_record
        assert record.body == "user logged in"
        assert record.attributes["user_id"] == 42
        assert record.severity_text == "INFO"

    def test_processor_maps_levels(self, make_client, log_exporter):
        client = make_client()
        processor = ledger_structlog_processor(client)

        processor(None, "warning", {"event": "careful"})
        processor(None, "error", {"event": "oops"})
        processor(None, "critical", {"event": "fire"})
        flush_client(client)

        records = {r.log_record.body: r.log_record for r in log_exporter.get_finished_logs()}
        assert records["careful"].severity_text == "WARN"
        assert records["oops"].severity_text == "ERROR"
        assert records["fire"].severity_text == "FATAL"

    def test_processor_captures_exc_info_true(self, make_client, log_exporter):
        client = make_client()
        processor = ledger_structlog_processor(client)

        try:
            raise ValueError("structlog boom")
        except ValueError:
            processor(None, "error", {"event": "failed", "exc_info": True})

        flush_client(client)
        record = log_exporter.get_finished_logs()[0].log_record
        assert record.attributes["exception.type"] == "ValueError"
        assert record.attributes["exception.message"] == "structlog boom"

    def test_processor_within_full_structlog_pipeline(self, make_client, log_exporter):
        client = make_client()
        structlog.configure(
            processors=[
                ledger_structlog_processor(client),
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(),
        )
        try:
            log = structlog.get_logger()
            log.info("pipeline event", order_id="abc")
            flush_client(client)

            records = log_exporter.get_finished_logs()
            assert len(records) == 1
            record = records[0].log_record
            assert record.body == "pipeline event"
            assert record.attributes["order_id"] == "abc"
        finally:
            structlog.reset_defaults()
