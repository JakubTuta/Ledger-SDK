from collections.abc import Mapping
from re import Pattern
from typing import Any

import ledger.core.caller as caller_module
import ledger.core.client as client_module
import ledger.core.url_processor as url_processor_module

_MAX_ERROR_RESPONSE_BODY_BYTES: int = 4096


def _body_preview(body: bytes) -> str:
    preview = body[:_MAX_ERROR_RESPONSE_BODY_BYTES].decode("utf-8", errors="replace")
    if len(body) > _MAX_ERROR_RESPONSE_BODY_BYTES:
        preview += " ...[truncated]"
    return preview


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
        allowed_path_prefixes: list[str] | None = None,
        only_registered_routes: bool = True,
        capture_client_info: bool = True,
        trusted_proxies: list[str] | None = None,
    ):
        """See framework-specific `LedgerMiddleware` subclasses for the full
        parameter list. Two are documented here since they're shared and
        privacy-sensitive:

        Args:
            capture_client_info: Whether to derive and attach caller metadata
                (channel, truncated IP prefix, User-Agent breakdown) to
                endpoint logs. Set False to disable entirely.
            trusted_proxies: List of IP networks (e.g. `["10.0.0.0/8"]`) whose
                `X-Forwarded-For` header is trusted. Unset (the default) means
                only the direct TCP peer address is ever used -- headers are
                never trusted, so a reverse proxy's address is recorded
                instead of the visitor's. Never set this to `["0.0.0.0/0"]`:
                that trusts every hop, including attacker-controlled ones,
                which defeats the point of the walk. Set it to the address
                range your app actually receives connections from.
        """
        self.ledger = ledger_client
        self.exclude_paths: set[str] = set(exclude_paths or [])
        self.capture_query_params = capture_query_params
        self.only_registered_routes = only_registered_routes
        self.capture_client_info = capture_client_info
        self._trusted_networks = caller_module.parse_trusted_proxies(trusted_proxies)

        self.url_processor = url_processor_module.URLProcessor(
            normalize_paths=normalize_paths,
            filter_ignored_paths=filter_ignored_paths,
            custom_ignored_paths=custom_ignored_paths,
            custom_ignored_prefixes=custom_ignored_prefixes,
            custom_ignored_extensions=custom_ignored_extensions,
            normalization_patterns=normalization_patterns,
            template_style=template_style,
            allowed_path_prefixes=allowed_path_prefixes,
        )

    def should_exclude_path(self, path: str) -> bool:
        return path in self.exclude_paths

    def process_request_path(self, path: str) -> str | None:
        return self.url_processor.process_url(path)

    def describe_caller(
        self, headers: Mapping[str, Any], socket_ip: str | None
    ) -> dict[str, Any] | None:
        if not self.capture_client_info:
            return None
        return caller_module.describe(headers, socket_ip, self._trusted_networks)

    @staticmethod
    def _build_request_info(
        method: str,
        path: str,
        query_params: str | None,
        path_params: dict[str, Any] | None,
        caller: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_info: dict[str, Any] = {"method": method, "path": path}
        if query_params:
            request_info["query_params"] = query_params
        if path_params:
            request_info["path_params"] = path_params
        if caller:
            request_info["caller"] = caller
        return request_info

    def log_request(
        self,
        request_info: dict[str, Any],
        status_code: int,
        duration_ms: float,
        response_body: str | None = None,
    ) -> None:
        self.ledger.log_endpoint(
            method=request_info["method"],
            path=request_info["path"],
            status_code=status_code,
            duration_ms=duration_ms,
            query_params=request_info.get("query_params"),
            path_params=request_info.get("path_params"),
            response_body=response_body,
            caller=request_info.get("caller"),
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

        caller = request_info.get("caller")
        if caller:
            exception_attributes.update(caller)

        self.ledger.log_exception(
            exception=exception,
            message=message,
            attributes=exception_attributes,
        )
