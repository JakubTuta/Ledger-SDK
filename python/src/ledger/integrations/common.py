import contextlib
from collections.abc import Generator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import opentelemetry.trace as trace_api
from opentelemetry import propagate

import ledger.core.caller as caller_module

_TRACER_NAME = "ledger-sdk-python"

_tracer_provider: "trace_api.TracerProvider | None" = None


def use_tracer_provider(provider: "trace_api.TracerProvider") -> None:
    """Route integration spans through `provider` (the active LedgerClient's).

    The global tracer provider is set-once and may belong to the application's
    own OpenTelemetry setup, so integrations must not rely on it.
    """
    global _tracer_provider  # noqa: PLW0603
    _tracer_provider = provider


def release_tracer_provider(provider: "trace_api.TracerProvider") -> None:
    global _tracer_provider  # noqa: PLW0603
    if _tracer_provider is provider:
        _tracer_provider = None


def get_tracer() -> trace_api.Tracer:
    if _tracer_provider is not None:
        return _tracer_provider.get_tracer(_TRACER_NAME)
    return trace_api.get_tracer(_TRACER_NAME)


def url_without_query(url: str) -> str:
    """`url` minus query string and fragment.

    Query strings routinely carry credentials (tokens, signed-URL signatures,
    password-reset codes); spans keep the location only. Query parameters are
    recorded on endpoint logs, and only when capture_query_params is enabled.
    """
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


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
        span.set_attribute("url.full", url_without_query(url))
        client_ip_prefix = caller_module.truncate_ip(client_ip) if client_ip is not None else None
        if client_ip_prefix is not None:
            span.set_attribute("client.address", client_ip_prefix)
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
    span.set_attribute("url.full", url_without_query(url))
    client_ip_prefix = caller_module.truncate_ip(client_ip) if client_ip is not None else None
    if client_ip_prefix is not None:
        span.set_attribute("client.address", client_ip_prefix)
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
