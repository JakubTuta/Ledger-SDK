from typing import Any

import opentelemetry.trace as trace_api
from opentelemetry import propagate

import ledger.integrations.common as common_module

_installed = False


def install() -> None:
    global _installed  # noqa: PLW0603
    if _installed:
        return

    import requests as _requests

    original_send = _requests.Session.send

    def patched_send(self: Any, request: Any, **kwargs: Any) -> Any:
        tracer = common_module.get_tracer()

        with tracer.start_as_current_span(
            f"HTTP {request.method}",
            kind=trace_api.SpanKind.CLIENT,
        ) as span:
            span.set_attribute("http.request.method", request.method)
            span.set_attribute("url.full", request.url)
            propagate.inject(request.headers)
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

    _requests.Session.send = patched_send
    _installed = True
