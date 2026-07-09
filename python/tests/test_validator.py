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
            "max_environment_length": 20,
            "max_release_length": 100,
            "max_platform_version_length": 50,
            "max_error_type_length": 255,
        }
        return Validator(constraints)

    def test_truncate_message_under_limit(self, validator):
        assert validator.truncate_message("short") == "short"

    def test_truncate_message_over_limit(self, validator):
        truncated = validator.truncate_message("A" * 200)
        assert len(truncated) == 100
        assert truncated.endswith("... [truncated]")

    def test_truncate_error_message(self, validator):
        truncated = validator.truncate_error_message("E" * 100)
        assert len(truncated) == 50

    def test_truncate_stack_trace(self, validator):
        truncated = validator.truncate_stack_trace("S" * 1000)
        assert len(truncated) == 500

    def test_truncate_error_type_under_limit(self, validator):
        assert validator.truncate_error_type("ValueError") == "ValueError"

    def test_truncate_environment(self, validator):
        truncated = validator.truncate_environment("X" * 30)
        assert len(truncated) == 20

    def test_truncate_release(self, validator):
        assert validator.truncate_release("v1.2.3") == "v1.2.3"

    def test_normalize_log_type_valid(self, validator):
        assert validator.normalize_log_type("exception") == "exception"

    def test_normalize_log_type_invalid_defaults_to_console(self, validator):
        assert validator.normalize_log_type("not_a_type") == "console"

    def test_normalize_log_type_none_defaults_to_console(self, validator):
        assert validator.normalize_log_type(None) == "console"

    def test_normalize_importance_valid(self, validator):
        assert validator.normalize_importance("critical") == "critical"

    def test_normalize_importance_invalid_defaults_to_standard(self, validator):
        assert validator.normalize_importance("urgent") == "standard"

    def test_validate_attributes_passthrough(self, validator):
        attributes = {"user_id": 123, "action": "login"}
        validated = validator.validate_attributes(attributes)
        assert validated["user_id"] == 123
        assert validated["action"] == "login"

    def test_validate_attributes_non_dict_converted(self, validator):
        validated = validator.validate_attributes("not_a_dict")
        assert isinstance(validated, dict)
        assert "value" in validated

    def test_validate_attributes_oversized_truncated(self, validator):
        attributes = {f"key_{i}": "x" * 100 for i in range(50)}
        validated = validator.validate_attributes(attributes)
        assert "_truncated" in validated

    def test_validate_attributes_not_json_serializable(self, validator):
        class Unserializable:
            pass

        attributes = {f"key_{i}": Unserializable() for i in range(50)}
        validated = validator.validate_attributes(attributes)
        assert validated == {}
