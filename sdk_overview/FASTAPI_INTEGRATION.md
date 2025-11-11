# FastAPI Integration

Detailed design for FastAPI middleware integration.

## Overview

FastAPI integration uses ASGI middleware to automatically capture:
- **Request metadata**: Method, URL, headers, timestamp
- **Response metadata**: Status code, duration
- **Exceptions**: Error type, message, stack trace (errors only)

## Middleware Architecture

```python
class LedgerMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware for FastAPI applications.

    Captures all HTTP traffic and exceptions automatically.
    """

    def __init__(self, app, ledger_client: LedgerClient, **options):
        super().__init__(app)
        self.ledger = ledger_client
        self.options = options

    async def dispatch(self, request: Request, call_next):
        # Capture request start time
        start_time = time.time()

        # Store request info
        request_info = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        try:
            # Call next middleware/endpoint
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log successful request
            await self._log_request(
                request_info,
                response.status_code,
                duration_ms
            )

            return response

        except Exception as exc:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log exception
            await self._log_exception(
                request_info,
                exc,
                duration_ms
            )

            # Re-raise so app can handle normally
            raise
```

## Request Logging

**What gets logged**:
```python
{
    "timestamp": "2025-11-01T10:30:45.123Z",
    "level": "info",  # info for 2xx/3xx, warning for 4xx, error for 5xx
    "log_type": "console",
    "importance": "standard",  # high for 5xx
    "message": "GET /api/payment - 200 (145ms)",
    "attributes": {
        "http": {
            "method": "GET",
            "url": "/api/payment",
            "status_code": 200,
            "duration_ms": 145
        }
    }
}
```

**Log levels by status code**:
- **2xx, 3xx**: `info` level, `standard` importance
- **4xx**: `warning` level, `standard` importance
- **5xx**: `error` level, `high` importance

## Exception Logging

**What gets logged** (errors only):
```python
{
    "timestamp": "2025-11-01T10:30:45.123Z",
    "level": "error",
    "log_type": "exception",
    "importance": "high",
    "message": "Payment processing failed",
    "error_type": "PaymentError",
    "error_message": "Credit card declined",
    "stack_trace": "Traceback (most recent call last):\n  File ...",
    "attributes": {
        "http": {
            "method": "POST",
            "url": "/api/payment",
            "duration_ms": 245
        }
    }
}
```

**Stack trace capture**: Only for exceptions (errors), not for regular logs.

## Configuration Options

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,

    # What to capture
    capture_request_body=False,      # Don't capture by default (privacy)
    capture_response_body=False,     # Don't capture by default (privacy)
    capture_headers=False,           # Don't capture by default (security)
    capture_query_params=True,       # Capture query params (useful for debugging)

    # Filtering
    exclude_paths=["/health", "/metrics"],  # Don't log these paths
    include_paths=None,              # If set, only log these paths

    # Performance
    async_logging=True,              # Always async (non-blocking)
)
```

## Performance Considerations

### Non-Blocking Design

```python
async def dispatch(self, request, call_next):
    # ... capture request info ...

    response = await call_next(request)  # Endpoint executes

    # Add to buffer (returns instantly, no await)
    self.ledger.log_info(message, **attributes)

    return response  # User gets response immediately
```

**Latency added by middleware**: <1ms (just data capture, no I/O)

### Memory Impact

Each request creates a log entry (~1KB):
```python
Log entry size:
- Message: ~50 bytes
- Attributes: ~200 bytes (HTTP metadata)
- Overhead: ~50 bytes (Python object)
Total: ~300 bytes per request

Buffer size: 10,000 logs
Total memory: ~3MB
```

### CPU Impact

Middleware operations:
- Timestamp capture: ~1μs
- String formatting: ~10μs
- Dict creation: ~5μs
- Buffer.add(): ~1μs
- **Total**: ~20μs (<0.001ms)

**Negligible impact** on request processing.

## Privacy & Security

### What NOT to Capture

By default, middleware **does not** capture:
- **Request bodies**: May contain passwords, credit cards, PII
- **Response bodies**: May contain sensitive data
- **Headers**: May contain auth tokens, API keys
- **Cookies**: May contain session tokens

### What IS Captured

- Request method (GET, POST, etc.)
- Request URL path (e.g., `/api/payment`)
- Query parameters (configurable, can disable)
- Status code
- Duration
- Exception details (for errors only)

### Filtering Sensitive Data

```python
# Exclude sensitive endpoints
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=[
        "/auth/login",      # Password in body
        "/auth/register",   # Password in body
        "/payment/card",    # Credit card in body
    ]
)
```

### Custom Filtering

```python
class CustomLedgerMiddleware(LedgerMiddleware):
    def _sanitize_url(self, url: str) -> str:
        # Remove sensitive query params
        if "api_key=" in url:
            url = re.sub(r'api_key=[^&]+', 'api_key=***', url)
        return url
