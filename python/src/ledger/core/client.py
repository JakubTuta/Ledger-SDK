import sys
import traceback
from datetime import datetime, timezone
from typing import Any

import ledger.core.buffer as buffer_module
import ledger.core.config as config_module
import ledger.core.flusher as flusher_module
import ledger.core.http_client as http_client_module
import ledger.core.rate_limiter as rate_limiter_module
import ledger.core.settings as settings_module
import ledger.core.validator as validator_module


class LedgerClient:
    """Client for sending logs to the Ledger logging service.

    The LedgerClient handles log buffering, batching, rate limiting, and automatic
    retries with circuit breaker protection. Logs are sent asynchronously in the
    background to minimize performance impact on your application.

    Example:
        >>> client = LedgerClient(api_key="ledger_your_api_key")
    >>> client.log_info("User logged in", {"user_id": "123"})
    >>> await client.shutdown()
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        flush_interval: float | None = None,
        flush_size: int | None = None,
        max_buffer_size: int | None = None,
        http_timeout: float | None = None,
        http_pool_size: int | None = None,
        rate_limit_buffer: float | None = None,
        environment: str | None = None,
        release: str | None = None,
        platform_version: str | None = None,
    ):
        """Initialize the Ledger client.

        Args:
            api_key: Your Ledger API key (must start with 'ledger_').
            base_url: Base URL for the Ledger API. If not provided, uses the default
                production endpoint.
            flush_interval: How often (in seconds) to automatically flush buffered logs.
                Default is from config.
            flush_size: Maximum number of logs to include in a single batch.
                Default is from config.
            max_buffer_size: Maximum number of logs to hold in memory before dropping
                old logs. Default is from config.
            http_timeout: Timeout in seconds for HTTP requests. Default is from config.
            http_pool_size: Maximum number of concurrent HTTP connections.
                Default is from config.
            rate_limit_buffer: Safety margin (0-1) for rate limiting. For example, 0.9
                means use 90% of the allowed rate. Default is from config.
            environment: Optional environment identifier (e.g., "production", "staging").
                Attached to all logs.
            release: Optional release version identifier. Attached to all logs.
            platform_version: Python version string. Auto-detected if not provided.

        Raises:
            ValueError: If configuration parameters are invalid (e.g., invalid API key,
                negative timeouts, invalid URLs).
        """
        config = config_module.DEFAULT_CONFIG

        base_url = base_url or config.base_url
        flush_interval = flush_interval or config.flush_interval
        flush_size = flush_size or config.flush_size
        max_buffer_size = max_buffer_size or config.max_buffer_size
        http_timeout = http_timeout or config.http_timeout
        http_pool_size = http_pool_size or config.http_pool_size
        rate_limit_buffer = rate_limit_buffer or config.rate_limit_buffer
        self._validate_config(
            api_key=api_key,
            base_url=base_url,
            flush_interval=flush_interval,
            flush_size=flush_size,
            max_buffer_size=max_buffer_size,
            http_timeout=http_timeout,
            http_pool_size=http_pool_size,
            rate_limit_buffer=rate_limit_buffer,
        )

        self.api_key = api_key
        self.base_url = base_url
        self.environment = environment
        self.release = release
        self.platform_version = (
            platform_version
            or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )

        self._http_client = http_client_module.HTTPClient(
            base_url=base_url,
            api_key=api_key,
            timeout=http_timeout,
            pool_size=http_pool_size,
        )

        self._settings_manager = settings_module.SettingsManager()

        self._buffer = buffer_module.LogBuffer(max_size=max_buffer_size)

        rate_limits = self._settings_manager.get_rate_limits()
        self._rate_limiter = rate_limiter_module.RateLimiter(
            requests_per_minute=rate_limits["requests_per_minute"],
            requests_per_hour=rate_limits["requests_per_hour"],
            buffer=rate_limit_buffer,
        )

        constraints = self._settings_manager.get_constraints()
        self._validator = validator_module.Validator(constraints)

        self._flusher = flusher_module.BackgroundFlusher(
            buffer=self._buffer,
            http_client=self._http_client,
            rate_limiter=self._rate_limiter,
            flush_interval=flush_interval,
            max_batch_size=constraints["max_batch_size"],
        )

        self._flusher.start()

        self._sdk_start_time = datetime.now(timezone.utc)

    def _validate_config(
        self,
        api_key: str,
        base_url: str,
        flush_interval: float,
        flush_size: int,
        max_buffer_size: int,
        http_timeout: float,
        http_pool_size: int,
        rate_limit_buffer: float,
    ) -> None:
        errors = []

        if not api_key or not isinstance(api_key, str):
            errors.append("api_key must be a non-empty string")

        if not api_key.startswith("ledger_"):
            errors.append("api_key must start with 'ledger_' prefix")

        if not base_url or not isinstance(base_url, str):
            errors.append("base_url must be a non-empty string")

        if not base_url.startswith(("http://", "https://")):
            errors.append("base_url must start with 'http://' or 'https://'")

        if flush_interval <= 0:
            errors.append(f"flush_interval must be positive, got {flush_interval}")

        if flush_size <= 0:
            errors.append(f"flush_size must be positive, got {flush_size}")

        if max_buffer_size <= 0:
            errors.append(f"max_buffer_size must be positive, got {max_buffer_size}")

        if http_timeout <= 0:
            errors.append(f"http_timeout must be positive, got {http_timeout}")

        if http_pool_size <= 0:
            errors.append(f"http_pool_size must be positive, got {http_pool_size}")

        if not 0 < rate_limit_buffer <= 1:
            errors.append(f"rate_limit_buffer must be between 0 and 1, got {rate_limit_buffer}")

        if errors:
            raise ValueError("Invalid Ledger SDK configuration:\n  - " + "\n  - ".join(errors))

    def log_info(
        self,
        message: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Log an informational message.

        Args:
            message: The log message to record.
            attributes: Optional dictionary of custom attributes to attach to the log.
                Can contain any JSON-serializable values.

        Example:
            >>> client.log_info("User logged in", {"user_id": "123", "ip": "192.168.1.1"})
        """
        self._log(
            level="info",
            log_type="console",
            importance="standard",
            message=message,
            attributes=attributes,
        )

    def log_error(
        self,
        message: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Log an error message.

        Args:
            message: The error message to record.
            attributes: Optional dictionary of custom attributes to attach to the log.
                Can contain any JSON-serializable values.

        Example:
            >>> client.log_error("Payment failed", {"order_id": "ORD-123", "amount": 99.99})
        """
        self._log(
            level="error",
            log_type="console",
            importance="high",
            message=message,
            attributes=attributes,
        )

    def log_exception(
        self,
        exception: Exception,
        message: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Log an exception with full stack trace.

        Automatically captures the exception type, message, and full stack trace.

        Args:
            exception: The exception object to log.
            message: Optional custom message. If not provided, uses str(exception).
            attributes: Optional dictionary of custom attributes to attach to the log.
                Can contain any JSON-serializable values.

        Example:
            >>> try:
            ...     risky_operation()
            ... except Exception as e:
            ...     client.log_exception(e, "Failed to process order", {"order_id": "123"})
        """
        stack_trace = "".join(
            traceback.format_exception(
                type(exception),
                exception,
                exception.__traceback__,
            )
        )

        self._log(
            level="error",
            log_type="exception",
            importance="high",
            message=message or str(exception),
            error_type=exception.__class__.__name__,
            error_message=str(exception),
            stack_trace=stack_trace,
            attributes=attributes,
        )

    def _log(
        self,
        level: str,
        log_type: str,
        importance: str,
        message: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        stack_trace: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        from ledger._version import __version__

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": level,
            "log_type": log_type,
            "importance": importance,
        }

        if message:
            log_entry["message"] = message

        if error_type:
            log_entry["error_type"] = error_type

        if error_message:
            log_entry["error_message"] = error_message

        if stack_trace:
            log_entry["stack_trace"] = stack_trace

        if attributes:
            log_entry["attributes"] = attributes

        log_entry["sdk_version"] = __version__
        log_entry["platform"] = "python"
        log_entry["platform_version"] = self.platform_version

        if self.environment:
            log_entry["environment"] = self.environment

        if self.release:
            log_entry["release"] = self.release

        validated_log = self._validator.validate_log(log_entry)

        self._buffer.add(validated_log)

    def is_healthy(self) -> bool:
        """Check if the client is operating normally.

        Returns False if any of the following conditions are met:
        - Circuit breaker is open (too many consecutive failures)
        - 3 or more consecutive flush failures
        - Buffer is more than 90% full

        Returns:
            True if the client is healthy, False otherwise.

        Example:
            >>> if not client.is_healthy():
            ...     print("Warning: Ledger client is experiencing issues")
        """
        flusher_metrics = self._flusher.get_metrics()

        if flusher_metrics["circuit_breaker_open"]:
            return False

        if flusher_metrics["consecutive_failures"] >= 3:
            return False

        buffer_utilization = (self._buffer.size() / self._buffer.max_size) * 100
        if buffer_utilization > 90:
            return False

        return True

    def get_health_status(self) -> dict[str, Any]:
        """Get detailed health status information.

        Returns:
            Dictionary containing:
            - status (str): Overall status - "healthy", "degraded", or "unhealthy"
            - healthy (bool): True if status is "healthy"
            - issues (list[str] | None): List of current issues, or None if healthy
            - buffer_utilization_percent (float): Percentage of buffer in use
            - circuit_breaker_open (bool): Whether circuit breaker is active
            - consecutive_failures (int): Number of consecutive flush failures

        Example:
            >>> status = client.get_health_status()
            >>> if status["status"] != "healthy":
            ...     print(f"Issues: {status['issues']}")
        """
        flusher_metrics = self._flusher.get_metrics()
        buffer_utilization = (self._buffer.size() / self._buffer.max_size) * 100

        status = "healthy"
        issues = []

        if flusher_metrics["circuit_breaker_open"]:
            status = "unhealthy"
            issues.append("Circuit breaker is open (too many failures)")

        if flusher_metrics["consecutive_failures"] >= 3:
            status = "degraded" if status == "healthy" else status
            issues.append(f"Consecutive failures: {flusher_metrics['consecutive_failures']}")

        if buffer_utilization > 90:
            status = "degraded" if status == "healthy" else status
            issues.append(f"Buffer nearly full: {buffer_utilization:.1f}%")

        if self._buffer.get_dropped_count() > 0:
            status = "degraded" if status == "healthy" else status
            issues.append(f"Dropped logs: {self._buffer.get_dropped_count()}")

        return {
            "status": status,
            "healthy": status == "healthy",
            "issues": issues if issues else None,
            "buffer_utilization_percent": round(buffer_utilization, 2),
            "circuit_breaker_open": flusher_metrics["circuit_breaker_open"],
            "consecutive_failures": flusher_metrics["consecutive_failures"],
        }

    async def shutdown(self, timeout: float = 10.0) -> None:
        """Gracefully shut down the client and flush remaining logs.

        This method should be called before your application exits to ensure all
        buffered logs are sent to the server.

        Args:
            timeout: Maximum time in seconds to wait for pending logs to flush.
                Default is 10 seconds.

        Example:
            >>> await client.shutdown()
            >>> # Or with custom timeout:
            >>> await client.shutdown(timeout=30.0)
        """
        await self._flusher.shutdown(timeout=timeout)
        await self._http_client.close()

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics about SDK performance and status.

        Returns:
            Dictionary containing:
            - sdk: SDK version and uptime information
            - buffer: Current buffer size, capacity, and dropped logs
            - flusher: Flush statistics including successes, failures, and timing
            - rate_limiter: Current rate and limits
            - errors: Error counts by type

        Example:
            >>> metrics = client.get_metrics()
            >>> print(f"Uptime: {metrics['sdk']['uptime_seconds']}s")
            >>> print(f"Success rate: {metrics['flusher']['successful_flushes']} / {metrics['flusher']['total_flushes']}")
        """
        from ledger._version import __version__

        flusher_metrics = self._flusher.get_metrics()
        uptime = (datetime.now(timezone.utc) - self._sdk_start_time).total_seconds()

        return {
            "sdk": {
                "uptime_seconds": round(uptime, 2),
                "version": __version__,
            },
            "buffer": {
                "current_size": self._buffer.size(),
                "max_size": self._buffer.max_size,
                "total_dropped": self._buffer.get_dropped_count(),
                "utilization_percent": round(
                    (self._buffer.size() / self._buffer.max_size) * 100, 2
                ),
            },
            "flusher": {
                "total_flushes": flusher_metrics["total_flushes"],
                "successful_flushes": flusher_metrics["successful_flushes"],
                "failed_flushes": flusher_metrics["failed_flushes"],
                "total_logs_sent": flusher_metrics["total_logs_sent"],
                "total_logs_failed": flusher_metrics["total_logs_failed"],
                "consecutive_failures": flusher_metrics["consecutive_failures"],
                "circuit_breaker_open": flusher_metrics["circuit_breaker_open"],
                "last_flush_time": flusher_metrics["last_flush_time"],
                "last_error": flusher_metrics["last_error"],
            },
            "rate_limiter": {
                "current_rate": self._rate_limiter.get_current_rate(),
                "limit_per_minute": self._rate_limiter.limit_per_minute,
            },
            "errors": flusher_metrics["errors_by_type"],
        }
