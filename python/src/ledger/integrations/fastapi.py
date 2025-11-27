import time
from collections.abc import Callable
from typing import Pattern

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

import ledger.core.base_middleware as base_middleware_module
import ledger.core.client as client_module


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

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        if self.should_exclude_path(request.url.path):
            return await call_next(request)

        start_time = time.time()

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            route = request.scope.get("route")
            if route and hasattr(route, "path"):
                path = route.path
            else:
                path = self.process_request_path(request.url.path)
                if path is None:
                    return response

            request_info = {
                "method": request.method,
                "path": path,
            }

            if self.capture_query_params and request.url.query:
                request_info["query_params"] = str(request.url.query)

            self.log_request(request_info, response.status_code, duration_ms)
            return response
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000

            route = request.scope.get("route")
            if route and hasattr(route, "path"):
                path = route.path
            else:
                path = self.process_request_path(request.url.path)
                if path is None:
                    raise

            request_info = {
                "method": request.method,
                "path": path,
            }

            if self.capture_query_params and request.url.query:
                request_info["query_params"] = str(request.url.query)

            self.log_exception(request_info, exc, duration_ms)
            raise
