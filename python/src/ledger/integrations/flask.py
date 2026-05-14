import re
import time
from contextvars import Token
from re import Pattern
from typing import Any

from flask import Flask, g, got_request_exception, request

import ledger.core.base_middleware as base_middleware_module
import ledger.core.client as client_module
import ledger.integrations.common as common_module
import ledger.tracing.span as span_module
import ledger.tracing.tracer as tracer_module


class LedgerMiddleware(base_middleware_module.BaseMiddleware):
    def __init__(
        self,
        app: Flask,
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
    ):
        if ledger_client is None:
            ledger_client = app.config.get("LEDGER_CLIENT")
            if ledger_client is None:
                ledger_client = app.config.get("ledger")
            if ledger_client is None:
                raise ValueError(
                    "LedgerClient not found. Set app.config['LEDGER_CLIENT'] or app.config['ledger'], "
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
        )

        self.normalize_paths = normalize_paths

        app.before_request(self._before_request)
        app.after_request(self._after_request)
        got_request_exception.connect(self._on_exception, app)

    def _before_request(self) -> None:
        if self.should_exclude_path(request.path):
            return

        g.ledger_start_time = time.time()

        tracer = self.ledger.tracer
        if tracer is None:
            return

        import ledger.tracing.propagation as propagation_module

        headers = common_module.django_meta_to_headers(request.environ)
        client_ip = request.environ.get("REMOTE_ADDR")
        user_agent = request.headers.get("User-Agent")
        context = propagation_module.extract(headers)

        span = tracer.start_span(
            f"{request.method} {request.path}",
            kind=span_module.SpanKind.SERVER,
            parent=context,
        )
        span.set_attr("http.method", request.method)
        span.set_attr("http.url", request.url)
        if client_ip is not None:
            span.set_attr("http.client_ip", client_ip)
        if user_agent is not None:
            span.set_attr("user_agent.original", user_agent)

        token: Token[span_module.Span | None] = tracer.activate_span(span)
        g.ledger_span = span
        g.ledger_span_token = token

    def _after_request(self, response: Any) -> Any:
        if not hasattr(g, "ledger_start_time"):
            return response

        duration_ms = (time.time() - g.ledger_start_time) * 1000

        tracer: tracer_module.Tracer | None = self.ledger.tracer
        span: span_module.Span | None = getattr(g, "ledger_span", None)
        token: Token[span_module.Span | None] | None = getattr(g, "ledger_span_token", None)

        path = self._get_path()
        if path is not None and tracer is not None and span is not None:
            span.name = f"{request.method} {path}"
            span.set_attr("http.route", path)
            span.set_attr("http.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(span_module.SpanStatus.ERROR)

        if tracer is not None and span is not None and token is not None:
            tracer.deactivate_span(span, token)

        if path is None:
            return response

        request_info = {
            "method": request.method,
            "path": path,
        }

        if self.capture_query_params and request.query_string:
            request_info["query_params"] = request.query_string.decode()

        if request.view_args:
            request_info["path_params"] = dict(request.view_args)

        response_body: str | None = None
        if response.status_code >= 400:
            response_body = base_middleware_module._body_preview(response.get_data(as_text=False))

        self.log_request(request_info, response.status_code, duration_ms, response_body)
        return response

    def _on_exception(self, _sender: Any, exception: Exception, **_extra: Any) -> None:
        if not hasattr(g, "ledger_start_time"):
            return

        duration_ms = (time.time() - g.ledger_start_time) * 1000

        tracer: tracer_module.Tracer | None = self.ledger.tracer
        span: span_module.Span | None = getattr(g, "ledger_span", None)
        token: Token[span_module.Span | None] | None = getattr(g, "ledger_span_token", None)

        if tracer is not None and span is not None:
            span.record_exception(exception)
            span.set_status(span_module.SpanStatus.ERROR)
            path = self._get_path()
            if path is not None:
                span.name = f"{request.method} {path}"
                span.set_attr("http.route", path)
            if token is not None:
                tracer.deactivate_span(span, token)
            g.ledger_span = None
            g.ledger_span_token = None

        path = self._get_path()
        if path is None:
            return

        request_info = {
            "method": request.method,
            "path": path,
        }

        if self.capture_query_params and request.query_string:
            request_info["query_params"] = request.query_string.decode()

        self.log_exception(request_info, exception, duration_ms)

    def _get_path(self) -> str | None:
        if self.normalize_paths and request.url_rule:
            return self._normalize_flask_path(request.url_rule.rule)

        return self.process_request_path(request.path)

    def _normalize_flask_path(self, path: str) -> str:
        normalized = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", path)
        return normalized
