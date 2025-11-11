import pytest

from ledger.core.validator import Validator


class TestValidator:
    @pytest.fixture
    def validator(self):
        constraints = {
            "max_message_length": 100,
            "max_error_message_length": 50,
            "max_stack_trace_length": 500,
            "max_attributes_size_bytes": 1024,
        }
        return Validator(constraints)

    def test_validate_valid_log(self, validator):
        log_entry = {
            "timestamp": "2025-01-11T10:00:00Z",
            "level": "info",
            "log_type": "console",
            "importance": "standard",
            "message": "Test message",
        }

        validated = validator.validate_log(log_entry)

        assert validated["level"] == "info"
        assert validated["log_type"] == "console"
        assert validated["importance"] == "standard"
        assert validated["message"] == "Test message"

    def test_validate_with_invalid_level(self, validator):
        log_entry = {
            "level": "invalid_level",
            "log_type": "console",
            "importance": "standard",
        }

        validated = validator.validate_log(log_entry)

        assert validated["level"] == "info"

    def test_truncate_long_message(self, validator):
        long_message = "A" * 200
        log_entry = {
            "level": "info",
            "log_type": "console",
            "importance": "standard",
            "message": long_message,
        }

        validated = validator.validate_log(log_entry)

        assert len(validated["message"]) == 100
        assert validated["message"].endswith("... [truncated]")

    def test_validate_attributes(self, validator):
        log_entry = {
            "level": "info",
            "log_type": "console",
            "importance": "standard",
            "attributes": {"user_id": 123, "action": "login"},
        }

        validated = validator.validate_log(log_entry)

        assert validated["attributes"]["user_id"] == 123
        assert validated["attributes"]["action"] == "login"

    def test_validate_invalid_attributes(self, validator):
        log_entry = {
            "level": "info",
            "log_type": "console",
            "importance": "standard",
            "attributes": "not_a_dict",
        }

        validated = validator.validate_log(log_entry)

        assert isinstance(validated["attributes"], dict)
        assert "value" in validated["attributes"]

    def test_normalize_timestamp(self, validator):
        log_entry = {
            "level": "info",
            "log_type": "console",
            "importance": "standard",
            "timestamp": "2025-01-11T10:00:00Z",
        }

        validated = validator.validate_log(log_entry)

        assert validated["timestamp"] == "2025-01-11T10:00:00Z"
