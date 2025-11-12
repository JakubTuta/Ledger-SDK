# Ledger SDK for Python

**Production-ready observability SDK with zero-overhead logging for FastAPI, Flask, and Django applications.**

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI Version](https://img.shields.io/badge/pypi-v1.0.0-blue.svg)](https://pypi.org/project/ledger-sdk/)
[![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)](CHANGELOG.md)

## Overview

Ledger SDK provides automatic request/response logging, exception tracking, and performance monitoring for Python web applications with **zero performance impact** on your request handlers. All logging happens asynchronously in the background with intelligent batching, rate limiting, and circuit breaker protection.

**Key Benefits:**

- **Non-blocking**: <0.1ms overhead per request
- **Production-ready**: Circuit breaker, retry logic, health checks
- **Framework support**: FastAPI, Flask (coming soon), Django (coming soon)
- **Zero configuration**: Works out of the box with sensible defaults
- **Observable**: Built-in metrics, health checks, and diagnostics

## Installation

```bash
# Install with FastAPI support
pip install ledger-sdk[fastapi]

# Or install core only
pip install ledger-sdk
```

## Quick Start

### FastAPI

```python
from fastapi import FastAPI
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware

app = FastAPI()

ledger = LedgerClient(
    api_key="ldg_proj_1_your_api_key_here",
    base_url="https://ledger-server.jtuta.cloud"
)

app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"]
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.on_event("shutdown")
async def shutdown():
    await ledger.shutdown()
```

## Features

- Automatic request/response logging via middleware
- Automatic exception capture with full stack traces
- Non-blocking async operation
- Intelligent batching and buffering (every 5s or 1000 logs)
- Dual rate limiting (per-minute and per-hour)

## Usage Examples

### Basic Logging

```python
from ledger import LedgerClient

ledger = LedgerClient(
    api_key="ldg_proj_1_your_api_key",
    base_url="https://ledger-server.jtuta.cloud"
)

ledger.log_info("User logged in", attributes={"user_id": 123, "ip": "192.168.1.1"})

ledger.log_error("Payment failed", attributes={"amount": 99.99, "error_code": "CARD_DECLINED"})

try:
    result = 1 / 0
except Exception as e:
    ledger.log_exception(e, message="Division error in payment calculation")
```

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware

app = FastAPI()
ledger = LedgerClient(api_key="ldg_proj_1_your_api_key")

app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"]
)

@app.get("/user/{user_id}")
async def get_user(user_id: int):
    ledger.log_info(f"Fetching user {user_id}", attributes={"user_id": user_id})

    if user_id == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user_id": user_id, "name": f"User {user_id}"}

@app.on_event("shutdown")
async def shutdown():
    await ledger.shutdown()
```

## Advanced Configuration

### All Configuration Options

```python
from ledger import LedgerClient

ledger = LedgerClient(
    api_key="ldg_proj_1_your_api_key",
    base_url="https://api.ledger.example.com",

    flush_interval=5.0,
    flush_size=1000,
    max_buffer_size=10000,

    http_timeout=5.0,
    http_pool_size=10,

    rate_limit_buffer=0.9
)
```

### High-Volume Configuration

For APIs handling >1000 req/sec:

```python
ledger = LedgerClient(
    api_key="ldg_proj_1_your_api_key",
    flush_interval=2.0,
    flush_size=500,
    max_buffer_size=50000,
    http_pool_size=20,
    rate_limit_buffer=0.95
)
```

### Low-Volume Configuration

For APIs handling <100 req/sec:

```python
ledger = LedgerClient(
    api_key="ldg_proj_1_your_api_key",
    flush_interval=10.0,
    flush_size=50,
    max_buffer_size=1000,
    http_pool_size=5
)
```

## Monitoring & Health Checks

### Health Checks

```python
if ledger.is_healthy():
    print("SDK is healthy")

status = ledger.get_health_status()
```

**Health Status Response:**

```python
{
    "status": "healthy",
    "healthy": true,
    "issues": null,
    "buffer_utilization_percent": 42.5,
    "circuit_breaker_open": false,
    "consecutive_failures": 0
}
```

### Metrics

```python
metrics = ledger.get_metrics()
```

**Metrics Response:**

```python
{
    "sdk": {
        "uptime_seconds": 123.45,
        "version": "1.0.0"
    },
    "buffer": {
        "current_size": 42,
        "max_size": 10000,
        "total_dropped": 0,
        "utilization_percent": 0.42
    },
    "flusher": {
        "total_flushes": 10,
        "successful_flushes": 9,
        "failed_flushes": 1,
        "consecutive_failures": 0,
        "circuit_breaker_open": false
    },
    "rate_limiter": {
        "current_rate": 12,
        "limit_per_minute": 900
    },
    "errors": {
        "network_error": 1,
        "rate_limit": 0
    }
}
```

### Expose Health Endpoints (FastAPI)

```python
@app.get("/sdk/health")
async def sdk_health():
    return ledger.get_health_status()

@app.get("/sdk/metrics")
async def sdk_metrics():
    return ledger.get_metrics()
