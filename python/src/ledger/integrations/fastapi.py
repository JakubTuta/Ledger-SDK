import time
from collections.abc import Callable
from re import Pattern

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

import ledger.core.base_middleware as base_middleware_module
import ledger.core.client as client_module
import ledger.integrations.common as common_module
import ledger.tracing.span as span_module


class LedgerMiddleware(BaseHTTPMiddleware, base_middleware_module.BaseMiddleware):
    def __init__(
        self,
        app: ASGIApp,
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
        BaseHTTPMiddleware.__init__(self, app)
        base_middleware_module.BaseMiddleware.__init__(
            self,
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
        )

    def _resolve_path(self, request: Request) -> str | None:
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            return route.path
        return self.process_request_path(request.url.path)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        if self.should_exclude_path(request.url.path):
            return await call_next(request)

        start_time = time.time()
        tracer = self.ledger.tracer

        if tracer is None:
            return await self._dispatch_no_tracing(request, call_next, start_time)

        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        with common_module.http_server_span(
            tracer=tracer,
            method=request.method,
            route=request.url.path,
            url=str(request.url),
            headers=dict(request.headers),
            client_ip=client_ip,
            user_agent=user_agent,
        ) as span:
            try:
                response = await call_next(request)
                duration_ms = (time.time() - start_time) * 1000

                path = self._resolve_path(request)
                if path is not None:
                    span.name = f"{request.method} {path}"
                    span.set_attr("http.route", path)

                span.set_attr("http.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status(span_module.SpanStatus.ERROR)

                if path is not None:
                    request_info = {"method": request.method, "path": path}
                    if self.capture_query_params and request.url.query:
                        request_info["query_params"] = str(request.url.query)
                    if request.path_params:
                        request_info["path_params"] = dict(request.path_params)  # type: ignore[assignment]
                    self.log_request(request_info, response.status_code, duration_ms)

                return response
            except Exception as exc:
                duration_ms = (time.time() - start_time) * 1000
                span.record_exception(exc)
                span.set_status(span_module.SpanStatus.ERROR)

                path = self._resolve_path(request)
                if path is not None:
                    span.name = f"{request.method} {path}"
                    span.set_attr("http.route", path)
                    request_info = {"method": request.method, "path": path}
                    if self.capture_query_params and request.url.query:
                        request_info["query_params"] = str(request.url.query)
                    if request.path_params:
                        request_info["path_params"] = dict(request.path_params)  # type: ignore[assignment]
                    self.log_exception(request_info, exc, duration_ms)
                raise

    async def _dispatch_no_tracing(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
        start_time: float,
    ) -> Response:
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            path = self._resolve_path(request)
            if path is None:
                return response

            request_info = {"method": request.method, "path": path}
            if self.capture_query_params and request.url.query:
                request_info["query_params"] = str(request.url.query)
            if request.path_params:
                request_info["path_params"] = dict(request.path_params)  # type: ignore[assignment]

            self.log_request(request_info, response.status_code, duration_ms)
            return response
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000

            path = self._resolve_path(request)
            if path is None:
                raise

            request_info = {"method": request.method, "path": path}
            if self.capture_query_params and request.url.query:
                request_info["query_params"] = str(request.url.query)
            if request.path_params:
                request_info["path_params"] = dict(request.path_params)  # type: ignore[assignment]

            self.log_exception(request_info, exc, duration_ms)
            raise
