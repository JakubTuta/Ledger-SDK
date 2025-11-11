import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

import ledger.core.client as client_module


class LedgerMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        ledger_client: "client_module.LedgerClient",
        exclude_paths: list[str] | None = None,
        capture_query_params: bool = True,
    ):
        super().__init__(app)
        self.ledger = ledger_client
        self.exclude_paths = exclude_paths or []
        self.capture_query_params = capture_query_params

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        start_time = time.time()

        request_info = {
            "method": request.method,
            "path": request.url.path,
        }

        if self.capture_query_params and request.url.query:
            request_info["query_params"] = str(request.url.query)

        try:
            response = await call_next(request)

            duration_ms = (time.time() - start_time) * 1000

            self._log_request(request_info, response.status_code, duration_ms)

            return response

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000

            self._log_exception(request_info, exc, duration_ms)

            raise

    def _log_request(
        self,
        request_info: dict[str, str],
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

        self.ledger._log(
            level=level,
            log_type="console",
            importance=importance,
            message=message,
            attributes={
                "http": {
                    "method": request_info["method"],
                    "path": request_info["path"],
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                    "query_params": request_info.get("query_params"),
                }
            },
        )

    def _log_exception(
        self,
        request_info: dict[str, str],
        exception: Exception,
        duration_ms: float,
    ) -> None:
        message = f"{request_info['method']} {request_info['path']} - Exception: {exception!s}"

        self.ledger.log_exception(
            exception=exception,
            message=message,
            attributes={
                "http": {
                    "method": request_info["method"],
                    "path": request_info["path"],
                    "duration_ms": round(duration_ms, 2),
                    "query_params": request_info.get("query_params"),
                }
            },
        )
