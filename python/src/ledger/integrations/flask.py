import re
import time
from typing import Pattern

from flask import Flask, g, request

import ledger.core.base_middleware as base_middleware_module
import ledger.core.client as client_module


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
        app.errorhandler(Exception)(self._handle_exception)

    def _before_request(self):
        if self.should_exclude_path(request.path):
            return None

        g.ledger_start_time = time.time()

    def _after_request(self, response):
        if not hasattr(g, "ledger_start_time"):
            return response

        duration_ms = (time.time() - g.ledger_start_time) * 1000

        path = self._get_path()
        if path is None:
            return response

        request_info = {
            "method": request.method,
            "path": path,
        }

        if self.capture_query_params and request.query_string:
            request_info["query_params"] = request.query_string.decode()

        self.log_request(request_info, response.status_code, duration_ms)
        return response

    def _handle_exception(self, exc: Exception):
        if not hasattr(g, "ledger_start_time"):
            raise exc

        duration_ms = (time.time() - g.ledger_start_time) * 1000

        path = self._get_path()
        if path is None:
            raise exc

        request_info = {
            "method": request.method,
            "path": path,
        }

        if self.capture_query_params and request.query_string:
            request_info["query_params"] = request.query_string.decode()

        self.log_exception(request_info, exc, duration_ms)
        raise exc

    def _get_path(self) -> str | None:
        if self.normalize_paths and request.url_rule:
            return self._normalize_flask_path(request.url_rule.rule)

        return self.process_request_path(request.path)

    def _normalize_flask_path(self, path: str) -> str:
        normalized = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", path)
        return normalized
