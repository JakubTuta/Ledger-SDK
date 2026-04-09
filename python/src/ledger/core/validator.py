import json
from typing import Any

import ledger._logging as logging_module


class Validator:
    VALID_LEVELS: frozenset[str] = frozenset({"debug", "info", "warning", "error", "critical"})
    VALID_LOG_TYPES: frozenset[str] = frozenset(
        {"console", "logger", "exception", "database", "endpoint", "custom"}
    )
    VALID_IMPORTANCE: frozenset[str] = frozenset({"critical", "high", "standard", "low"})

    _ATTR_FAST_PATH_MAX_KEYS = 32
    _ATTR_FAST_PATH_MAX_VALUE_CHARS = 1000

    def __init__(self, constraints: dict[str, Any]):
        self.max_message_length: int = constraints["max_message_length"]
        self.max_error_message_length: int = constraints["max_error_message_length"]
        self.max_stack_trace_length: int = constraints["max_stack_trace_length"]
        self.max_attributes_size_bytes: int = constraints["max_attributes_size_bytes"]
        self.max_environment_length: int = constraints["max_environment_length"]
        self.max_release_length: int = constraints["max_release_length"]
        self.max_platform_version_length: int = constraints["max_platform_version_length"]
        self.max_error_type_length: int = constraints["max_error_type_length"]

    def validate_log(self, log_entry: dict[str, Any]) -> dict[str, Any]:
        validated = log_entry.copy()

        if "level" not in validated or validated["level"] not in self.VALID_LEVELS:
            validated["level"] = "info"

        if "log_type" not in validated or validated["log_type"] not in self.VALID_LOG_TYPES:
            validated["log_type"] = "console"

        if "importance" not in validated or validated["importance"] not in self.VALID_IMPORTANCE:
            validated["importance"] = "standard"

        if validated.get("message"):
            validated["message"] = self._truncate_string(
                validated["message"], self.max_message_length, "message"
            )

        if validated.get("error_message"):
            validated["error_message"] = self._truncate_string(
                validated["error_message"], self.max_error_message_length, "error_message"
            )

        if validated.get("stack_trace"):
            validated["stack_trace"] = self._truncate_string(
                validated["stack_trace"], self.max_stack_trace_length, "stack_trace"
            )

        if validated.get("error_type"):
            validated["error_type"] = self._truncate_string(
                validated["error_type"], self.max_error_type_length, "error_type"
            )

        if validated.get("environment"):
            validated["environment"] = self._truncate_string(
                validated["environment"], self.max_environment_length, "environment"
            )

        if validated.get("release"):
            validated["release"] = self._truncate_string(
                validated["release"], self.max_release_length, "release"
            )

        if validated.get("platform_version"):
            validated["platform_version"] = self._truncate_string(
                validated["platform_version"], self.max_platform_version_length, "platform_version"
            )

        if validated.get("attributes"):
            validated["attributes"] = self._validate_attributes(validated["attributes"])

        return validated

    def _truncate_string(self, value: str, max_length: int, field_name: str) -> str:
        if not isinstance(value, str):
            value = str(value)

        if len(value) <= max_length:
            return value

        truncated_suffix = "... [truncated]"
        truncate_at = max_length - len(truncated_suffix)

        logging_module.get_logger().warning(
            "Field '%s' truncated from %d to %d characters", field_name, len(value), max_length
        )

        return value[:truncate_at] + truncated_suffix

    def _validate_attributes(self, attributes: Any) -> dict[str, Any]:
        if not isinstance(attributes, dict):
            logging_module.get_logger().warning(
                "Attributes must be a dict, got %s, converting", type(attributes).__name__
            )
            return {"value": str(attributes)}

        if (
            len(attributes) <= self._ATTR_FAST_PATH_MAX_KEYS
            and all(
                isinstance(v, (int, float, bool, type(None)))
                or (isinstance(v, str) and len(v) <= self._ATTR_FAST_PATH_MAX_VALUE_CHARS)
                for v in attributes.values()
            )
        ):
            return attributes

        try:
            serialized = json.dumps(attributes)
            size_bytes = len(serialized.encode("utf-8"))

            if size_bytes > self.max_attributes_size_bytes:
                logging_module.get_logger().warning(
                    "Attributes size (%d bytes) exceeds max (%d bytes), truncating",
                    size_bytes,
                    self.max_attributes_size_bytes,
                )
                return self._truncate_attributes(attributes, self.max_attributes_size_bytes)

            return attributes

        except (TypeError, ValueError) as e:
            logging_module.get_logger().warning(
                "Attributes not JSON serializable: %s, removing", e
            )
            return {}

    def _truncate_attributes(self, attributes: dict[str, Any], max_bytes: int) -> dict[str, Any]:
        result = {}
        current_bytes = 2

        for key, value in attributes.items():
            try:
                item_json = json.dumps({key: value})
                item_bytes = len(item_json.encode("utf-8"))

                if current_bytes + item_bytes <= max_bytes - 100:
                    result[key] = value
                    current_bytes += item_bytes
                else:
                    result["_truncated"] = True
                    break

            except (TypeError, ValueError):
                continue

        return result
