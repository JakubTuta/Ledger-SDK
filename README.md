# Ledger

**Modern, production-ready observability platform with zero-overhead SDKs for every language and framework.**

[![Python SDK](https://img.shields.io/badge/python-production--ready-brightgreen.svg)](python/fastapi/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()

## Mission

Ledger provides developers with **effortless observability** through automatic request/response logging, exception tracking, and performance monitoring across all major languages and frameworks. Our goal is to make observability as simple as adding a single line of code, with zero performance impact on production applications.

## Vision

Modern applications span multiple languages and frameworks. Ledger SDKs provide consistent, production-grade observability across your entire stack with:

- **Zero overhead**: <0.1ms per request
- **Zero configuration**: Works out of the box with sensible defaults
- **Zero maintenance**: Automatic retries, circuit breakers, and health monitoring built-in

## Project Status

### ✅ Production Ready

- **[Python SDK](python/fastapi/)** - FastAPI integration (v1.0.0)
  - Automatic request/response logging
  - Exception tracking with stack traces
  - Circuit breaker pattern
  - Dual rate limiting (per-minute and per-hour)
  - Comprehensive health checks and metrics

### 🚧 Coming Soon

- **Python SDK** - Flask integration (v1.1)
- **Python SDK** - Django integration (v1.2)
- **Node.js SDK** - Express, Fastify, NestJS

## Quick Start

### Python (FastAPI)

```bash
pip install ledger-sdk
```

```python
from fastapi import FastAPI
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware

app = FastAPI()

ledger = LedgerClient(
    api_key="ldg_proj_1_your_api_key",
    base_url="https://api.ledger.example.com"
)

app.add_middleware(LedgerMiddleware, ledger_client=ledger)

@app.on_event("shutdown")
async def shutdown():
    await ledger.shutdown()
```

See [Python SDK Documentation](python/fastapi/) for complete guide.

## Features

### Core Capabilities

- **Automatic Logging**: Request/response capture via middleware
- **Exception Tracking**: Full stack traces with context
- **Performance Monitoring**: Request duration, status codes, error rates
- **Custom Events**: Manual logging with structured attributes

### Production Features

- **Circuit Breaker**: Automatic failure detection and recovery
- **Exponential Backoff**: Smart retry logic for transient failures
- **Rate Limiting**: Client-side rate limiting (per-minute and per-hour)
- **Health Checks**: Built-in health and metrics endpoints
- **Graceful Shutdown**: Connection draining and buffer flushing

### Developer Experience

- **Zero Overhead**: <0.1ms overhead per request
- **Non-Blocking**: All I/O happens asynchronously
- **Type Safe**: Full type hints and IDE support
- **Observable**: Built-in metrics and diagnostics
- **Configurable**: Tune for any workload (high-volume, low-latency, background workers)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Application                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Ledger SDK Middleware                   │  │
│  │  • Captures requests/responses (<0.1ms overhead)     │  │
│  │  • Adds to buffer (non-blocking, O(1))              │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Background Flusher (Async Task)             │  │
│  │  • Batches logs (every 5s or 1000 logs)             │  │
│  │  • Rate limiting (client-side)                       │  │
│  │  • Circuit breaker (5 failures → 60s timeout)        │  │
│  │  • Exponential backoff (2s, 4s, 8s)                 │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS
                            ▼
            ┌──────────────────────────────┐
            │      Ledger Server API       │
            │  • /api/v1/ingest/batch      │
            │  • Rate limiting (1000/min)  │
            │  • Queue management          │
            └──────────────────────────────┘
                            │
                            ▼
            ┌──────────────────────────────┐
            │       Ledger Platform        │
            │  • Log storage & indexing    │
            │  • Search & analytics        │
            │  • Alerting & dashboards     │
            └──────────────────────────────┘
```

## Design Principles

1. **Zero Overhead**: SDK operations never slow down your application
2. **Fail Gracefully**: Buffer → Retry → Drop (only as last resort)
3. **Respect Limits**: Client-side rate limiting and batch size constraints
4. **Observable**: Built-in metrics and health checks for debugging
5. **Configurable**: Tune behavior for different workloads
6. **Future-Proof**: Architecture designed for multi-language expansion

## Support

### Getting Help

- **Documentation**: [SDK Overview](sdk_overview/)
- **GitHub Issues**: [Report bugs or request features](https://github.com/JakubTuta/ledger-sdk/issues)
- **Discussions**: [Ask questions](https://github.com/JakubTuta/ledger-sdk/discussions)
- **Examples**: [See examples/](python/fastapi/examples/)

### Reporting Issues

When reporting issues, include:

- SDK version and language
- Framework and version
- Minimal reproduction code
- Expected vs actual behavior
- SDK metrics output (if applicable)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with inspiration from:

- **Sentry** - Error tracking and monitoring
- **Datadog** - APM and observability
- **OpenTelemetry** - Observability standards
- **httpx** - Modern HTTP client architecture
- **FastAPI** - Performance and developer experience
