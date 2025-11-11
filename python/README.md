# Ledger SDK for Python

**Production-ready observability SDK with zero-overhead logging for FastAPI, Flask, and Django applications.**

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
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
    base_url="https://api.ledger.example.com"
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

That's it! All requests are now automatically logged to Ledger.

## Features

### Core Features

- Automatic request/response logging via middleware
- Automatic exception capture with full stack traces
- Non-blocking async operation (<0.1ms overhead)
- Intelligent batching and buffering (every 5s or 1000 logs)
- Dual rate limiting (per-minute and per-hour)

### Production Features

- Circuit breaker pattern (5 failure threshold, 60s timeout)
- Exponential backoff retry logic (max 3 retries)
- Comprehensive metrics and monitoring
- Health checks and diagnostics
- Configuration validation on startup
- Enhanced validation with detailed warnings
- Structured logging to stderr
- Graceful shutdown with connection draining

## Usage Examples

### Basic Logging

```python
from ledger import LedgerClient

ledger = LedgerClient(
    api_key="ldg_proj_1_your_api_key",
    base_url="https://api.ledger.example.com"
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

### Flask Integration (Coming Soon)

```python
from flask import Flask
from ledger import LedgerClient
from ledger.integrations.flask import LedgerMiddleware

app = Flask(__name__)
ledger = LedgerClient(api_key="ldg_proj_1_your_api_key")

app.wsgi_app = LedgerMiddleware(app.wsgi_app, ledger_client=ledger)

@app.route("/")
def index():
    ledger.log_info("Homepage visited")
    return {"message": "Hello World"}
```

### Django Integration (Coming Soon)

```python
# settings.py
MIDDLEWARE = [
    'ledger.integrations.django.LedgerMiddleware',
    # ... other middleware
]

LEDGER_CONFIG = {
    'api_key': 'ldg_proj_1_your_api_key',
    'base_url': 'https://api.ledger.example.com',
}

# views.py
from ledger import get_ledger_client

def my_view(request):
    ledger = get_ledger_client()
    ledger.log_info("View accessed", attributes={"path": request.path})
    return HttpResponse("Hello World")
```

### Background Workers (Celery/RQ)

```python
from celery import Celery
from ledger import LedgerClient

app = Celery('tasks')
ledger = LedgerClient(
    api_key="ldg_proj_1_your_api_key",
    flush_interval=30.0,
    flush_size=1000
)

@app.task
def process_payment(payment_id):
    ledger.log_info(f"Processing payment {payment_id}", attributes={"payment_id": payment_id})

    try:
        # Process payment logic
        ledger.log_info(f"Payment {payment_id} processed successfully")
    except Exception as e:
        ledger.log_exception(e, message=f"Payment {payment_id} failed")
        raise
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
export LEDGER_BASE_URL="https://api.ledger.example.com"
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
              value: "https://api.ledger.example.com"
```

## Documentation

- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Migration from old structure
- [Architecture](../sdk_overview/ARCHITECTURE.md) - System design and data flow
- [Components](../sdk_overview/COMPONENTS.md) - Internal component details
- [FastAPI Integration](../sdk_overview/FASTAPI_INTEGRATION.md) - FastAPI middleware guide
- [Performance](../sdk_overview/PERFORMANCE.md) - Performance tuning guide
- [Error Handling](../sdk_overview/ERROR_HANDLING.md) - Error handling strategies
- [Configuration](../sdk_overview/CONFIGURATION.md) - Full configuration reference

## Troubleshooting

### High Buffer Utilization

**Symptom**: Buffer utilization >90%

**Cause**: Logs not being sent fast enough

**Solution**:

- Check network connectivity to Ledger server
- Increase `flush_interval` to flush more frequently
- Reduce traffic or increase rate limits

### Circuit Breaker Open

**Symptom**: `circuit_breaker_open: true` in health status

**Cause**: Too many consecutive failures (5+)

**Solution**:

- Check Ledger server health and availability
- Verify API key is valid
- Check network connectivity
- Review stderr logs for error details

### Logs Not Appearing

**Symptom**: Logs not showing up in Ledger

**Solution**:

1. Check API key is valid and starts with `ldg_`
2. Verify `base_url` is correct
3. Check network connectivity
4. Enable debug logging to stderr
5. Check metrics: `ledger.get_metrics()`

### Memory Usage Growing

**Symptom**: Application memory increasing over time

**Cause**: Buffer not being flushed

**Solution**:

- Check background flusher is running
- Verify network connectivity
- Check for rate limiting (429 errors)
- Reduce `max_buffer_size` if needed

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/JakubTuta/ledger-sdk/issues)
- **Documentation**: [Full documentation](../sdk_overview/)
- **Examples**: [See examples/](examples/)

## Links

- **PyPI**: https://pypi.org/project/ledger-sdk/
- **GitHub**: https://github.com/JakubTuta/ledger-sdk
- **Documentation**: https://docs.ledger.example.com
- **Homepage**: https://ledger.example.com

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## FAQ

### Is the SDK thread-safe?

Yes, all operations are thread-safe and async-safe.

### What happens if the Ledger server is down?

The SDK will buffer logs in memory (up to `max_buffer_size`) and retry with exponential backoff. After 5 consecutive failures, the circuit breaker opens and stops sending requests for 60 seconds before retrying.

### Will the SDK slow down my application?

No. The middleware adds <0.1ms overhead per request. All network I/O happens asynchronously in a background task.

### How do I rotate API keys?

Update the environment variable and restart your application. The SDK validates the API key format on initialization.

### Can I use this with sync frameworks (Flask, Django)?

Flask and Django support is planned for v1.1. Currently only FastAPI (async) is supported.

### What Python versions are supported?

Python 3.9, 3.10, 3.11, and 3.12 are officially supported and tested in CI.

### How much memory does the SDK use?

Approximately 8-12MB with default settings (10,000 log buffer). Memory usage scales with `max_buffer_size`.

### Can I customize the log format?

Yes, use the `attributes` parameter to add custom fields:

```python
ledger.log_info("User action", attributes={"user_id": 123, "action": "login"})
```

### How do I test locally without a Ledger server?

Run the Ledger server locally and use the setup script:

```bash
python scripts/setup_test_account.py
```

## Changelog

### v1.0.0 (2024-11-10)

**Production Release**

- Circuit breaker pattern (5 failure threshold, 60s timeout)
- Exponential backoff retry logic (max 3 retries)
- Dual rate limiting (per-minute and per-hour)
- Comprehensive metrics and health checks
- Configuration validation on startup
- Enhanced validation with warnings
- Graceful shutdown with connection draining
- FastAPI middleware integration
- Automatic exception capture
- Non-blocking async operation

## License

MIT License - see [LICENSE](LICENSE) for details
