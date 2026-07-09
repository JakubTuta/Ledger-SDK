from typing import Any

import opentelemetry.trace as trace_api
from opentelemetry import propagate

import ledger.integrations.common as common_module

_installed = False


def install() -> None:
    global _installed  # noqa: PLW0603
    if _installed:
        return

    import httpx as _httpx

    original_send = _httpx.Client.send
    original_async_send = _httpx.AsyncClient.send

    def patched_send(self: Any, request: Any, **kwargs: Any) -> Any:
        tracer = common_module.get_tracer()

        with tracer.start_as_current_span(
            f"HTTP {request.method}",
            kind=trace_api.SpanKind.CLIENT,
        ) as span:
            span.set_attribute("http.request.method", request.method)
            span.set_attribute("url.full", str(request.url))
            inject_headers: dict[str, str] = {}
            propagate.inject(inject_headers)
            for key, value in inject_headers.items():
                request.headers[key] = value
            try:
                response = original_send(self, request, **kwargs)
                span.set_attribute("http.response.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status(trace_api.StatusCode.ERROR)
                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(trace_api.StatusCode.ERROR)
                raise

    async def patched_async_send(self: Any, request: Any, **kwargs: Any) -> Any:
        tracer = common_module.get_tracer()

        with tracer.start_as_current_span(
            f"HTTP {request.method}",
            kind=trace_api.SpanKind.CLIENT,
        ) as span:
            span.set_attribute("http.request.method", request.method)
            span.set_attribute("url.full", str(request.url))
            inject_headers = {}
            propagate.inject(inject_headers)
            for key, value in inject_headers.items():
                request.headers[key] = value
            try:
                response = await original_async_send(self, request, **kwargs)
                span.set_attribute("http.response.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status(trace_api.StatusCode.ERROR)
                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(trace_api.StatusCode.ERROR)
                raise

    _httpx.Client.send = patched_send
    _httpx.AsyncClient.send = patched_async_send
    _installed = True
