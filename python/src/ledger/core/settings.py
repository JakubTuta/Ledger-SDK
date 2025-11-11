from typing import Any


class SettingsManager:
    def __init__(self):
        self._settings = self._get_default_settings()

    def get_settings(self) -> dict[str, Any]:
        return self._settings

    def get_rate_limits(self) -> dict[str, int]:
        return self._settings["rate_limits"]

    def get_constraints(self) -> dict[str, Any]:
        return self._settings["constraints"]

    def _get_default_settings(self) -> dict[str, Any]:
        return {
            "rate_limits": {
                "requests_per_minute": 1000,
                "requests_per_hour": 50000,
            },
            "constraints": {
                "max_batch_size": 1000,
                "max_message_length": 10000,
                "max_error_message_length": 5000,
                "max_stack_trace_length": 50000,
                "max_attributes_size_bytes": 102400,
            },
        }
