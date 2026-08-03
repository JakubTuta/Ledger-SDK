import re
import time
from collections.abc import Callable
from re import Pattern
from typing import Any

import opentelemetry.trace as trace_api

import ledger.core.base_middleware as base_middleware_module
import ledger.core.client as client_module
import ledger.integrations.common as common_module


class LedgerMiddleware(base_middleware_module.BaseMiddleware):
    sync_capable = True
    async_capable = True

    def __init__(
        self,
        get_response: Callable[[Any], Any],
        ledger_client: "client_module.LedgerClient | None" = None,
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
        if ledger_client is None:
            from django.conf import settings

            ledger_client = getattr(settings, "LEDGER_CLIENT", None)
            if ledger_client is None:
                ledger_client = getattr(settings, "ledger", None)
            if ledger_client is None:
                raise ValueError(
                    "LedgerClient not found. Set settings.LEDGER_CLIENT or settings.ledger, "
                    "or pass ledger_client parameter to middleware."
                )

        super().__init__(
            ledger_client=ledger_client,
            exclude_paths=exclude_paths,
            capture_query_params=capture_query_params,
            normalize_paths=normalize_paths,
            filter_ignored_paths=filter_ignored_paths,
            custom_ignored_paths=custom_ignored_paths,
            custom_ignored_prefixes=custom_ignored_prefixes,
            custom_ignored_extensions=custom_ignored_extensions,
            normalization_patterns=normalization_patterns,
            template_style=template_style,
            allowed_path_prefixes=allowed_path_prefixes,
            only_registered_routes=only_registered_routes,
            capture_client_info=capture_client_info,
            trusted_proxies=trusted_proxies,
        )
        self.get_response = get_response

        try:
            from asgiref.sync import iscoroutinefunction

            self._is_async = iscoroutinefunction(get_response)
        except ImportError:
            self._is_async = False

    def __call__(self, request: Any) -> Any:
        if self._is_async:
            return self.__acall__(request)
        return self._sync_call(request)

    def _sync_call(self, request: Any) -> Any:
        if self.should_exclude_path(request.path):
            return self.get_response(request)

        start_time = time.time()
        with self._start_request_span(request) as span:
            try:
                response = self.get_response(request)
                return self._finalize_response(request, response, span, start_time)
            except Exception as exc:
                self._finalize_exception(request, exc, span, start_time)
                raise

    async def __acall__(self, request: Any) -> Any:
        if self.should_exclude_path(request.path):
            return await self.get_response(request)

        start_time = time.time()
        with self._start_request_span(request) as span:
            try:
                response = await self.get_response(request)
                return self._finalize_response(request, response, span, start_time)
            except Exception as exc:
                self._finalize_exception(request, exc, span, start_time)
                raise

    def _start_request_span(self, request: Any) -> Any:
        headers = common_module.django_meta_to_headers(request.META)
        client_ip = request.META.get("REMOTE_ADDR")
        url = (
            request.build_absolute_uri() if hasattr(request, "build_absolute_uri") else request.path
        )
        request._ledger_caller = self.describe_caller(headers, client_ip)
        return common_module.http_server_span(
            method=request.method,
            route=request.path,
            url=url,
            headers=headers,
            client_ip=client_ip,
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )

    def _finalize_response(
        self, request: Any, response: Any, span: "trace_api.Span", start_time: float
    ) -> Any:
        duration_ms = (time.time() - start_time) * 1000

        path = self._get_path(request)
        if path is not None:
            span.update_name(f"{request.method} {path}")
            span.set_attribute("http.route", path)

        span.set_attribute("http.response.status_code", response.status_code)
        if response.status_code >= 500:
            span.set_status(trace_api.StatusCode.ERROR)

        if path is not None:
            request_info = self._build_request_info(
                method=request.method,
                path=path,
                query_params=(
                    request.META.get("QUERY_STRING") if self.capture_query_params else None
                ),
                path_params=self._get_path_params(request),
                caller=getattr(request, "_ledger_caller", None),
            )

            response_body: str | None = None
            if response.status_code >= 400:
                response_body = base_middleware_module._body_preview(response.content)

            self.log_request(request_info, response.status_code, duration_ms, response_body)

        return response

    def _finalize_exception(
        self, request: Any, exc: Exception, span: "trace_api.Span", start_time: float
    ) -> None:
        duration_ms = (time.time() - start_time) * 1000
        span.record_exception(exc)
        span.set_status(trace_api.StatusCode.ERROR)

        path = self._get_path(request)
        if path is not None:
            span.update_name(f"{request.method} {path}")
            span.set_attribute("http.route", path)
            request_info = self._build_request_info(
                method=request.method,
                path=path,
                query_params=(
                    request.META.get("QUERY_STRING") if self.capture_query_params else None
                ),
                path_params=self._get_path_params(request),
                caller=getattr(request, "_ledger_caller", None),
            )
            self.log_exception(request_info, exc, duration_ms)

    def _get_path(self, request: Any) -> str | None:
        if hasattr(request, "resolver_match") and request.resolver_match:
            route = request.resolver_match.route
            if route:
                return self._normalize_django_path(route)

        if self.only_registered_routes:
            return None

        return self.process_request_path(request.path)

    def _get_path_params(self, request: Any) -> dict[str, Any] | None:
        if hasattr(request, "resolver_match") and request.resolver_match:
            kwargs = getattr(request.resolver_match, "kwargs", None)
            if kwargs:
                return {k: str(v) for k, v in kwargs.items()}
        return None

    def _normalize_django_path(self, path: str) -> str:
        normalized = re.sub(
            r"<(?:(?P<converter>[^:>]+):)?(?P<parameter>[^>]+)>", r"{\g<parameter>}", path
        )
        return normalized
