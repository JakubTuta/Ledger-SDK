import asyncio
import json
import os
import sys
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import opentelemetry._logs as logs_api
import opentelemetry.metrics as metrics_api
import opentelemetry.sdk._logs as sdk_logs
import opentelemetry.sdk._logs.export as logs_export
import opentelemetry.sdk.metrics as sdk_metrics
import opentelemetry.sdk.metrics.export as metrics_export
import opentelemetry.sdk.resources as resources_module
import opentelemetry.sdk.trace as sdk_trace
import opentelemetry.sdk.trace.export as trace_export
import opentelemetry.sdk.trace.sampling as sampling_module
import opentelemetry.trace as trace_api
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

import ledger._logging as logging_module
import ledger.core.config as config_module
import ledger.core.log_processor as log_processor_module
import ledger.core.scrubbers as scrubbers_module
import ledger.core.validator as validator_module
from ledger._version import __version__

_SEVERITY_BY_LEVEL: dict[str, tuple["logs_api.SeverityNumber", str]] = {
    "debug": (logs_api.SeverityNumber.DEBUG, "DEBUG"),
    "info": (logs_api.SeverityNumber.INFO, "INFO"),
    "warning": (logs_api.SeverityNumber.WARN, "WARN"),
    "error": (logs_api.SeverityNumber.ERROR, "ERROR"),
    "critical": (logs_api.SeverityNumber.FATAL, "FATAL"),
}


