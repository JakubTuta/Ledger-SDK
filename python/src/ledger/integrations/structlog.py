"""Optional structlog processor that forwards events into a LedgerClient.

`structlog` is not a hard dependency of the SDK -- nothing here imports it
at module load time, so importing this module is safe even when
`structlog` isn't installed (install the `structlog` extra:
`pip install ledger-sdk[structlog]`).
"""

import sys
from typing import Any

import ledger.core.client as client_module

# structlog level/method name -> Ledger SDK level key (see
# client._SEVERITY_BY_LEVEL). structlog has no dedicated "critical" method by
# default but honors it if used; "warn"/"fatal"/"exception" are common
# aliases/derived methods that need folding into the SDK's five levels.
_STRUCTLOG_TO_SDK_LEVEL: dict[str, str] = {
    "debug": "debug",
    "info": "info",
    "warning": "warning",
    "warn": "warning",
    "error": "error",
    "exception": "error",
    "critical": "critical",
    "fatal": "critical",
}


def ledger_structlog_processor(
    client: "client_module.LedgerClient",
) -> "Any":
    """Build a structlog processor that tees every event to Ledger.

    Use it in `structlog.configure(processors=[...])`, placed before your
    normal rendering processor. Each event is forwarded through the same
    code path `LedgerClient._log` uses internally (trace/span correlation,
    attribute validation, truncation) and mapped into
    `{message, attributes, exception}`. The processor returns the event dict
    unchanged so the rest of your structlog pipeline (console rendering,
    JSON output, etc.) keeps working exactly as before.

    Args:
        client: The LedgerClient to forward events to.

    Returns:
        A processor callable usable in `structlog.configure(processors=[...])`.

    Example:
        >>> import structlog
        >>> from ledger.integrations.structlog import ledger_structlog_processor
        >>> structlog.configure(
        ...     processors=[
        ...         ledger_structlog_processor(client),
        ...         structlog.processors.JSONRenderer(),
        ...     ]
        ... )
        >>> structlog.get_logger().info("hello from structlog", user_id=123)
    """

    def _processor(_logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        payload = dict(event_dict)
        message = payload.pop("event", "")
        level_name = str(payload.pop("level", method_name) or method_name).lower()
        sdk_level = _STRUCTLOG_TO_SDK_LEVEL.get(level_name, "info")
        payload.pop("timestamp", None)

        exc_info = payload.pop("exc_info", None)
        exception: BaseException | None = None
        if isinstance(exc_info, BaseException):
            exception = exc_info
        elif exc_info is True:
            exception = sys.exc_info()[1]
        elif isinstance(exc_info, tuple) and len(exc_info) == 3:
            exception = exc_info[1]

        client._log(
            level=sdk_level,
            log_type="logger",
            importance="high" if sdk_level in ("error", "critical") else "standard",
            message=str(message),
            attributes=payload,
            exception=exception,
        )

        return event_dict

    return _processor
