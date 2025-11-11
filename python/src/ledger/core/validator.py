import json
import sys
from typing import Any


class Validator:
    VALID_LEVELS = {"debug", "info", "warning", "error", "critical"}
    VALID_LOG_TYPES = {"console", "logger", "exception", "custom"}
    VALID_IMPORTANCE = {"low", "standard", "high"}

    def __init__(self, constraints: dict[str, Any]):
        self.max_message_length = constraints.get("max_message_length", 10000)
        self.max_error_message_length = constraints.get("max_error_message_length", 5000)
        self.max_stack_trace_length = constraints.get("max_stack_trace_length", 50000)
        self.max_attributes_size_bytes = constraints.get("max_attributes_size_bytes", 102400)

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

        if validated.get("attributes"):
            validated["attributes"] = self._validate_attributes(validated["attributes"])

        if "timestamp" in validated:
            validated["timestamp"] = self._normalize_timestamp(validated["timestamp"])

        return validated

    def _truncate_string(self, value: str, max_length: int, field_name: str) -> str:
        if not isinstance(value, str):
            value = str(value)

        if len(value) <= max_length:
            return value

        truncated_suffix = "... [truncated]"
        truncate_at = max_length - len(truncated_suffix)

        self._log_validation_warning(
            f"Field '{field_name}' truncated from {len(value)} to {max_length} characters"
        )

        return value[:truncate_at] + truncated_suffix

    def _validate_attributes(self, attributes: Any) -> dict[str, Any]:
        if not isinstance(attributes, dict):
            self._log_validation_warning(
                f"Attributes must be a dict, got {type(attributes).__name__}, converting"
            )
            return {"value": str(attributes)}

        try:
            serialized = json.dumps(attributes)
            size_bytes = len(serialized.encode("utf-8"))

            if size_bytes > self.max_attributes_size_bytes:
                self._log_validation_warning(
                    f"Attributes size ({size_bytes} bytes) exceeds max ({self.max_attributes_size_bytes} bytes), truncating"
                )

                return self._truncate_attributes(attributes, self.max_attributes_size_bytes)

            return attributes

        except (TypeError, ValueError) as e:
            self._log_validation_warning(f"Attributes not JSON serializable: {e}, removing")
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

    def _normalize_timestamp(self, timestamp: str) -> str:
        if isinstance(timestamp, str) and timestamp.endswith("Z"):
            return timestamp

        if isinstance(timestamp, str):
            return timestamp

        return str(timestamp)

    def _log_validation_warning(self, message: str) -> None:
        sys.stderr.write(f"[Ledger SDK] [VALIDATION WARNING] {message}\n")
        sys.stderr.flush()
