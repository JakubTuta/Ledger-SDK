<div align="center">

# Ledger SDK

**OpenTelemetry-native observability for developers who just want to ship.**

[![Python SDK](https://img.shields.io/badge/python-v2.0.0-blue.svg)](https://pypi.org/project/ledger-sdk/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[Dashboard](https://ledger.jtuta.cloud) • [Setup Guide](https://ledger.jtuta.cloud/how-to-setup) • [Backend](https://github.com/JakubTuta/Ledger-APP) • [Web UI](https://github.com/JakubTuta/Ledger-WEB) • [API Docs](https://bump.sh/tuta-corp/doc/ledger-api/)

</div>

---

Ledger's server speaks standard **OTLP/HTTP**, so this repo ships the Python SDK — a thin
distribution of the official `opentelemetry-python` SDK with Python-specific enhancements
(exception capture, endpoint monitoring, log↔trace correlation). Any other language can send data
to Ledger with its own stock OpenTelemetry SDK, no Ledger-specific package required — see
[Any OpenTelemetry SDK](#any-opentelemetry-sdk) below.

Add one line of code. Get automatic request logging, exception tracking, and performance monitoring.

```python
app.add_middleware(LedgerMiddleware, ledger_client=ledger)
```

Every request, response, and exception is now logged to your Ledger dashboard.

## Why Ledger

- **OpenTelemetry-native** — real `opentelemetry-python` TracerProvider/LoggerProvider under the hood, OTLP/HTTP export
- **Zero overhead** — Less than 0.1ms per request
- **Works out of the box** — No configuration files, no dashboards to build
- **Automatic error grouping** — Like Sentry, but free and self-hosted
- **Distributed tracing** — W3C-compatible spans across services
- **Any language welcome** — the server accepts standard OTLP from any OTel SDK, not just Python

## Installation

```bash
pip install ledger-sdk
```

Supports **FastAPI**, **Django**, and **Flask**.

## Quick Start

> Full step-by-step walkthrough with copyable snippets for basic setup, metrics, tracing, and
> OpenTelemetry: **[ledger.jtuta.cloud/how-to-setup](https://ledger.jtuta.cloud/how-to-setup)**.

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

[Full Python SDK docs](python/) • [Setup guide](https://ledger.jtuta.cloud/how-to-setup) • [Get API key](https://ledger.jtuta.cloud) • [Examples](python/examples/)

## Any OpenTelemetry SDK

Not using Python? Point any language's stock OpenTelemetry SDK at Ledger — no Ledger package needed:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://ledger-server.jtuta.cloud"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer ledger_proj_1_your_api_key"
```

Then use your language's normal OTel SDK setup (`@opentelemetry/sdk-trace-node`, Go's
`go.opentelemetry.io/otel`, Java's `opentelemetry-sdk`, etc.) — traces, logs, and metrics will all
appear in your Ledger dashboard.

## Links

- [PyPI Package](https://pypi.org/project/ledger-sdk/)
- [Dashboard](https://ledger.jtuta.cloud)
- [Setup Guide](https://ledger.jtuta.cloud/how-to-setup)
- [API Reference](https://bump.sh/tuta-corp/doc/ledger-api/)

## License

MIT License — see [LICENSE](LICENSE) for details.
