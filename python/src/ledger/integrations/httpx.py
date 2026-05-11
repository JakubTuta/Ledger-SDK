from typing import Any

import ledger.tracing as tracing_module
import ledger.tracing.propagation as propagation_module
import ledger.tracing.span as span_module

_installed = False


def install() -> None:
    global _installed  # noqa: PLW0603
    if _installed:
        return

    import httpx as _httpx

    original_send = _httpx.Client.send
    original_async_send = _httpx.AsyncClient.send

    def patched_send(self: Any, request: Any, **kwargs: Any) -> Any:
        tracer = tracing_module.get_tracer()
        if tracer is None:
            return original_send(self, request, **kwargs)

        with tracer.start_as_current_span(
            f"HTTP {request.method}",
            kind=span_module.SpanKind.CLIENT,
        ) as span:
            span.set_attr("http.method", request.method)
            span.set_attr("http.url", str(request.url))
            inject_headers: dict[str, str] = {}
            propagation_module.inject(inject_headers, span)
            for key, value in inject_headers.items():
                request.headers[key] = value
            try:
                response = original_send(self, request, **kwargs)
                span.set_attr("http.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status(span_module.SpanStatus.ERROR)
                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(span_module.SpanStatus.ERROR)
                raise

    async def patched_async_send(self: Any, request: Any, **kwargs: Any) -> Any:
        tracer = tracing_module.get_tracer()
        if tracer is None:
            return await original_async_send(self, request, **kwargs)

        with tracer.start_as_current_span(
            f"HTTP {request.method}",
            kind=span_module.SpanKind.CLIENT,
        ) as span:
            span.set_attr("http.method", request.method)
            span.set_attr("http.url", str(request.url))
            inject_headers = {}
            propagation_module.inject(inject_headers, span)
            for key, value in inject_headers.items():
                request.headers[key] = value
            try:
                response = await original_async_send(self, request, **kwargs)
                span.set_attr("http.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status(span_module.SpanStatus.ERROR)
                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(span_module.SpanStatus.ERROR)
                raise

    _httpx.Client.send = patched_send
    _httpx.AsyncClient.send = patched_async_send
    _installed = True
