import logging

import opentelemetry._logs as logs_api
import opentelemetry.sdk._logs as sdk_logs
import pytest

from tests.conftest import flush_client


@pytest.fixture
def root_logger():
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield root
    root.handlers[:] = handlers
    root.setLevel(level)


def _ledger_handlers(client, root):
    return [h for h in root.handlers if h is client._logging_handler]


@pytest.mark.usefixtures("root_logger")
def test_stdlib_warning_reaches_ledger(make_client, log_exporter):
    client = make_client()
    client.instrument_logging()

    logging.getLogger("app.orders").warning("payment provider slow")
    flush_client(client)

    assert [r.log_record.body for r in log_exporter.get_finished_logs()] == [
        "payment provider slow"
    ]


@pytest.mark.usefixtures("root_logger")
def test_records_reach_ledger_when_another_global_provider_exists(make_client, log_exporter):
    logs_api.set_logger_provider(sdk_logs.LoggerProvider())
    client = make_client()
    client.instrument_logging()

    logging.getLogger("app").error("disk almost full")
    flush_client(client)

    assert [r.log_record.body for r in log_exporter.get_finished_logs()] == ["disk almost full"]


def test_calling_twice_attaches_one_handler(make_client, root_logger):
    client = make_client()
    client.instrument_logging()
    client.instrument_logging()

    assert len(_ledger_handlers(client, root_logger)) == 1


def test_shutdown_detaches_the_handler(make_client, root_logger):
    client = make_client()
    client.instrument_logging()
    handler = client._logging_handler

    client.shutdown_sync(timeout=1)

    assert handler not in root_logger.handlers


def test_level_lowers_the_root_threshold(make_client, log_exporter, root_logger):
    root_logger.setLevel(logging.WARNING)
    client = make_client()
    client.instrument_logging(level=logging.INFO)

    logging.getLogger("app").info("cache warmed")
    flush_client(client)

    assert root_logger.level == logging.INFO
    assert [r.log_record.body for r in log_exporter.get_finished_logs()] == ["cache warmed"]
