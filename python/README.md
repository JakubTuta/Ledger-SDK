# Ledger SDK for Python

**Observability for developers who just want to ship.**

Add one line of code. Get automatic request logging, exception tracking, and performance monitoring. No configuration required.

```python
from ledger.integrations.fastapi import LedgerMiddleware

app.add_middleware(LedgerMiddleware, ledger_client=ledger)
```

That's it. Every request, response, and exception is now logged to your Ledger dashboard.

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI Version](https://img.shields.io/badge/pypi-v1.2.0-blue.svg)](https://pypi.org/project/ledger-sdk/)
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
