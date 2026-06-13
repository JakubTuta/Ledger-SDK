# Ledger SDK for Python

**Observability for developers who just want to ship.**

Add one line of code. Get automatic request logging, exception tracking, and performance monitoring. No configuration required.

```python
from ledger.integrations.fastapi import LedgerMiddleware

app.add_middleware(LedgerMiddleware, ledger_client=ledger)
```

That's it. Every request, response, and exception is now logged to your Ledger dashboard.

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI Version](https://img.shields.io/badge/pypi-v1.7.0-blue.svg)](https://pypi.org/project/ledger-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Supported Frameworks:** FastAPI • Django • Flask

## Why Ledger?

- **Actually zero overhead** - Less than 0.1ms per request. Your users won't notice.
- **Works out of the box** - No configuration files, no setup guides, no dashboards to build.
- **Production-ready from day one** - Built-in retry logic, rate limiting, and graceful failure handling.

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

## Manual Logging

```python
ledger.log_info("User logged in", attributes={"user_id": 123})

ledger.log_warning("Slow query", attributes={"duration_ms": 450})

ledger.log_error("Payment failed", attributes={"amount": 99.99, "error_code": "CARD_DECLINED"})

try:
    result = process_payment()
except Exception as e:
    ledger.log_exception(e, message="Payment processing failed")
```

## Exclude Paths

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"]
)
```

## Only Log Registered Routes

By default, the SDK only logs requests that match a registered route — scanner noise, 404s, and bot traffic are dropped automatically.

```python
# To log everything including unmatched paths:
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    only_registered_routes=False
)
```

## Configuration

The defaults work for most applications. Tune when needed:

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

## Distributed Tracing

Trace requests across services with spans. Traces appear in Ledger's **Trace List** panel on the dashboard.

### Setup

Tracing is enabled automatically when you call `LedgerClient(...)`.

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

### Cross-service propagation

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

### Trace IDs in logs

Any log emitted inside an active span automatically includes the `trace_id` and `span_id` as attributes, linking logs to traces in the dashboard.

## Monitoring the SDK

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
```

## Production

Set your API key as an environment variable:

```bash
export LEDGER_API_KEY="ledger_proj_1_your_production_key"
export LEDGER_BASE_URL="https://ledger-server.jtuta.cloud"
```

```python
import os

ledger = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY"),
    base_url=os.getenv("LEDGER_BASE_URL")
)
```

## Need Help?

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
