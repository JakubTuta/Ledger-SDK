from typing import Any

import opentelemetry.context as context_api
import opentelemetry.trace as trace_api

import ledger.integrations.common as common_module

_MAX_STATEMENT_LENGTH = 1024


def instrument(engine: Any) -> None:
    from sqlalchemy import event

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        tracer = common_module.get_tracer()

        span = tracer.start_span("db.query", kind=trace_api.SpanKind.CLIENT)
        span.set_attribute("db.system", engine.dialect.name)
        truncated = statement[:_MAX_STATEMENT_LENGTH]
        if len(statement) > _MAX_STATEMENT_LENGTH:
            truncated += "... [truncated]"
        span.set_attribute("db.statement", truncated)

        if not hasattr(conn, "_ledger_spans"):
            conn._ledger_spans = []
        token = context_api.attach(trace_api.set_span_in_context(span))
        conn._ledger_spans.append((span, token))

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Any,
        cursor: Any,
        _statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        if not hasattr(conn, "_ledger_spans") or not conn._ledger_spans:
            return

        span, token = conn._ledger_spans.pop()
        if hasattr(cursor, "rowcount") and cursor.rowcount >= 0:
            span.set_attribute("db.rows_affected", cursor.rowcount)
        span.end()
        context_api.detach(token)

    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context: Any) -> None:
        conn = getattr(exception_context, "connection", None)
        if conn is None or not hasattr(conn, "_ledger_spans") or not conn._ledger_spans:
            return

        span, token = conn._ledger_spans.pop()
        exc = exception_context.original_exception
        if exc is not None and isinstance(exc, Exception):
            span.record_exception(exc)
        span.set_status(trace_api.StatusCode.ERROR)
        span.end()
        context_api.detach(token)
