from collections.abc import Callable
from typing import Any

import opentelemetry.sdk._logs as sdk_logs
import uuid6

import ledger.core.validator as validator_module
from ledger._version import __version__


class LedgerLogRecordProcessor(sdk_logs.LogRecordProcessor):
    """Enriches and truncates every emitted log record before export.

    Runs synchronously inside Logger.emit, ahead of the (downstream) export
    processor, so truncation, `before_send`, and PII scrubbing always apply
    regardless of which exporter is configured.

    This processor owns the downstream (export) processor directly, rather
    than being registered alongside it as a sibling on the LoggerProvider,
    so that a `before_send` hook returning None can genuinely drop a record
    -- there is no other way to stop a sibling BatchLogRecordProcessor from
    exporting a record once LoggerProvider has handed it to every processor.
    """

    def __init__(
        self,
        validator: validator_module.Validator,
        downstream: "sdk_logs.LogRecordProcessor | None" = None,
        before_send: "Callable[[dict[str, Any]], dict[str, Any] | None] | None" = None,
    ) -> None:
        self._validator = validator
        self._downstream = downstream
        self._before_send = before_send

    def on_emit(self, log_record: "sdk_logs.ReadWriteLogRecord") -> None:
        record = log_record.log_record

        if record.body is not None:
            record.body = self._validator.truncate_message(str(record.body))

        attributes = record.attributes
        if attributes is None:
            attributes = {}
            record.attributes = attributes

        exception_type = attributes.get("exception.type")
        if exception_type is not None:
            attributes["exception.type"] = self._validator.truncate_error_type(str(exception_type))

        exception_message = attributes.get("exception.message")
        if exception_message is not None:
            attributes["exception.message"] = self._validator.truncate_error_message(
                str(exception_message)
            )

        exception_stacktrace = attributes.get("exception.stacktrace")
        if exception_stacktrace is not None:
            attributes["exception.stacktrace"] = self._validator.truncate_stack_trace(
                str(exception_stacktrace)
            )

        attributes["ledger.log_type"] = self._validator.normalize_log_type(
            attributes.get("ledger.log_type")
        )
        attributes["ledger.importance"] = self._validator.normalize_importance(
            attributes.get("ledger.importance")
        )
        attributes["ledger.sdk_version"] = __version__

        if not attributes.get("ledger.log_id"):
            attributes["ledger.log_id"] = uuid6.uuid7().hex

        if self._before_send is not None:
            payload: dict[str, Any] = {
                "body": record.body,
                "attributes": dict(attributes),
                "severity_number": record.severity_number,
                "severity_text": record.severity_text,
            }
            result = self._before_send(payload)

            if result is None:
                # Dropped: never forwarded to the downstream export processor.
                return

            record.body = result.get("body", record.body)
            new_attributes = result.get("attributes")
            if new_attributes is not None and new_attributes is not attributes:
                attributes.clear()
                attributes.update(new_attributes)
            if "severity_number" in result:
                record.severity_number = result["severity_number"]
            if "severity_text" in result:
                record.severity_text = result["severity_text"]

        if self._downstream is not None:
            self._downstream.on_emit(log_record)

    def shutdown(self) -> None:
        if self._downstream is not None:
            self._downstream.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        if self._downstream is not None:
            return self._downstream.force_flush(timeout_millis)
        return True
