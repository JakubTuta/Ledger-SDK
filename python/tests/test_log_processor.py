import ledger.core.config as config_module
import ledger.core.log_processor as log_processor_module
import ledger.core.validator as validator_module


class _FakeInner:
    def __init__(self, body=None, attributes=None):
        self.body = body
        self.attributes = attributes if attributes is not None else {}


class _FakeLogRecord:
    def __init__(self, body=None, attributes=None):
        self.log_record = _FakeInner(body, attributes)


def _make_processor() -> log_processor_module.LedgerLogRecordProcessor:
    validator = validator_module.Validator(config_module.DEFAULT_CONSTRAINTS)
    return log_processor_module.LedgerLogRecordProcessor(validator)


def test_on_emit_injects_log_id_when_missing():
    processor = _make_processor()
    record = _FakeLogRecord(body="hello", attributes={})

    processor.on_emit(record)

    log_id = record.log_record.attributes["ledger.log_id"]
    assert isinstance(log_id, str)
    assert len(log_id) == 32


def test_on_emit_preserves_existing_log_id():
    processor = _make_processor()
    record = _FakeLogRecord(body="hello", attributes={"ledger.log_id": "custom-id"})

    processor.on_emit(record)

    assert record.log_record.attributes["ledger.log_id"] == "custom-id"


def test_on_emit_generates_distinct_ids_per_record():
    processor = _make_processor()
    record_a = _FakeLogRecord(body="a", attributes={})
    record_b = _FakeLogRecord(body="b", attributes={})

    processor.on_emit(record_a)
    processor.on_emit(record_b)

    assert (
        record_a.log_record.attributes["ledger.log_id"]
        != record_b.log_record.attributes["ledger.log_id"]
    )


def test_on_emit_truncates_message_body():
    processor = _make_processor()
    long_message = "x" * (config_module.DEFAULT_CONSTRAINTS["max_message_length"] + 500)
    record = _FakeLogRecord(body=long_message, attributes={})

    processor.on_emit(record)

    assert len(record.log_record.body) <= config_module.DEFAULT_CONSTRAINTS["max_message_length"]


def test_on_emit_initializes_log_id_when_attributes_is_none():
    processor = _make_processor()
    record = _FakeLogRecord(body="hello", attributes=None)

    processor.on_emit(record)

    assert record.log_record.attributes is not None
    assert "ledger.log_id" in record.log_record.attributes
