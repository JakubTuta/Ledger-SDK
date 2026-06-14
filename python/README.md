# Ledger SDK for Python

**Observability for developers who just want to ship.**

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI Version](https://img.shields.io/badge/pypi-v1.7.0-blue.svg)](https://pypi.org/project/ledger-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Supported Frameworks:** FastAPI • Django • Flask

---

## Installation

```bash
pip install ledger-sdk
```

## Setup

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
    "ledger.integrations.django.LedgerMiddleware",
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

## Manual Logging

```python
ledger.log_info("User logged in", attributes={"user_id": 123})
ledger.log_warning("Slow query", attributes={"duration_ms": 450})
ledger.log_error("Payment failed", attributes={"error_code": "CARD_DECLINED"})

try:
    result = process_payment()
except Exception as e:
    ledger.log_exception(e, message="Payment processing failed")
```

## Configuration

```python
ledger = LedgerClient(
    api_key="ledger_proj_1_your_api_key",
    flush_interval=5.0,     # Seconds between flushes
    flush_size=1000,        # Logs before auto-flush
    max_buffer_size=10000,  # Max logs buffered in memory
)
```

Use environment variables in production:

```bash
export LEDGER_API_KEY="ledger_proj_1_your_api_key"
export LEDGER_BASE_URL="https://ledger-server.jtuta.cloud"
```

```python
import os

ledger = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY"),
    base_url=os.getenv("LEDGER_BASE_URL")
)
```

## Exclude Paths

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"]
)
```

By default the SDK only logs requests that match a registered route — scanner noise, 404s, and bot traffic are dropped automatically. To log everything:

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    only_registered_routes=False
)
```

---

## Distributed Tracing

Tracing is enabled automatically when you create a `LedgerClient`. Traces appear in Ledger's **Trace List** panel on the dashboard.

```python
from ledger import LedgerClient
from ledger.tracing import get_tracer

ledger = LedgerClient(api_key="...", base_url="...", service_name="my-service")
tracer = get_tracer()
```

### Manual spans

```python
with tracer.start_as_current_span("process-order", attributes={"order_id": 42}) as span:
    result = process_order(42)
    span.set_attribute("status", result.status)
```

### Cross-service propagation

Inject the W3C `traceparent` header into outgoing calls:

```python
from ledger.tracing import propagation

with tracer.start_as_current_span("outgoing-call") as span:
    headers = {}
    propagation.inject(headers, span)
    response = httpx.get("https://downstream/api", headers=headers)
```

Extract context in the downstream service:

```python
ctx = propagation.extract(request.headers)
with tracer.start_as_current_span("downstream-handler", parent=ctx):
    ...
```

Any log emitted inside an active span automatically includes `trace_id` and `span_id`, linking logs to traces in the dashboard.

### FastAPI auto-instrumentation

With `LedgerMiddleware`, every request automatically becomes a root span. Spans created inside request handlers are nested under it:

```python
@app.get("/orders/{id}")
async def get_order(id: int):
    tracer = get_tracer()
    with tracer.start_as_current_span("db-fetch", attributes={"order_id": id}):
        return await db.get_order(id)
```

---

## SDK Health

```python
if ledger.is_healthy():
    print("SDK is healthy")

status = ledger.get_health_status()
metrics = ledger.get_metrics()
```

Expose as an endpoint:

```python
@app.get("/sdk/health")
async def sdk_health():
    return ledger.get_health_status()
```

---

## Links

- [PyPI Package](https://pypi.org/project/ledger-sdk/)
- [Dashboard](https://ledger.jtuta.cloud)
- [Examples](examples/)
- [Changelog](CHANGELOG.md)

## License

MIT License — see [LICENSE](LICENSE) for details.
