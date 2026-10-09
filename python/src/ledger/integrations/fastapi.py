import time
from re import Pattern
from typing import Any

import opentelemetry.trace as trace_api
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import ledger.core.base_middleware as base_middleware_module
import ledger.core.client as client_module
import ledger.integrations.common as common_module

# One byte past the preview size, so _body_preview can tell a body that was
# truncated from one that was exactly the preview size.
_ERROR_BODY_CAPTURE_BYTES: int = base_middleware_module._MAX_ERROR_RESPONSE_BODY_BYTES + 1


class _ResponseObserver:
    """Status, time to response start and an error-body preview, read off ASGI send.

    Only a bounded prefix of an error body is copied; every message is passed
    through unchanged, so streaming responses keep streaming and large error
    bodies are never buffered.
    """

    def __init__(self, start: float) -> None:
        self._start = start
        self.status_code: int | None = None
        self.duration_ms: float | None = None
        self._error_body = bytearray()

    def observe(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
            self.duration_ms = (time.perf_counter() - self._start) * 1000
        elif (
            message["type"] == "http.response.body"
            and self.status_code is not None
            and self.status_code >= 400
            and len(self._error_body) < _ERROR_BODY_CAPTURE_BYTES
        ):
            room = _ERROR_BODY_CAPTURE_BYTES - len(self._error_body)
            self._error_body += message.get("body", b"")[:room]

    def error_body_preview(self) -> str | None:
        if self.status_code is None or self.status_code < 400:
            return None
        return base_middleware_module._body_preview(bytes(self._error_body))


class LedgerMiddleware(base_middleware_module.BaseMiddleware):
    """Pure ASGI middleware: one span and one endpoint log per request.

    Not a BaseHTTPMiddleware subclass - that wrapper adds a task, a queue and a
    response re-wrap per request (about 150 us measured with an empty
    dispatch), and buffered whole error responses to read a 4 KB preview.
    """

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
        allowed_path_prefixes: list[str] | None = None,
        only_registered_routes: bool = True,
        capture_client_info: bool = True,
        trusted_proxies: list[str] | None = None,
    ):
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
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if self.should_exclude_path(request.url.path):
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        headers = dict(request.headers)
        client_ip = request.client.host if request.client else None
        caller = self.describe_caller(headers, client_ip)
        response = _ResponseObserver(start)

        async def observing_send(message: Message) -> None:
            response.observe(message)
            await send(message)

        with common_module.http_server_span(
            method=request.method,
            route=request.url.path,
            url=str(request.url),
            headers=headers,
            client_ip=client_ip,
            user_agent=headers.get("user-agent"),
        ) as span:
            try:
                await self.app(scope, receive, observing_send)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(trace_api.StatusCode.ERROR)
                path = self._resolve_path(request)
                if path is not None:
                    self._name_span(span, request.method, path)
                    duration_ms = response.duration_ms or (time.perf_counter() - start) * 1000
                    self.log_exception(self._request_info(request, path, caller), exc, duration_ms)
                raise

            if response.status_code is None:
                return

            path = self._resolve_path(request)
            if path is not None:
                self._name_span(span, request.method, path)
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(trace_api.StatusCode.ERROR)

            if path is not None:
                self.log_request(
                    self._request_info(request, path, caller),
                    response.status_code,
                    response.duration_ms or 0.0,
                    response.error_body_preview(),
                )

    def _resolve_path(self, request: Request) -> str | None:
        # The router stores the matched route in the shared scope while
        # handling the request, so it is only known once the app has run.
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            return route.path
        if self.only_registered_routes:
            return None
        return self.process_request_path(request.url.path)

    @staticmethod
    def _name_span(span: trace_api.Span, method: str, path: str) -> None:
        span.update_name(f"{method} {path}")
        span.set_attribute("http.route", path)

    def _request_info(
        self, request: Request, path: str, caller: dict[str, Any] | None
    ) -> dict[str, Any]:
        return self._build_request_info(
            method=request.method,
            path=path,
            query_params=(
                str(request.url.query) if self.capture_query_params and request.url.query else None
            ),
            path_params=dict(request.path_params) if request.path_params else None,
            caller=caller,
        )
