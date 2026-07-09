import contextlib
from collections.abc import Generator
from typing import Any

import opentelemetry.trace as trace_api
from opentelemetry import propagate

_TRACER_NAME = "ledger-sdk-python"


def get_tracer() -> trace_api.Tracer:
    return trace_api.get_tracer(_TRACER_NAME)


@contextlib.contextmanager
def http_server_span(
    method: str,
    route: str,
    url: str,
    headers: Any,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> Generator[trace_api.Span, None, None]:
    context = propagate.extract(headers)
    with get_tracer().start_as_current_span(
        f"{method} {route}",
        kind=trace_api.SpanKind.SERVER,
        context=context,
    ) as span:
        span.set_attribute("http.request.method", method)
        span.set_attribute("http.route", route)
        span.set_attribute("url.full", url)
        if client_ip is not None:
            span.set_attribute("client.address", client_ip)
        if user_agent is not None:
            span.set_attribute("user_agent.original", user_agent)
        yield span


def start_server_span(
    method: str,
    route: str,
    url: str,
    headers: Any,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[trace_api.Span, "trace_api.context.Context | Any"]:
    """Start a SERVER span without attaching it via a `with` block.

    Used by frameworks (Flask, Django) that expose request lifecycle as
    separate before/after callbacks rather than a single call stack.
    Callers must attach the returned span's context themselves and end the
    span explicitly.
    """
    context = propagate.extract(headers)
    span = get_tracer().start_span(
        f"{method} {route}",
        kind=trace_api.SpanKind.SERVER,
        context=context,
    )
    span.set_attribute("http.request.method", method)
    span.set_attribute("url.full", url)
    if client_ip is not None:
        span.set_attribute("client.address", client_ip)
    if user_agent is not None:
        span.set_attribute("user_agent.original", user_agent)
    return span, trace_api.set_span_in_context(span)


def django_meta_to_headers(meta: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in meta.items():
        if key.startswith("HTTP_") and isinstance(value, str):
            header_name = key[5:].replace("_", "-").lower()
            headers[header_name] = value
    return headers
