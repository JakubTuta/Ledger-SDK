import pytest

loguru = pytest.importorskip("loguru")

from ledger.integrations.loguru import add_loguru_sink  # noqa: E402
from tests.conftest import flush_client  # noqa: E402


class TestLoguruIntegration:
    def test_add_loguru_sink_forwards_info_log(self, make_client, log_exporter):
        client = make_client()
        handler_id = add_loguru_sink(client, level="TRACE")
        try:
            loguru.logger.bind(user_id=123).info("hello from loguru")
            flush_client(client)

            records = log_exporter.get_finished_logs()
            assert len(records) == 1
            record = records[0].log_record
            assert record.body == "hello from loguru"
            assert record.severity_text == "INFO"
            assert record.attributes["user_id"] == 123
            assert record.attributes["ledger.log_type"] == "logger"
        finally:
            loguru.logger.remove(handler_id)

    def test_add_loguru_sink_maps_levels(self, make_client, log_exporter):
        client = make_client()
        handler_id = add_loguru_sink(client, level="TRACE")
        try:
            loguru.logger.trace("trace msg")
            loguru.logger.debug("debug msg")
            loguru.logger.success("success msg")
            loguru.logger.warning("warning msg")
            loguru.logger.error("error msg")
            loguru.logger.critical("critical msg")
            flush_client(client)

            records = {r.log_record.body: r.log_record for r in log_exporter.get_finished_logs()}
            assert records["trace msg"].severity_text == "DEBUG"
            assert records["debug msg"].severity_text == "DEBUG"
            assert records["success msg"].severity_text == "INFO"
            assert records["warning msg"].severity_text == "WARN"
            assert records["error msg"].severity_text == "ERROR"
            assert records["critical msg"].severity_text == "FATAL"
        finally:
            loguru.logger.remove(handler_id)

    def test_add_loguru_sink_captures_exception(self, make_client, log_exporter):
        client = make_client()
        handler_id = add_loguru_sink(client, level="TRACE")
        try:
            try:
                raise ValueError("loguru boom")
            except ValueError:
                loguru.logger.exception("failed")

            flush_client(client)

            record = log_exporter.get_finished_logs()[0].log_record
            assert record.attributes["exception.type"] == "ValueError"
            assert record.attributes["exception.message"] == "loguru boom"
        finally:
            loguru.logger.remove(handler_id)

    def test_add_loguru_sink_returns_removable_handler_id(self, make_client, log_exporter):
        client = make_client()
        handler_id = add_loguru_sink(client)
        loguru.logger.remove(handler_id)

        loguru.logger.info("after removal, should not be forwarded")
        flush_client(client)
        assert len(log_exporter.get_finished_logs()) == 0
