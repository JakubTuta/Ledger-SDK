from typing import Any

import ledger.tracing as tracing_module
import ledger.tracing.propagation as propagation_module
import ledger.tracing.span as span_module

_installed = False


def install() -> None:
    global _installed  # noqa: PLW0603
    if _installed:
        return

    import requests as _requests

    original_send = _requests.Session.send

    def patched_send(self: Any, request: Any, **kwargs: Any) -> Any:
        tracer = tracing_module.get_tracer()
        if tracer is None:
            return original_send(self, request, **kwargs)

        with tracer.start_as_current_span(
            f"HTTP {request.method}",
            kind=span_module.SpanKind.CLIENT,
        ) as span:
            span.set_attr("http.method", request.method)
            span.set_attr("http.url", request.url)
            propagation_module.inject(request.headers, span)
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

    _requests.Session.send = patched_send
    _installed = True
