<div align="center">

# Ledger SDK

**Observability for developers who just want to ship.**

[![Python SDK](https://img.shields.io/badge/python-v1.7.0-blue.svg)](https://pypi.org/project/ledger-sdk/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[Dashboard](https://ledger.jtuta.cloud) • [Backend](https://github.com/JakubTuta/Ledger-APP) • [Web UI](https://github.com/JakubTuta/Ledger-WEB) • [API Docs](https://bump.sh/tuta-corp/doc/ledger-api/)

</div>

---

Add one line of code. Get automatic request logging, exception tracking, and performance monitoring.

```python
app.add_middleware(LedgerMiddleware, ledger_client=ledger)
```

Every request, response, and exception is now logged to your Ledger dashboard.

## Why Ledger

- **Zero overhead** — Less than 0.1ms per request
- **Works out of the box** — No configuration files, no dashboards to build
- **Automatic error grouping** — Like Sentry, but free and self-hosted
- **Distributed tracing** — W3C-compatible spans across services
- **Production-ready** — Built-in retry logic, rate limiting, and graceful failure handling

## Installation

```bash
pip install ledger-sdk
```

Supports **FastAPI**, **Django**, and **Flask**.

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
from ledger import LedgerClient

LEDGER_CLIENT = LedgerClient(
    api_key="ledger_proj_1_your_api_key",
    base_url="https://ledger-server.jtuta.cloud"
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

[Full Python SDK docs](python/) • [Get API key](https://ledger.jtuta.cloud) • [Examples](python/examples/)

## Links

- [PyPI Package](https://pypi.org/project/ledger-sdk/)
- [Dashboard](https://ledger.jtuta.cloud)
- [API Reference](https://bump.sh/tuta-corp/doc/ledger-api/)

## License

MIT License — see [LICENSE](LICENSE) for details.