class LedgerClient:
    """Client for sending traces and logs to the Ledger observability platform.

    Ledger's Python SDK is a thin distribution of the official OpenTelemetry SDK:
    it wires up a TracerProvider and LoggerProvider that export via OTLP/HTTP to
    the Ledger server, while preserving Ledger-specific enhancements (exception
    stack traces, log-trace correlation, endpoint monitoring, attribute
    truncation) through a custom LogRecordProcessor and instrumentation
    middlewares.

    Example:
        >>> client = LedgerClient(api_key="ledger_your_api_key")
        >>> client.log_info("User logged in", {"user_id": "123"})
        >>> await client.shutdown()
    """

    tracer: "trace_api.Tracer | None" = None

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        flush_interval: float | None = None,
        flush_size: int | None = None,
        max_buffer_size: int | None = None,
        http_timeout: float | None = None,
        environment: str | None = None,
        release: str | None = None,
        platform_version: str | None = None,
        service_name: str | None = None,
        tracing_enabled: bool | None = None,
        trace_sample_rate: float | None = None,
        before_send: "Callable[[dict[str, Any]], dict[str, Any] | None] | None" = None,
        scrub_pii: bool = False,
    ):
        """Initialize the Ledger client.

        Args:
            api_key: Your Ledger API key (must start with 'ledger_').
            base_url: Base URL for the Ledger API. If not provided, uses the default
                production endpoint.
            flush_interval: How often (in seconds) to automatically export buffered
                spans and logs. Default is from config.
            flush_size: Maximum number of records to include in a single OTLP export
                batch. Default is from config.
            max_buffer_size: Maximum number of records to queue before old ones are
                dropped. Default is from config.
            http_timeout: Timeout in seconds for OTLP export requests. Default is
                from config.
            environment: Optional environment identifier (e.g., "production", "staging").
                Attached as resource attribute to all spans and logs.
            release: Optional release version identifier. Attached as resource attribute.
            platform_version: Python version string. Auto-detected if not provided.
            service_name: Service name attached to the OTel resource.
            tracing_enabled: Whether to create and export spans. Default is from config.
            trace_sample_rate: Head sample rate for tracing (0.0 to 1.0). Default is
                from config.
            before_send: Optional hook called with a dict shaped
                `{"body", "attributes", "severity_number", "severity_text"}` for every
                log record right before export. Return a (possibly mutated) dict to
                keep the record, or None to drop it entirely. If `scrub_pii` is also
                set, the built-in scrubbers run first and this hook runs second.
            scrub_pii: If True, wire up a default `before_send` built from the SDK's
                built-in PII scrubbers (email addresses, credit-card-like digit
                sequences, sensitive header/secret-shaped attribute keys). Composes
                with an explicit `before_send` if both are provided.

        Raises:
            ValueError: If configuration parameters are invalid (e.g., invalid API key,
                negative timeouts, invalid URLs).
        """
        config = config_module.DEFAULT_CONFIG

        base_url = base_url if base_url is not None else config.base_url
        flush_interval = flush_interval if flush_interval is not None else config.flush_interval
        flush_size = flush_size if flush_size is not None else config.flush_size
        max_buffer_size = max_buffer_size if max_buffer_size is not None else config.max_buffer_size
        http_timeout = http_timeout if http_timeout is not None else config.http_timeout
        resolved_service_name = service_name if service_name is not None else config.service_name
        resolved_tracing_enabled = (
            tracing_enabled if tracing_enabled is not None else config.tracing_enabled
        )
        resolved_trace_sample_rate = (
            trace_sample_rate if trace_sample_rate is not None else config.trace_sample_rate
        )

        self._validate_config(
            api_key=api_key,
            base_url=base_url,
            flush_interval=flush_interval,
            flush_size=flush_size,
            max_buffer_size=max_buffer_size,
            http_timeout=http_timeout,
        )

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.environment = environment
        self.release = release
        self.platform_version = (
            platform_version
            or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        self.tracing_enabled = resolved_tracing_enabled

        constraints = config_module.DEFAULT_CONSTRAINTS
        self._validator = validator_module.Validator(constraints)

        resource = self._build_resource(resolved_service_name)
        headers = {"Authorization": f"Bearer {self.api_key}"}

        otlp_endpoint_from_env = bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))
        otlp_headers_from_env = bool(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS"))

        self._tracer_provider: sdk_trace.TracerProvider | None = None

        if self.tracing_enabled:
            sampler = sampling_module.ParentBased(
                sampling_module.TraceIdRatioBased(resolved_trace_sample_rate)
            )
            self._tracer_provider = sdk_trace.TracerProvider(resource=resource, sampler=sampler)
            span_exporter = OTLPSpanExporter(
                endpoint=None if otlp_endpoint_from_env else f"{self.base_url}/v1/traces",
                headers=None if otlp_headers_from_env else headers,
                timeout=http_timeout,
                compression=Compression.Gzip,
            )
            self._tracer_provider.add_span_processor(
                trace_export.BatchSpanProcessor(
                    span_exporter,
                    max_queue_size=max_buffer_size,
                    schedule_delay_millis=flush_interval * 1000,
                    max_export_batch_size=flush_size,
                    export_timeout_millis=http_timeout * 1000,
                )
            )
            trace_api.set_tracer_provider(self._tracer_provider)
            self.tracer = trace_api.get_tracer("ledger-sdk-python", __version__)
        else:
            self.tracer = None

        self._logger_provider = sdk_logs.LoggerProvider(resource=resource)
        log_exporter = OTLPLogExporter(
            endpoint=None if otlp_endpoint_from_env else f"{self.base_url}/v1/logs",
            headers=None if otlp_headers_from_env else headers,
            timeout=http_timeout,
            compression=Compression.Gzip,
        )
        batch_log_processor = logs_export.BatchLogRecordProcessor(
            log_exporter,
            max_queue_size=max_buffer_size,
            schedule_delay_millis=flush_interval * 1000,
            max_export_batch_size=flush_size,
            export_timeout_millis=http_timeout * 1000,
        )
        self._logger_provider.add_log_record_processor(
            log_processor_module.LedgerLogRecordProcessor(
                self._validator,
                downstream=batch_log_processor,
                before_send=self._build_before_send(before_send, scrub_pii),
            )
        )
        logs_api.set_logger_provider(self._logger_provider)
        self._logger = logs_api.get_logger("ledger-sdk-python", __version__)

        metric_exporter = OTLPMetricExporter(
            endpoint=None if otlp_endpoint_from_env else f"{self.base_url}/v1/metrics",
            headers=None if otlp_headers_from_env else headers,
            timeout=http_timeout,
            compression=Compression.Gzip,
        )
        self._meter_provider = sdk_metrics.MeterProvider(
            resource=resource,
            metric_readers=[
                metrics_export.PeriodicExportingMetricReader(
                    metric_exporter,
                    export_interval_millis=flush_interval * 1000,
                    export_timeout_millis=http_timeout * 1000,
                )
            ],
        )
        metrics_api.set_meter_provider(self._meter_provider)
        self._meters: dict[str, metrics_api.Meter] = {}
        self._counters: dict[str, metrics_api.Counter] = {}
        self._gauges: dict[str, metrics_api.ObservableGauge | metrics_api.Gauge] = {}
        self._histograms: dict[str, metrics_api.Histogram] = {}

        self._http_timeout = http_timeout
        self._sdk_start_time = datetime.now(timezone.utc)
        self._shutdown = False

        self._uncaught_capture_installed = False
        self._previous_excepthook: (
            Callable[[type[BaseException], BaseException, Any], None] | None
        ) = None
        self._previous_threading_excepthook: Callable[[Any], None] | None = None
        self._previous_new_event_loop: Callable[..., asyncio.AbstractEventLoop] | None = None

    def _build_before_send(
        self,
        before_send: "Callable[[dict[str, Any]], dict[str, Any] | None] | None",
        scrub_pii: bool,
    ) -> "Callable[[dict[str, Any]], dict[str, Any] | None] | None":
        if not scrub_pii:
            return before_send

        pii_scrubber = scrubbers_module.build_pii_scrubber()
        if before_send is None:
            return pii_scrubber

        def _combined(record: dict[str, Any]) -> dict[str, Any] | None:
            scrubbed = pii_scrubber(record)
            if scrubbed is None:
                return None
            return before_send(scrubbed)

        return _combined

    def _build_resource(self, service_name: str) -> "resources_module.Resource":
        attributes: dict[str, Any] = {
            "service.name": service_name,
            "telemetry.sdk.language": "python",
            "ledger.platform_version": self.platform_version,
            "ledger.sdk_version": __version__,
        }

        if self.environment:
            attributes["deployment.environment.name"] = self._validator.truncate_environment(
                self.environment
            )

        if self.release:
            attributes["service.version"] = self._validator.truncate_release(self.release)

        return resources_module.Resource.create(attributes)

    def _validate_config(
        self,
        api_key: str,
        base_url: str,
        flush_interval: float,
        flush_size: int,
        max_buffer_size: int,
        http_timeout: float,
    ) -> None:
        errors = []

        if not api_key or not isinstance(api_key, str):
            errors.append("api_key must be a non-empty string")
        elif not api_key.startswith("ledger_"):
            errors.append("api_key must start with 'ledger_' prefix")

        if not base_url or not isinstance(base_url, str):
            errors.append("base_url must be a non-empty string")
        elif not base_url.startswith(("http://", "https://")):
            errors.append("base_url must start with 'http://' or 'https://'")

        if flush_interval <= 0:
            errors.append(f"flush_interval must be positive, got {flush_interval}")

        if flush_size <= 0:
            errors.append(f"flush_size must be positive, got {flush_size}")

        if max_buffer_size <= 0:
            errors.append(f"max_buffer_size must be positive, got {max_buffer_size}")

        if http_timeout <= 0:
            errors.append(f"http_timeout must be positive, got {http_timeout}")

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

    def log_warning(
        self,
        message: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Log a warning message.

        Args:
            message: The warning message to record.
            attributes: Optional dictionary of custom attributes to attach to the log.
                Can contain any JSON-serializable values.

        Example:
            >>> client.log_warning("Cache miss rate high", {"rate": 0.85})
        """
        self._log(
            level="warning",
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

        Automatically captures the exception type, message, and full stack trace
        as `exception.type` / `exception.message` / `exception.stacktrace` attributes.

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
        self._log(
            level="error",
            log_type="exception",
            importance="high",
            message=message or str(exception),
            attributes=attributes,
            exception=exception,
        )

    def log_endpoint(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        query_params: str | None = None,
        path_params: dict[str, Any] | None = None,
        response_body: str | None = None,
    ) -> None:
        """Log an HTTP endpoint invocation.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: Request path, optionally normalized.
            status_code: HTTP response status code.
            duration_ms: Request duration in milliseconds.
            query_params: Optional raw query string.
            path_params: Optional dict of path parameter names to their values.
            response_body: Optional response body preview for error responses (4 KB cap).

        Example:
            >>> client.log_endpoint("GET", "/users/{id}", 200, 12.5, path_params={"id": "123"})
        """
        if 200 <= status_code < 400:
            level = "info"
            importance = "standard"
        elif 400 <= status_code < 500:
            level = "warning"
            importance = "standard"
        else:
            level = "error"
            importance = "high"

        message = f"{method} {path} - {status_code} ({duration_ms:.0f}ms)"

        attributes: dict[str, Any] = {
            "http.request.method": method,
            "http.route": path,
            "http.response.status_code": status_code,
            "ledger.duration_ms": round(duration_ms, 2),
        }

        if query_params:
            attributes["url.query"] = query_params

        if path_params:
            attributes["ledger.path_params"] = json.dumps(path_params)

        if response_body:
            attributes["ledger.response_body"] = response_body

        self._log(
            level=level,
            log_type="endpoint",
            importance=importance,
            message=message,
            attributes=attributes,
        )

    def _log(
        self,
        level: str,
        log_type: str,
        importance: str,
        message: str | None = None,
        attributes: dict[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> None:
        severity_number, severity_text = _SEVERITY_BY_LEVEL[level]

        merged_attributes: dict[str, Any] = (
            self._validator.validate_attributes(dict(attributes)) if attributes else {}
        )
        merged_attributes["ledger.log_type"] = log_type
        merged_attributes["ledger.importance"] = importance

        current_span = trace_api.get_current_span()
        span_context = current_span.get_span_context()
        if span_context.is_valid:
            merged_attributes["trace_id"] = format(span_context.trace_id, "032x")
            merged_attributes["span_id"] = format(span_context.span_id, "016x")

        self._logger.emit(
            severity_number=severity_number,
            severity_text=severity_text,
            body=message,
            attributes=merged_attributes,
            exception=exception,
        )

    def is_healthy(self) -> bool:
        """Check if the client is operating normally.

        Returns:
            True if the client's providers have not been shut down.

        Example:
            >>> if not client.is_healthy():
            ...     print("Warning: Ledger client has been shut down")
        """
        return not self._shutdown

    def get_health_status(self) -> dict[str, Any]:
        """Get health status information.

        Returns:
            Dictionary containing:
            - status (str): Overall status - "healthy" or "shutdown"
            - healthy (bool): True if status is "healthy"

        Example:
            >>> status = client.get_health_status()
            >>> print(status["status"])
        """
        healthy = self.is_healthy()
        return {
            "status": "healthy" if healthy else "shutdown",
            "healthy": healthy,
        }

    def get_metrics(self) -> dict[str, Any]:
        """Get SDK version and uptime information.

        Detailed export queue/failure counters are not exposed by the underlying
        OpenTelemetry SDK; use OTel's own diagnostic logging (`OTEL_PYTHON_LOG_LEVEL`)
        for export-level troubleshooting.

        Returns:
            Dictionary containing sdk version and uptime information.

        Example:
            >>> metrics = client.get_metrics()
            >>> print(f"Uptime: {metrics['sdk']['uptime_seconds']}s")
        """
        uptime = (datetime.now(timezone.utc) - self._sdk_start_time).total_seconds()

        return {
            "sdk": {
                "uptime_seconds": round(uptime, 2),
                "version": __version__,
            }
        }

    def instrument_logging(self, level: int | None = None) -> None:
        """Bridge the Python standard library `logging` module into Ledger.

        Attaches an OpenTelemetry logging handler to the root logger so that
        any `logging.getLogger(...)` call in your application (or in
        third-party libraries) is exported to Ledger alongside SDK-native logs.

        Args:
            level: Minimum stdlib logging level to forward. Defaults to the root
                logger's own effective level.

        Example:
            >>> client.instrument_logging()
            >>> import logging
            >>> logging.getLogger(__name__).warning("this reaches Ledger too")
        """
        import logging as stdlib_logging

        import opentelemetry.instrumentation.logging as otel_logging_instrumentation

        instrumentor = otel_logging_instrumentation.LoggingInstrumentor()
        instrumentor.instrument(
            logger_provider=self._logger_provider,
            set_logging_format=False,
        )

        if level is not None:
            stdlib_logging.getLogger().setLevel(level)

    def capture_uncaught(self) -> None:
        """Automatically log uncaught exceptions from any thread or event loop.

        Installs three global hooks, each chaining to whatever was previously
        installed (e.g. an IDE debugger, or a hook set by another library) so
        nothing else that depends on the previous hook stops working:

        - `sys.excepthook` -- uncaught exceptions on the main thread.
        - `threading.excepthook` -- uncaught exceptions on background threads.
          The thread name is attached as the `thread.name` attribute.
        - asyncio's exception handler -- exceptions raised inside tasks that
          are never awaited/collected.

        Every captured exception is logged through the same code path as
        `log_exception()`, with `ledger.uncaught=True` added so these can be
        told apart from exceptions your own code logs deliberately.

        This method is idempotent: calling it more than once is a no-op after
        the first call, so it's safe to call from library code without
        double-chaining the same hooks.

        Asyncio caveat: an event loop's exception handler is a per-loop
        setting, not a process-global one. If a loop is already running when
        you call this method, its handler is installed immediately. For loops
        created later (including the implicit loop behind `asyncio.run()`),
        this method also wraps the active event loop policy's
        `new_event_loop`, so every subsequently created loop is covered
        automatically. A loop created *before* `capture_uncaught()` runs, and
        never re-created afterward, is not covered -- call
        `capture_uncaught()` as early as possible, ideally right after
        constructing the client.

        Example:
            >>> client = LedgerClient(api_key="ledger_your_api_key")
            >>> client.capture_uncaught()
            >>> raise RuntimeError("boom")  # now reported to Ledger automatically
        """
        if self._uncaught_capture_installed:
            return
        self._uncaught_capture_installed = True

        self._previous_excepthook = sys.excepthook

        def _excepthook(
            exc_type: type[BaseException], exc_value: BaseException, exc_traceback: Any
        ) -> None:
            try:
                self.log_exception(
                    exc_value,  # type: ignore[arg-type]
                    message=f"Uncaught exception: {exc_type.__name__}",
                    attributes={"ledger.uncaught": True},
                )
            except Exception:
                logging_module.get_logger().exception(
                    "ledger-sdk: failed to log uncaught exception via capture_uncaught()"
                )
            finally:
                previous_excepthook = self._previous_excepthook
                if previous_excepthook is not None:
                    previous_excepthook(exc_type, exc_value, exc_traceback)

        sys.excepthook = _excepthook

        self._previous_threading_excepthook = threading.excepthook

        def _threading_excepthook(args: Any) -> None:
            thread_name = (
                args.thread.name if getattr(args, "thread", None) is not None else "unknown"
            )
            exc_type = args.exc_type
            exc_value = args.exc_value
            try:
                self.log_exception(
                    exc_value,  # type: ignore[arg-type]
                    message=(
                        f"Uncaught exception in thread '{thread_name}': "
                        f"{exc_type.__name__ if exc_type is not None else 'Unknown'}"
                    ),
                    attributes={"ledger.uncaught": True, "thread.name": thread_name},
                )
            except Exception:
                logging_module.get_logger().exception(
                    "ledger-sdk: failed to log uncaught thread exception via capture_uncaught()"
                )
            finally:
                previous_threading_excepthook = self._previous_threading_excepthook
                if previous_threading_excepthook is not None:
                    previous_threading_excepthook(args)

        threading.excepthook = _threading_excepthook

        def _install_asyncio_handler(loop: "asyncio.AbstractEventLoop") -> None:
            previous_handler = loop.get_exception_handler()

            def _asyncio_exception_handler(
                loop: "asyncio.AbstractEventLoop", context: dict[str, Any]
            ) -> None:
                try:
                    exception = context.get("exception")
                    if isinstance(exception, BaseException):
                        self.log_exception(
                            exception,  # type: ignore[arg-type]
                            message=context.get("message")
                            or f"Uncaught exception in asyncio task: {type(exception).__name__}",
                            attributes={"ledger.uncaught": True},
                        )
                    else:
                        self.log_error(
                            context.get("message", "Unhandled error in asyncio event loop"),
                            attributes={"ledger.uncaught": True},
                        )
                except Exception:
                    logging_module.get_logger().exception(
                        "ledger-sdk: failed to log uncaught asyncio exception via "
                        "capture_uncaught()"
                    )
                finally:
                    if previous_handler is not None:
                        previous_handler(loop, context)
                    else:
                        loop.default_exception_handler(context)

            loop.set_exception_handler(_asyncio_exception_handler)

        try:
            running_loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is not None:
            _install_asyncio_handler(running_loop)

        policy = asyncio.get_event_loop_policy()
        self._previous_new_event_loop = policy.new_event_loop

        def _patched_new_event_loop(*args: Any, **kwargs: Any) -> "asyncio.AbstractEventLoop":
            previous_new_event_loop = self._previous_new_event_loop
            assert previous_new_event_loop is not None
            loop = previous_new_event_loop(*args, **kwargs)
            _install_asyncio_handler(loop)
            return loop

        policy.new_event_loop = _patched_new_event_loop

    def get_meter(self, name: str = "ledger-sdk-python") -> "metrics_api.Meter":
        """Get a standard OpenTelemetry Meter exporting to Ledger.

        Use this for full control over counters, gauges, and histograms via
        the standard OTel metrics API. For quick one-off calls, prefer
        metric_increment/metric_gauge/metric_histogram below.

        Example:
            >>> meter = client.get_meter("my-service")
            >>> requests_counter = meter.create_counter("requests")
            >>> requests_counter.add(1, {"route": "/health"})
        """
        if name not in self._meters:
            self._meters[name] = metrics_api.get_meter(name, __version__)
        return self._meters[name]

    def metric_increment(
        self, name: str, value: int | float = 1, tags: dict[str, str] | None = None
    ) -> None:
        """Increment a counter metric by `value` (default 1).

        Example:
            >>> client.metric_increment("orders_processed", tags={"region": "eu"})
        """
        if name not in self._counters:
            self._counters[name] = self.get_meter().create_counter(name)
        self._counters[name].add(value, attributes=tags or {})

    def metric_gauge(
        self, name: str, value: int | float, tags: dict[str, str] | None = None
    ) -> None:
        """Record the current value of a gauge metric.

        Example:
            >>> client.metric_gauge("queue_depth", 42, tags={"queue": "emails"})
        """
        if name not in self._gauges:
            self._gauges[name] = self.get_meter().create_gauge(name)
        self._gauges[name].set(value, attributes=tags or {})

    def metric_histogram(
        self, name: str, value: int | float, tags: dict[str, str] | None = None
    ) -> None:
        """Record an observation into a histogram metric.

        Example:
            >>> client.metric_histogram("request_duration_ms", 123.4, tags={"route": "/api"})
        """
        if name not in self._histograms:
            self._histograms[name] = self.get_meter().create_histogram(name)
        self._histograms[name].record(value, attributes=tags or {})

    def heartbeat(self, token: str, timeout: float | None = None) -> None:
        """Ping a Ledger heartbeat (dead-man's-switch) monitor.

        Call this on a schedule from the job/service being monitored. If the
        server doesn't see a ping within the monitor's configured interval +
        grace period, it fires an alert. This is a plain, synchronous HTTP
        call (no OTel pipeline involved) so it's safe to call from cron jobs
        or short-lived scripts that won't stick around for a batch flush.

        Args:
            token: The monitor's ping token (from the Ledger dashboard).
            timeout: Request timeout in seconds. Defaults to the client's
                configured http_timeout.

        Example:
            >>> client.heartbeat("abc123...")
        """
        import urllib.error
        import urllib.request

        url = f"{self.base_url}/api/v1/monitors/{token}/ping"
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"base_url must be http(s), got: {self.base_url}")
        request = urllib.request.Request(url, method="POST")  # noqa: S310
        try:
            urllib.request.urlopen(request, timeout=timeout or self._http_timeout)  # noqa: S310
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Heartbeat ping failed: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Heartbeat ping failed: {e.reason}") from e

    async def shutdown(self, timeout: float = 10.0) -> None:
        """Gracefully shut down the client and flush remaining spans and logs.

        This method should be called before your application exits to ensure all
        buffered spans and logs are exported to the server. For sync applications
        use shutdown_sync().

        Args:
            timeout: Maximum time in seconds to wait for pending exports to flush.
                Default is 10 seconds.

        Example:
            >>> await client.shutdown()
            >>> # Or with custom timeout:
            >>> await client.shutdown(timeout=30.0)
        """
        await asyncio.get_running_loop().run_in_executor(None, self.shutdown_sync, timeout)

    def shutdown_sync(self, timeout: float = 10.0) -> None:
        """Gracefully shut down the client from synchronous code (Flask, Django).

        Use this instead of shutdown() in sync contexts such as atexit handlers.

        Args:
            timeout: Maximum time in seconds to wait for pending exports to flush.
                Default is 10 seconds.

        Example:
            >>> import atexit
            >>> atexit.register(client.shutdown_sync)
        """
        timeout_millis = int(timeout * 1000)

        if self._tracer_provider is not None:
            self._tracer_provider.force_flush(timeout_millis=timeout_millis)
            self._tracer_provider.shutdown()

        self._logger_provider.force_flush(timeout_millis=timeout_millis)
        self._logger_provider.shutdown()

        self._meter_provider.force_flush(timeout_millis=timeout_millis)
        self._meter_provider.shutdown()
        self._shutdown = True
