import re
import time
from typing import Pattern

import ledger.core.base_middleware as base_middleware_module
import ledger.core.client as client_module


class LedgerMiddleware(base_middleware_module.BaseMiddleware):
    def __init__(
        self,
        get_response,
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
        )
        self.get_response = get_response

    def __call__(self, request):
        if self.should_exclude_path(request.path):
            return self.get_response(request)

        start_time = time.time()

        try:
            response = self.get_response(request)
            duration_ms = (time.time() - start_time) * 1000

            path = self._get_path(request)
            if path is None:
                return response

            request_info = {
                "method": request.method,
                "path": path,
            }

            if self.capture_query_params and request.META.get("QUERY_STRING"):
                request_info["query_params"] = request.META["QUERY_STRING"]

            self.log_request(request_info, response.status_code, duration_ms)
            return response
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000

            path = self._get_path(request)
            if path is None:
                raise

            request_info = {
                "method": request.method,
                "path": path,
            }

            if self.capture_query_params and request.META.get("QUERY_STRING"):
                request_info["query_params"] = request.META["QUERY_STRING"]

            self.log_exception(request_info, exc, duration_ms)
            raise

    def _get_path(self, request) -> str | None:
        if hasattr(request, "resolver_match") and request.resolver_match:
            route = request.resolver_match.route
            if route:
                return self._normalize_django_path(route)

        return self.process_request_path(request.path)

    def _normalize_django_path(self, path: str) -> str:
        normalized = re.sub(r"<(?:(?P<converter>[^:>]+):)?(?P<parameter>[^>]+)>", r"{\g<parameter>}", path)
        return normalized
