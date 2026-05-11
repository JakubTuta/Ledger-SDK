from typing import Any

import ledger.tracing as tracing_module
import ledger.tracing.span as span_module

_MAX_STATEMENT_LENGTH = 1024


def instrument(engine: Any) -> None:
    from sqlalchemy import event

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        tracer = tracing_module.get_tracer()
        if tracer is None:
            return

        span = tracer.start_span("db.query", kind=span_module.SpanKind.CLIENT)
        span.set_attr("db.system", engine.dialect.name)
        truncated = statement[:_MAX_STATEMENT_LENGTH]
        if len(statement) > _MAX_STATEMENT_LENGTH:
            truncated += "... [truncated]"
        span.set_attr("db.statement", truncated)

        if not hasattr(conn, "_ledger_spans"):
            conn._ledger_spans = []
        token = tracer.activate_span(span)
        conn._ledger_spans.append((span, token))

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        tracer = tracing_module.get_tracer()
        if tracer is None or not hasattr(conn, "_ledger_spans") or not conn._ledger_spans:
            return

        span, token = conn._ledger_spans.pop()
        if hasattr(cursor, "rowcount") and cursor.rowcount >= 0:
            span.set_attr("db.rows_affected", cursor.rowcount)
        tracer.deactivate_span(span, token)

    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context: Any) -> None:
        tracer = tracing_module.get_tracer()
        conn = getattr(exception_context, "connection", None)
        if tracer is None or conn is None:
            return
        if not hasattr(conn, "_ledger_spans") or not conn._ledger_spans:
            return

        span, token = conn._ledger_spans.pop()
        exc = exception_context.original_exception
        if exc is not None and isinstance(exc, Exception):
            span.record_exception(exc)
        span.set_status(span_module.SpanStatus.ERROR)
        tracer.deactivate_span(span, token)
