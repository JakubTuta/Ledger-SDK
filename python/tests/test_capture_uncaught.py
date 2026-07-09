import asyncio
import sys
import threading

import pytest

from tests.conftest import flush_client


@pytest.fixture(autouse=True)
def _restore_global_hooks():
    original_sys_excepthook = sys.excepthook
    original_threading_excepthook = threading.excepthook
    policy = asyncio.get_event_loop_policy()
    original_new_event_loop = policy.new_event_loop
    yield
    sys.excepthook = original_sys_excepthook
    threading.excepthook = original_threading_excepthook
    policy.new_event_loop = original_new_event_loop


class TestCaptureUncaughtSysExcepthook:
    def test_chains_to_previous_hook_and_logs_exception(self, make_client, log_exporter):
        client = make_client()
        calls = []

        def custom_previous_hook(exc_type, exc_value, _exc_tb):
            calls.append((exc_type, exc_value))

        sys.excepthook = custom_previous_hook
        client.capture_uncaught()

        try:
            raise ValueError("boom")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            sys.excepthook(exc_type, exc_value, exc_tb)

        flush_client(client)

        records = log_exporter.get_finished_logs()
        assert len(records) == 1
        record = records[0].log_record
        assert record.attributes["exception.type"] == "ValueError"
        assert record.attributes["ledger.uncaught"] is True

        # The previously-installed hook must still run (not be swallowed).
        assert len(calls) == 1
        assert calls[0][0] is ValueError

    def test_capture_uncaught_is_idempotent(self, make_client, log_exporter):
        client = make_client()
        client.capture_uncaught()
        hook_after_first_call = sys.excepthook

        client.capture_uncaught()
        hook_after_second_call = sys.excepthook

        assert hook_after_first_call is hook_after_second_call

        try:
            raise RuntimeError("only once")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            sys.excepthook(exc_type, exc_value, exc_tb)

        flush_client(client)

        # A double-chained hook would log this exception twice.
        assert len(log_exporter.get_finished_logs()) == 1


class TestCaptureUncaughtThreadingExcepthook:
    def test_threading_excepthook_fires_and_chains(self, make_client, log_exporter):
        client = make_client()
        calls = []

        def custom_previous_hook(args):
            calls.append(args)

        threading.excepthook = custom_previous_hook
        client.capture_uncaught()

        def _raise():
            raise RuntimeError("thread boom")

        thread = threading.Thread(target=_raise, name="ledger-test-worker")
        thread.start()
        thread.join()

        flush_client(client)

        records = log_exporter.get_finished_logs()
        assert len(records) == 1
        record = records[0].log_record
        assert record.attributes["exception.type"] == "RuntimeError"
        assert record.attributes["ledger.uncaught"] is True
        assert record.attributes["thread.name"] == "ledger-test-worker"

        assert len(calls) == 1


class TestCaptureUncaughtAsyncio:
    @pytest.mark.asyncio
    async def test_asyncio_handler_logs_exception_on_running_loop(self, make_client, log_exporter):
        client = make_client()
        client.capture_uncaught()

        loop = asyncio.get_running_loop()
        assert loop.get_exception_handler() is not None

        try:
            raise RuntimeError("async boom")
        except RuntimeError as exc:
            loop.call_exception_handler(
                {"message": "Unhandled exception in task", "exception": exc}
            )

        flush_client(client)

        records = log_exporter.get_finished_logs()
        assert len(records) == 1
        record = records[0].log_record
        assert record.attributes["exception.type"] == "RuntimeError"
        assert record.attributes["ledger.uncaught"] is True
