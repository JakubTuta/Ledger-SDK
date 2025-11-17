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
        self.platform_version = platform_version or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

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
        await self._flusher.shutdown(timeout=timeout)
        await self._http_client.close()

    def get_metrics(self) -> dict[str, Any]:
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
