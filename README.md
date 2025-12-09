# Ledger

**Observability for developers who just want to ship.**

Add one line of code. Get automatic request logging, exception tracking, and performance monitoring. No configuration required.

```python
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware

app.add_middleware(LedgerMiddleware, ledger_client=ledger)
```

That's it. Every request, response, and exception is now logged to your Ledger dashboard.

[![Python SDK](https://img.shields.io/badge/python-v1.2.1-blue.svg)](https://pypi.org/project/ledger-sdk/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/badge/production-ready-brightgreen.svg)]()

## Why Ledger?

Traditional observability tools are complicated, expensive, and slow down your application. Ledger is different:

- **Actually zero overhead** - Less than 0.1ms per request. Your users won't notice.
- **Works out of the box** - No configuration files, no setup guides, no dashboards to build.
- **Production-ready from day one** - Built-in retry logic, rate limiting, and graceful failure handling.

We built Ledger because we were tired of spending hours setting up logging infrastructure for every new project. Now it takes one line of code.

## Available Now

**Python SDK** (v1.2.1) - [Install from PyPI](https://pypi.org/project/ledger-sdk/)

Supports:

- **FastAPI** - Async-first framework
- **Django** - Full-stack web framework
- **Flask** - Lightweight WSGI framework

Coming soon: Express, and more.

Want support for your framework? [Open an issue](https://github.com/JakubTuta/Ledger-SDK/issues) and let us know.

## Quick Start

```bash
pip install ledger-sdk
```

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
from ledger import LedgerClient

LEDGER_CLIENT = LedgerClient(
    api_key="ledger_proj_1_your_api_key",
    base_url="https://ledger-server.jtuta.cloud"
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

[Full documentation](python/) • [Get API key](https://ledger.jtuta.cloud) • [Examples](python/examples/)

## What You Get

**Automatic capture** - Every request, response, and exception. No manual logging code.

**Full context** - Stack traces, request headers, response bodies, user attributes. Everything you need to debug.

**Performance insights** - Response times, error rates, slow endpoints. Know where to optimize.

**Production reliability** - Automatic retries, rate limiting, and graceful degradation. Works even when your network doesn't.

**Zero performance impact** - All logging happens in the background. Your API stays fast.

## How It Works

Ledger captures logs in your application (<0.1ms), buffers them in memory, and sends batches to the Ledger server in the background. Your application never waits for network I/O.

If the server is down or slow, the SDK automatically retries with backoff. If it's really stuck, it drops old logs to prevent memory issues. You get observability without the risk.

[Architecture details](sdk_overview/ARCHITECTURE.md) • [Performance benchmarks](sdk_overview/PERFORMANCE.md)

## Need Help?

- [Read the docs](python/) - Full guides and examples
- [Open an issue](https://github.com/JakubTuta/Ledger-SDK/issues) - Bug reports and feature requests
- [View examples](python/fastapi/examples/) - See it in action

## Links

- [PyPI Package](https://pypi.org/project/ledger-sdk/) - Install the SDK
- [Dashboard](https://ledger.jtuta.cloud) - View your logs
- [API Server](https://ledger-server.jtuta.cloud) - Server endpoint
- [Backend Source](https://github.com/JakubTuta/Ledger-APP) - API server code
- [Frontend Source](https://github.com/JakubTuta/Ledger-WEB) - Dashboard code

## License

MIT License - see [LICENSE](LICENSE) for details.
