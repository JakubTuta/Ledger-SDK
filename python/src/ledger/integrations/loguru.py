"""Optional loguru sink that forwards records into a LedgerClient.

`loguru` is not a hard dependency of the SDK -- it is only imported inside
`add_loguru_sink`, so importing this module is safe even when `loguru` isn't
installed; only calling `add_loguru_sink` requires it (install the `loguru`
extra: `pip install ledger-sdk[loguru]`).
"""

from typing import TYPE_CHECKING, Any

import ledger.core.client as client_module

if TYPE_CHECKING:
    import loguru as _loguru_typing

# loguru level name -> Ledger SDK level key (see client._SEVERITY_BY_LEVEL).
# Ledger's schema has no TRACE/SUCCESS levels, so they're folded into the
# nearest equivalent: TRACE -> debug, SUCCESS -> info.
_LOGURU_TO_SDK_LEVEL: dict[str, str] = {
    "TRACE": "debug",
    "DEBUG": "debug",
    "INFO": "info",
    "SUCCESS": "info",
    "WARNING": "warning",
    "ERROR": "error",
    "CRITICAL": "critical",
}


def add_loguru_sink(client: "client_module.LedgerClient", level: str = "INFO") -> int:
    """Forward loguru log records into Ledger via `loguru.logger.add`.

    Emits through the same code path `LedgerClient._log` uses internally
    (trace/span correlation, attribute validation, truncation), so records
    logged via loguru behave identically to records logged via
    `client.log_info`/`log_error`/etc.

    Args:
        client: The LedgerClient to forward records to.
        level: Minimum loguru level to forward (passed straight to
            `loguru.logger.add`).

    Returns:
        The loguru handler id, so the caller can later remove it with
        `loguru.logger.remove(handler_id)`.

    Example:
        >>> from loguru import logger
        >>> from ledger.integrations.loguru import add_loguru_sink
        >>> add_loguru_sink(client)
        >>> logger.info("hello from loguru", user_id=123)
    """
    import loguru as _loguru

    def _sink(message: "_loguru_typing.Message") -> None:
        record = message.record
        loguru_level_name = record["level"].name
        sdk_level = _LOGURU_TO_SDK_LEVEL.get(loguru_level_name, "info")

        attributes: dict[str, Any] = dict(record["extra"])
        attributes["logger.name"] = record["name"] or ""
        attributes["logger.function"] = record["function"]
        attributes["logger.line"] = record["line"]

        exception = None
        record_exception = record["exception"]
        if record_exception is not None:
            exception = record_exception.value

        client._log(
            level=sdk_level,
            log_type="logger",
            importance="high" if sdk_level in ("error", "critical") else "standard",
            message=record["message"],
            attributes=attributes,
            exception=exception,
        )

    return _loguru.logger.add(_sink, level=level)
