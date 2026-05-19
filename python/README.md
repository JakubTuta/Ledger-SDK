# Ledger SDK for Python

**Observability for developers who just want to ship.**

Add one line of code. Get automatic request logging, exception tracking, and performance monitoring. No configuration required.

```python
from ledger.integrations.fastapi import LedgerMiddleware

app.add_middleware(LedgerMiddleware, ledger_client=ledger)
```

That's it. Every request, response, and exception is now logged to your Ledger dashboard.

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI Version](https://img.shields.io/badge/pypi-v1.6.1-blue.svg)](https://pypi.org/project/ledger-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Supported Frameworks:** FastAPI • Django • Flask

## Why Ledger?

Traditional observability tools are complicated, expensive, and slow down your application. Ledger is different:

- **Actually zero overhead** - Less than 0.1ms per request. Your users won't notice.
- **Works out of the box** - No configuration files, no setup guides, no dashboards to build.
- **Production-ready from day one** - Built-in retry logic, rate limiting, and graceful failure handling.

We built Ledger because we were tired of spending hours setting up logging infrastructure for every new project. Now it takes one line of code.

## Installation

```bash
pip install ledger-sdk
```

## Quick Start

### FastAPI

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware

ledger = LedgerClient(
    api_key="ledger_proj_1_your_api_key",
    base_url="https://ledger-server.jtuta.cloud"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await ledger.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(LedgerMiddleware, ledger_client=ledger)
```

### Django

```python
# settings.py
import os
from ledger import LedgerClient

LEDGER_CLIENT = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY", "ledger_proj_1_your_api_key"),
    base_url=os.getenv("LEDGER_BASE_URL", "https://ledger-server.jtuta.cloud")
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "ledger.integrations.django.LedgerMiddleware",  # Add this
]
```

### Flask

```python
from flask import Flask
from ledger import LedgerClient
from ledger.integrations.flask import LedgerMiddleware

app = Flask(__name__)

ledger = LedgerClient(
    api_key="ledger_proj_1_your_api_key",
    base_url="https://ledger-server.jtuta.cloud"
)

app.config["LEDGER_CLIENT"] = ledger

LedgerMiddleware(app)
```

That's all you need. Start your app and watch the logs flow into your [Ledger dashboard](https://ledger.jtuta.cloud).

[Get your API key](https://ledger.jtuta.cloud) • [View examples](examples/)

## What You Get

**Automatic capture** - Every request, response, and exception. No manual logging code.

**Distributed tracing** - W3C-compatible spans across services. Trace IDs automatically attached to logs emitted inside a span.

**Full context** - Stack traces, request headers, response bodies, user attributes. Everything you need to debug.

**Performance insights** - Response times, error rates, slow endpoints. Know where to optimize.

**Production reliability** - Automatic retries, rate limiting, and graceful degradation. Works even when your network doesn't.

**Zero performance impact** - All logging happens in the background. Your API stays fast.

## More Examples

### Manual Logging

```python
ledger.log_info("User logged in", attributes={"user_id": 123})

ledger.log_error("Payment failed", attributes={"amount": 99.99, "error_code": "CARD_DECLINED"})

try:
    result = process_payment()
except Exception as e:
    ledger.log_exception(e, message="Payment processing failed")
```

### Exclude Paths

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"]
)
```

[More examples](examples/) • [Full API reference](../sdk_overview/)

## Configuration

The defaults work for most applications. But if you're handling extreme traffic, you can tune the SDK:

```python
ledger = LedgerClient(
    api_key="ledger_proj_1_your_api_key",
    flush_interval=5.0,        # Seconds between flushes
    flush_size=1000,            # Logs before auto-flush
    max_buffer_size=10000,      # Max logs in memory
)
```

**High traffic (>1000 req/sec)?** Decrease `flush_interval` to 2.0 and increase `max_buffer_size` to 50000.

**Low traffic (<100 req/sec)?** Increase `flush_interval` to 10.0 and decrease `flush_size` to 50.

[Full configuration reference](../sdk_overview/CONFIGURATION.md)

## Monitoring

Check if the SDK is working properly:

```python
if ledger.is_healthy():
    print("SDK is healthy")

status = ledger.get_health_status()
metrics = ledger.get_metrics()
```

Expose as HTTP endpoints (FastAPI):

```python
@app.get("/sdk/health")
async def sdk_health():
    return ledger.get_health_status()

@app.get("/sdk/metrics")
async def sdk_metrics():
    return ledger.get_metrics()
```

The SDK automatically handles failures with retries and circuit breakers. Check the health endpoint to see if anything is wrong.

## Performance

Ledger adds less than 0.1ms to each request. All network I/O happens in the background.

Your app stays fast even if the Ledger server is slow or down. Logs are batched and sent every 5 seconds or when 1000 logs accumulate.

[Performance benchmarks](../sdk_overview/PERFORMANCE.md)

## Distributed Tracing

Trace requests across services with spans. Traces appear in Ledger's **Trace List** panel and can be pinned as single-trace waterfall panels directly from the dashboard.

### Setup

The tracing module is enabled automatically when you call `LedgerClient(...)`. Get a tracer for your service and start creating spans:

```python
from ledger import LedgerClient
from ledger.tracing import get_tracer

ledger = LedgerClient(api_key="...", base_url="https://ledger-server.jtuta.cloud", service_name="my-service")
tracer = get_tracer()
```

### Manual spans

```python
with tracer.start_as_current_span("process-order", attributes={"order_id": 42}) as span:
    result = process_order(42)
    span.set_attribute("status", result.status)
```

### Nested spans (cross-service)

Child spans are automatically linked to the current span via context propagation:

```python
with tracer.start_as_current_span("api-request") as root:
    with tracer.start_as_current_span("db-query") as child:
        rows = await db.execute("SELECT ...")
```

### Propagate context to downstream services

Inject the W3C `traceparent` header into outgoing HTTP calls so downstream services can continue the trace:

```python
from ledger.tracing import propagation

with tracer.start_as_current_span("outgoing-call") as span:
    headers = {}
    propagation.inject(headers, span)
    response = httpx.get("https://downstream/api", headers=headers)
```

In the downstream service, extract the context before starting spans:

```python
ctx = propagation.extract(request.headers)
with tracer.start_as_current_span("downstream-handler", parent=ctx):
    ...
```

### FastAPI auto-instrumentation

With `LedgerMiddleware`, every request automatically becomes a root span. Spans you create inside request handlers are nested under it:

```python
app.add_middleware(LedgerMiddleware, ledger_client=ledger)

@app.get("/orders/{id}")
async def get_order(id: int):
    tracer = get_tracer()
    with tracer.start_as_current_span("db-fetch", attributes={"order_id": id}):
        return await db.get_order(id)
```

### gRPC client spans

Use a `UnaryUnaryClientInterceptor` to create a span for each outgoing gRPC call and inject the trace context into metadata.

**Critical: call `LedgerClient(...)` before creating any channels.** Interceptors cannot be added to an existing channel.

```python
import grpc
from ledger.tracing import get_tracer, propagation


class _MutableClientCallDetails:
    def __init__(self, details, metadata):
        self.method = details.method
        self.timeout = details.timeout
        self.metadata = metadata
        self.credentials = details.credentials
        self.wait_for_ready = details.wait_for_ready


class TracingClientInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    async def intercept_unary_unary(self, continuation, client_call_details, request):
        tracer = get_tracer()
        if tracer is None:
            return await continuation(client_call_details, request)

        method = client_call_details.method
        if isinstance(method, bytes):
            method = method.decode()

        with tracer.start_as_current_span(f"grpc.client{method}") as span:
            carrier: dict[str, str] = {}
            propagation.inject(carrier, span)

            metadata = list(client_call_details.metadata or [])
            for k, v in carrier.items():
                metadata.append((k, v))

            return await continuation(_MutableClientCallDetails(client_call_details, metadata), request)
```

Pass the interceptor when creating the channel — **every channel**, every time:

```python
# Initialize ledger FIRST
ledger = LedgerClient(api_key="...", base_url="https://ledger-server.jtuta.cloud", service_name="my-service")

# Then create channels with the interceptor
channel = grpc.aio.insecure_channel(
    "host:port",
    interceptors=[TracingClientInterceptor()],
)
```

A channel created without `interceptors=` will never produce spans, even if the tracer is initialized.

### Trace IDs in logs

Any log emitted inside an active span automatically includes the `trace_id` and `span_id` as attributes, linking logs to traces in the dashboard.

### Viewing traces

Once spans are flowing, open the Ledger dashboard and add a **Trace List** panel. Traces appear within seconds of the flush interval (default 5 s). Click any row to pin it as a single-trace waterfall panel.

## How It Works

Ledger captures logs in your application (<0.1ms), buffers them in memory, and sends batches to the Ledger server in the background. Your application never waits for network I/O.

If the server is down or slow, the SDK automatically retries with backoff. If it's really stuck, it drops old logs to prevent memory issues. You get observability without the risk.

[Architecture details](../sdk_overview/ARCHITECTURE.md) • [Error handling guide](../sdk_overview/ERROR_HANDLING.md)

## Development

```bash
git clone https://github.com/JakubTuta/Ledger-SDK.git
cd Ledger-SDK/python

pip install -e ".[dev]"

pytest
```

[Contributing guide](../CONTRIBUTING.md) • [Run examples](examples/)

## Production

Set your API key as an environment variable:

```bash
export LEDGER_API_KEY="ledger_proj_1_your_production_key"
export LEDGER_BASE_URL="https://ledger-server.jtuta.cloud"
```

Then use it in your code:

```python
import os

ledger = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY"),
    base_url=os.getenv("LEDGER_BASE_URL")
)
```

Set up health endpoints and monitor them:

```python
@app.get("/health")
async def health():
    return {"status": "healthy", "ledger": ledger.is_healthy()}
```

[Deployment guide](../sdk_overview/DEPLOYMENT.md)

## Need Help?

- [Read the docs](../sdk_overview/) - Architecture, configuration, and guides
- [Open an issue](https://github.com/JakubTuta/Ledger-SDK/issues) - Bug reports and feature requests
- [View examples](examples/) - See it in action
- [Changelog](CHANGELOG.md) - Version history

## Links

- [PyPI Package](https://pypi.org/project/ledger-sdk/) - Install the SDK
- [Dashboard](https://ledger.jtuta.cloud) - View your logs
- [API Server](https://ledger-server.jtuta.cloud) - Server endpoint
- [Backend Source](https://github.com/JakubTuta/Ledger-APP) - API server code
- [Frontend Source](https://github.com/JakubTuta/Ledger-WEB) - Dashboard code

## License

MIT License - see [LICENSE](LICENSE) for details.
