import contextlib
from collections.abc import Generator
from typing import Any

import ledger.tracing.propagation as propagation_module
import ledger.tracing.span as span_module
import ledger.tracing.tracer as tracer_module


@contextlib.contextmanager
def http_server_span(
    tracer: tracer_module.Tracer,
    method: str,
    route: str,
    url: str,
    headers: Any,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> Generator[span_module.Span, None, None]:
    context = propagation_module.extract(headers)
    with tracer.start_as_current_span(
        f"{method} {route}",
        kind=span_module.SpanKind.SERVER,
        parent=context,
    ) as span:
        span.set_attr("http.method", method)
        span.set_attr("http.route", route)
        span.set_attr("http.url", url)
        if client_ip is not None:
            span.set_attr("http.client_ip", client_ip)
        if user_agent is not None:
            span.set_attr("user_agent.original", user_agent)
        yield span


def django_meta_to_headers(meta: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in meta.items():
        if key.startswith("HTTP_") and isinstance(value, str):
            header_name = key[5:].replace("_", "-").lower()
            headers[header_name] = value
    return headers