```

## Performance

The SDK is designed for **zero impact** on your application performance:

| Metric           | Performance |
| ---------------- | ----------- |
| Request overhead | <0.1ms      |
| Background flush | 50-150ms    |
| Memory usage     | 8-12MB      |
| CPU overhead     | <0.5%       |

All logging operations are:

- **Non-blocking**: Logs added to buffer in <0.1ms
- **Asynchronous**: Network I/O happens in background task
- **Batched**: Logs sent in batches (every 5s or 1000 logs)
- **Rate-limited**: Client-side rate limiting prevents 429 errors

## Error Handling

The SDK includes production-grade error handling:

### Circuit Breaker

Automatically stops sending requests after 5 consecutive failures and retries after 60 seconds.

```python
if ledger.get_health_status()["circuit_breaker_open"]:
    print("Circuit breaker is open - too many failures")
```

### Exponential Backoff

Retries failed requests with exponential backoff:

- Server errors (5xx): 2s, 4s, 8s (max 3 retries)
- Network errors: 5s, 10s, 20s (max 3 retries)
- Rate limits (429): Respects `Retry-After` header

### Graceful Degradation

- **Buffer overflow**: Drops oldest logs (FIFO) to prevent memory exhaustion
- **Network failures**: Keeps retrying with backoff
- **Invalid responses**: Logs to stderr and drops batch

## Configuration Reference

| Parameter           | Default                 | Description                         |
| ------------------- | ----------------------- | ----------------------------------- |
| `api_key`           | Required                | Ledger API key (starts with `ldg_`) |
| `base_url`          | `http://localhost:8000` | Ledger server URL                   |
| `flush_interval`    | `5.0`                   | Seconds between flushes             |
| `flush_size`        | `1000`                  | Logs before auto-flush              |
| `max_buffer_size`   | `10000`                 | Max logs in memory                  |
| `http_timeout`      | `5.0`                   | Request timeout (seconds)           |
| `http_pool_size`    | `10`                    | HTTP connection pool size           |
| `rate_limit_buffer` | `0.9`                   | Use 90% of rate limit               |

See [CONFIGURATION.md](../sdk_overview/CONFIGURATION.md) for tuning recommendations.

## Development Setup

### 1. Install in Development Mode

```bash
# Clone the repository
git clone https://github.com/JakubTuta/ledger-sdk.git
cd ledger-sdk/python

# Install with dev dependencies
pip install -e ".[dev]"
```

### 2. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ledger --cov-report=html

# Run specific test
pytest tests/test_client.py
```

### 3. Run Example App

```bash
python examples/basic_app.py
```

Visit http://localhost:8080/docs to test the API.

## Production Deployment

### Deployment Checklist

- [ ] Set production API key as environment variable
- [ ] Configure HTTPS `base_url`
- [ ] Set up monitoring endpoints (`/sdk/health`, `/sdk/metrics`)
- [ ] Configure alerts for circuit breaker and buffer utilization
- [ ] Monitor stderr logs for warnings/errors
- [ ] Load test at expected traffic levels

### Environment Variables

```bash
export LEDGER_API_KEY="ldg_proj_1_your_production_key"
export LEDGER_BASE_URL="https://ledger-server.jtuta.cloud"
```

### Docker Example

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV LEDGER_API_KEY=${LEDGER_API_KEY}
ENV LEDGER_BASE_URL=${LEDGER_BASE_URL}

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
        - name: app
          image: my-app:latest
          env:
            - name: LEDGER_API_KEY
              valueFrom:
                secretKeyRef:
                  name: ledger-secret
                  key: api-key
            - name: LEDGER_BASE_URL
              value: "https://ledger-server.jtuta.cloud"
```

## Documentation

- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- [Architecture](../sdk_overview/ARCHITECTURE.md) - System design and data flow
- [Components](../sdk_overview/COMPONENTS.md) - Internal component details
- [FastAPI Integration](../sdk_overview/FASTAPI_INTEGRATION.md) - FastAPI middleware guide
- [Performance](../sdk_overview/PERFORMANCE.md) - Performance tuning guide
- [Error Handling](../sdk_overview/ERROR_HANDLING.md) - Error handling strategies
- [Configuration](../sdk_overview/CONFIGURATION.md) - Full configuration reference

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/JakubTuta/ledger-sdk/issues)
- **Documentation**: [Full documentation](../sdk_overview/)
- **Examples**: [See examples/](examples/)

## Resources

- **Server Repository**: https://github.com/JakubTuta/Ledger-APP
- **SDK Repository**: https://github.com/JakubTuta/Ledger-SDK
- **Frontend Repository**: https://github.com/JakubTuta/Ledger-WEB
- **PyPI Package**: https://pypi.org/project/ledger-sdk/
- **Production Server**: https://ledger-server.jtuta.cloud
- **Frontend Dashboard**: https://ledger.jtuta.cloud

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/JakubTuta/Ledger-SDK/issues)
- **Server Connection**: See [SERVER.md](../SERVER.md) for API endpoints

## License

MIT License - see [LICENSE](LICENSE) for details
