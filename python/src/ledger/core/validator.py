import json
from typing import Any

import ledger._logging as logging_module

_TRUNCATED_SUFFIX = "... [truncated]"


class Validator:
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

    def truncate_message(self, value: str) -> str:
        return self._truncate_string(value, self.max_message_length, "message")

    def truncate_error_message(self, value: str) -> str:
        return self._truncate_string(value, self.max_error_message_length, "error_message")

    def truncate_stack_trace(self, value: str) -> str:
        return self._truncate_string(value, self.max_stack_trace_length, "stack_trace")

    def truncate_error_type(self, value: str) -> str:
        return self._truncate_string(value, self.max_error_type_length, "error_type")

    def truncate_environment(self, value: str) -> str:
        return self._truncate_string(value, self.max_environment_length, "environment")

    def truncate_release(self, value: str) -> str:
        return self._truncate_string(value, self.max_release_length, "release")

    def truncate_platform_version(self, value: str) -> str:
        return self._truncate_string(value, self.max_platform_version_length, "platform_version")

    def normalize_log_type(self, value: Any) -> str:
        if isinstance(value, str) and value in self.VALID_LOG_TYPES:
            return value
        return "console"

    def normalize_importance(self, value: Any) -> str:
        if isinstance(value, str) and value in self.VALID_IMPORTANCE:
            return value
        return "standard"

    def validate_attributes(self, attributes: Any) -> dict[str, Any]:
        if not isinstance(attributes, dict):
            logging_module.get_logger().warning(
                "Attributes must be a dict, got %s, converting", type(attributes).__name__
            )
            return {"value": str(attributes)}

        if len(attributes) <= self._ATTR_FAST_PATH_MAX_KEYS and all(
            isinstance(v, (int, float, bool, type(None)))
            or (isinstance(v, str) and len(v) <= self._ATTR_FAST_PATH_MAX_VALUE_CHARS)
            for v in attributes.values()
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
            logging_module.get_logger().warning("Attributes not JSON serializable: %s, removing", e)
            return {}

    def _truncate_string(self, value: str, max_length: int, field_name: str) -> str:
        if not isinstance(value, str):
            value = str(value)

        if len(value) <= max_length:
            return value

        truncate_at = max_length - len(_TRUNCATED_SUFFIX)

        logging_module.get_logger().warning(
            "Field '%s' truncated from %d to %d characters", field_name, len(value), max_length
        )

        return value[:truncate_at] + _TRUNCATED_SUFFIX

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
