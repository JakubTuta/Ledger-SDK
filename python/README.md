# Ledger SDK for Python

**OpenTelemetry-native observability for developers who just want to ship.**

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI Version](https://img.shields.io/badge/pypi-v2.0.0-blue.svg)](https://pypi.org/project/ledger-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Supported Frameworks:** FastAPI • Django • Flask

Since v2.0.0, `ledger-sdk` is a thin distribution of the official
[`opentelemetry-python`](https://github.com/open-telemetry/opentelemetry-python) SDK: real
`TracerProvider`/`LoggerProvider`, OTLP/HTTP export, standard semantic-convention attributes —
plus Python-specific enhancements (exception capture, endpoint monitoring, log↔trace correlation,
attribute truncation) layered on top. Upgrading from 1.x? See [CHANGELOG.md](CHANGELOG.md#200---2026-07-07)
for the full migration guide.

---

## Installation

```bash
pip install ledger-sdk
```

## Setup

> Prefer a guided, tab-by-tab walkthrough (basic • metrics • tracing • OpenTelemetry) with
> copy buttons? See **[ledger.jtuta.cloud/how-to-setup](https://ledger.jtuta.cloud/how-to-setup)**.

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
    flush_interval=5.0,             # Seconds between log/span flushes
    flush_size=1000,                # Logs before auto-flush
    max_buffer_size=10000,          # Max logs buffered in memory
    trace_sample_rate=0.1,          # Fraction of traces sampled (0.0-1.0), default 0.1
    metrics_export_interval=60.0,   # Seconds between metric exports, default 60.0
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

## Capturing the visitor's IP behind a proxy

By default, the SDK only trusts the direct TCP peer address — the socket it actually received the
connection from. If your app sits behind a reverse proxy or load balancer (nginx, an ingress
controller, a cloud load balancer), that peer address is the proxy, not the visitor, and
`X-Forwarded-For`/`X-Real-IP`/`CF-Connecting-IP` headers are ignored entirely. Endpoint logs will
show the proxy's (truncated) address and country will stay empty.

Two things both have to be true to fix it:

1. **Your reverse proxy must forward the header.** Most don't by default. For nginx:

   ```nginx
   location / {
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_pass http://your_app;
   }
   ```

2. **`trusted_proxies` must be set to the address range your app actually receives connections
   from** — i.e. the proxy's own address as seen by your app, not the visitor's:

   ```python
   app.add_middleware(
       LedgerMiddleware,
       ledger_client=ledger,
       trusted_proxies=["10.0.0.0/8"],  # replace with your proxy's actual address range
   )
   ```

The SDK reads `X-Forwarded-For` right-to-left and only trusts the header at all once the direct
peer is itself inside `trusted_proxies` — a proxy appends to the header rather than rewriting it,
so a forged entry earlier in the chain is never reached. Never set `trusted_proxies=["0.0.0.0/0"]`:
that trusts every hop, including attacker-controlled ones, which is worse than leaving it unset.

If you get the range wrong, you don't have to guess: the SDK logs a one-time warning naming the
address it actually observed, so you can copy it straight into `trusted_proxies`.

---

## Distributed Tracing

Tracing is enabled automatically when you create a `LedgerClient` — it registers a real
OpenTelemetry `TracerProvider` as the process-global tracer provider. Traces appear in Ledger's
**Trace List** panel on the dashboard.

```python
from ledger import LedgerClient, get_tracer

ledger = LedgerClient(api_key="...", base_url="...", service_name="my-service")
tracer = get_tracer(__name__)
```

`ledger.tracer` is also available directly on the client instance once constructed.

### Manual spans

```python
with tracer.start_as_current_span("process-order", attributes={"order_id": 42}) as span:
    result = process_order(42)
    span.set_attribute("status", result.status)
```

### Cross-service propagation

Ledger uses the standard OpenTelemetry propagation API (`opentelemetry.propagate`), so
`requests`/`httpx` calls are instrumented automatically once you call `install()`:

```python
import ledger.integrations.requests as ledger_requests

ledger_requests.install()  # every requests.Session.send() now propagates traceparent
```

To propagate manually:

```python
import opentelemetry.propagate as propagate

with tracer.start_as_current_span("outgoing-call"):
    headers = {}
    propagate.inject(headers)
    response = httpx.get("https://downstream/api", headers=headers)
```

Extract context in the downstream service:

```python
import opentelemetry.propagate as propagate

ctx = propagate.extract(request.headers)
with tracer.start_as_current_span("downstream-handler", context=ctx):
    ...
```

Any log emitted inside an active span automatically includes `trace_id` and `span_id`, linking logs to traces in the dashboard.

### FastAPI auto-instrumentation

With `LedgerMiddleware`, every request automatically becomes a root span. Spans created inside request handlers are nested under it:

```python
@app.get("/orders/{id}")
async def get_order(id: int):
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("db-fetch", attributes={"order_id": id}):
        return await db.get_order(id)
```

---

## Standard library logging bridge

Forward every `logging.getLogger(...)` call — yours or a third-party library's — to Ledger
alongside SDK-native logs:

```python
ledger = LedgerClient(api_key="...")
ledger.instrument_logging()

import logging
logging.getLogger(__name__).warning("this reaches Ledger too")
```

---

## Global exception capture

Catch uncaught exceptions across threads and asyncio tasks with one call:

```python
ledger = LedgerClient(api_key="...")
ledger.capture_uncaught()
```

Chains to any previously-installed `sys.excepthook`/`threading.excepthook`/asyncio exception
handler rather than replacing them — safe to call alongside a debugger or another monitoring tool.
Idempotent (calling it twice doesn't double-log).

---

## `before_send` hook & PII scrubbing

Mutate or drop log records right before export:

```python
def redact(record: dict) -> dict | None:
    if record["attributes"].get("internal"):
        return None  # drop internal-only logs entirely
    record["attributes"].pop("session_cookie", None)
    return record

ledger = LedgerClient(api_key="...", before_send=redact)
```

Or turn on the built-in scrubbers (redacts common PII: emails, credit-card-like digit sequences,
`Authorization`/`X-API-Key`-shaped attributes, and any attribute key containing
`password`/`secret`/`token`/`api_key`):

```python
ledger = LedgerClient(api_key="...", scrub_pii=True)
```

Both together: built-in scrubbers run first, then your `before_send` hook.

---

## loguru / structlog sinks

```bash
pip install "ledger-sdk[loguru]"   # or [structlog], or [all]
```

```python
# loguru
from ledger.integrations.loguru import add_loguru_sink
from loguru import logger as loguru_logger

add_loguru_sink(ledger)
loguru_logger.info("this reaches Ledger too")
```

```python
# structlog
import structlog
from ledger.integrations.structlog import ledger_structlog_processor

structlog.configure(processors=[ledger_structlog_processor(ledger), structlog.processors.JSONRenderer()])
```

---

## Custom metrics

```python
ledger.metric_increment("orders_processed", tags={"region": "eu"})
ledger.metric_gauge("queue_depth", 42)
ledger.metric_histogram("request_duration_ms", 123.4, tags={"route": "/api"})

# Or the standard OTel Meter API for full control
meter = ledger.get_meter("my-service")
meter.create_counter("requests").add(1, {"route": "/health"})
```

Counters and histograms export with **delta** temporality, so each export carries what happened
since the last one rather than a running total. Gauges report their current value.

Chart what you send on a **Metric** panel in the web app, or read it back over the API:
`GET /api/v1/metrics/names` lists the metric names a project has sent,
`/api/v1/metrics/{name}/tags` lists a metric's tag keys and values, and
`/api/v1/metrics/{name}/series` returns a bucketed time series grouped by the tags you chose.
See the [API reference](https://bump.sh/tuta-corp/doc/ledger-api/) for the full parameter list.

---

## Uptime monitors (heartbeat)

Ping a dead-man's-switch monitor at the end of a cron job or scheduled task:

```python
ledger.heartbeat("YOUR_MONITOR_TOKEN")
```

Plain synchronous HTTP call, no OTel pipeline involved — safe to call from short-lived scripts
that exit right after. Raises `RuntimeError` on failure so a failed ping doesn't silently vanish.

---

## OpenTelemetry environment variables

The underlying OTel exporters honor the standard `OTEL_EXPORTER_OTLP_*` environment variables, so
you can override the endpoint or add extra headers without touching application code:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://ledger-server.jtuta.cloud"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer ledger_proj_1_your_api_key"
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
- [Setup Guide](https://ledger.jtuta.cloud/how-to-setup)
- [Examples](examples/)
- [Changelog](CHANGELOG.md)

## License

MIT License — see [LICENSE](LICENSE) for details.
