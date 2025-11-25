from typing import Any, Pattern

import ledger.core.client as client_module
import ledger.core.url_processor as url_processor_module


class BaseMiddleware:
    def __init__(
        self,
        ledger_client: "client_module.LedgerClient",
        exclude_paths: list[str] | None = None,
        capture_query_params: bool = True,
        normalize_paths: bool = True,
        filter_ignored_paths: bool = True,
        custom_ignored_paths: list[str] | None = None,
        custom_ignored_prefixes: list[str] | None = None,
        custom_ignored_extensions: list[str] | None = None,
        normalization_patterns: list[tuple[Pattern, str]] | None = None,
        template_style: str = "curly",
    ):
        self.ledger = ledger_client
        self.exclude_paths = exclude_paths or []
        self.capture_query_params = capture_query_params

        self.url_processor = url_processor_module.URLProcessor(
            normalize_paths=normalize_paths,
            filter_ignored_paths=filter_ignored_paths,
            custom_ignored_paths=custom_ignored_paths,
            custom_ignored_prefixes=custom_ignored_prefixes,
            custom_ignored_extensions=custom_ignored_extensions,
            normalization_patterns=normalization_patterns,
            template_style=template_style,
        )

    def should_exclude_path(self, path: str) -> bool:
        return path in self.exclude_paths

    def process_request_path(self, path: str) -> str | None:
        return self.url_processor.process_url(path)

    def log_request(
        self,
        request_info: dict[str, Any],
        status_code: int,
        duration_ms: float,
    ) -> None:
        if 200 <= status_code < 400:
            level = "info"
            importance = "standard"
        elif 400 <= status_code < 500:
            level = "warning"
            importance = "standard"
        else:
            level = "error"
            importance = "high"

        message = (
            f"{request_info['method']} {request_info['path']} - {status_code} ({duration_ms:.0f}ms)"
        )

        endpoint_data = {
            "method": request_info["method"],
            "path": request_info["path"],
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }

        if request_info.get("query_params"):
            endpoint_data["query_params"] = request_info["query_params"]

        self.ledger._log(
            level=level,
            log_type="endpoint",
            importance=importance,
            message=message,
            attributes={"endpoint": endpoint_data},
        )

    def log_exception(
        self,
        request_info: dict[str, Any],
        exception: Exception,
        duration_ms: float,
    ) -> None:
        message = f"{request_info['method']} {request_info['path']} - Exception: {exception!s}"

        exception_attributes = {
            "method": request_info["method"],
            "path": request_info["path"],
            "duration_ms": round(duration_ms, 2),
        }

        if request_info.get("query_params"):
            exception_attributes["query_params"] = request_info["query_params"]

        self.ledger.log_exception(
            exception=exception,
            message=message,
            attributes=exception_attributes,
        )