```

## Integration Example

```python
# main.py
from fastapi import FastAPI
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware

# Initialize SDK
ledger = LedgerClient(
    api_key="ldg_proj_1_abc123...",
    base_url="http://localhost:8000"
)

# Create FastAPI app
app = FastAPI()

# Add Ledger middleware
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"]
)

# Define endpoints
@app.get("/")
async def root():
    return {"message": "Hello World"}  # Automatically logged

@app.post("/payment")
async def process_payment(amount: float):
    if amount < 0:
        raise ValueError("Amount must be positive")  # Automatically logged
    return {"status": "success"}

# Shutdown handler
@app.on_event("shutdown")
async def shutdown():
    await ledger.shutdown()
```

**That's it!** All endpoints are now automatically monitored.

## Middleware Order

Ledger middleware should be **last in the chain** (first to execute):

```python
# Correct order
app.add_middleware(CORSMiddleware)      # Executes 3rd
app.add_middleware(GZipMiddleware)      # Executes 2nd
app.add_middleware(LedgerMiddleware)    # Executes 1st ✓
```

**Why?**
- Captures CORS errors
- Captures GZip errors
- Sees the "real" response (after all transformations)

## Testing with Middleware

```python
# test_main.py
from fastapi.testclient import TestClient
from unittest.mock import Mock

def test_endpoint_logging():
    # Mock ledger client
    mock_ledger = Mock(spec=LedgerClient)

    # Create app with mock
    app = FastAPI()
    app.add_middleware(LedgerMiddleware, ledger_client=mock_ledger)

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    # Make request
    client = TestClient(app)
    response = client.get("/test")

    # Verify log was created
    assert mock_ledger.log_info.called
    args = mock_ledger.log_info.call_args
    assert "GET /test" in args[0][0]  # Message contains method and path
```

## Advanced Features (Future)

### Custom Context Enrichment

```python
class EnrichedLedgerMiddleware(LedgerMiddleware):
    async def dispatch(self, request, call_next):
        # Add user context
        user_id = request.state.user_id if hasattr(request.state, "user_id") else None

        # Call parent
        response = await super().dispatch(request, call_next)

        # Add custom attributes
        if user_id:
            self.ledger.set_context(user_id=user_id)

        return response
```

### Performance Metrics

```python
# Capture additional performance metrics
await self.ledger.log_info(
    message,
    attributes={
        "http": {...},
        "performance": {
            "db_queries": request.state.db_query_count,
            "cache_hits": request.state.cache_hits,
            "memory_mb": get_memory_usage()
        }
    }
)
```

### Distributed Tracing (Future)

```python
# Integrate with OpenTelemetry
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def dispatch(self, request, call_next):
    span = trace.get_current_span()
    trace_id = span.get_span_context().trace_id

    # Add trace ID to logs
    await self.ledger.log_info(
        message,
        attributes={
            "trace_id": trace_id,
            ...
        }
    )
```

## Troubleshooting

### Middleware not capturing logs

**Problem**: Logs not appearing in Ledger

**Solutions**:
1. Check middleware order (should be last/first to execute)
2. Verify API key is valid
3. Check `exclude_paths` configuration
4. Enable debug mode: `LedgerClient(debug=True)`
5. Check stderr for SDK errors

### High latency

**Problem**: Requests are slow after adding middleware

**Solutions**:
1. Verify `async_logging=True` (should be default)
2. Check buffer isn't blocking (shouldn't happen)
3. Profile with `cProfile` to identify bottleneck
4. Disable middleware temporarily to confirm source

### Memory usage growing

**Problem**: App memory increases over time

**Solutions**:
1. Check buffer size limit (default 10,000)
2. Verify background flusher is running
3. Check for Ledger server connectivity (logs may accumulate)
4. Monitor with `ledger.get_metrics()["logs_buffered"]`

## Next Steps

- See [PERFORMANCE.md](PERFORMANCE.md) for optimization strategies
- See [ERROR_HANDLING.md](ERROR_HANDLING.md) for retry logic
- See [CONFIGURATION.md](CONFIGURATION.md) for tuning options
