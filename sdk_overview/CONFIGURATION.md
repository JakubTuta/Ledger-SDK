# SDK Configuration

Complete configuration reference for the Ledger SDK.

## Initialization Options

```python
from ledger import LedgerClient

client = LedgerClient(
    # Required
    api_key: str,                      # Ledger API key

    # Server
    base_url: str = "https://api.ledger.example.com",

    # Performance
    flush_interval: float = 5.0,       # Seconds between flushes
    flush_size: int = 100,             # Logs before auto-flush
    max_buffer_size: int = 10000,      # Max logs in memory

    # HTTP Client
    http_timeout: float = 5.0,         # Request timeout (seconds)
    http_pool_size: int = 10,          # Connection pool size

    # Rate Limiting
    rate_limit_buffer: float = 0.9,    # Use 90% of server limit

    # Retry Behavior
    max_retries: int = 3,              # For 5xx errors
    retry_backoff_base: float = 1.0,   # Exponential backoff base

    # Features
    capture_stack_traces: bool = True, # For exceptions only

    # Debug
    debug: bool = False,               # Log to stderr
    log_level: str = "WARNING"         # DEBUG, INFO, WARNING, ERROR
)
```

## Configuration by Use Case

### Production API (Default)

**Use case**: Standard production API server

```python
ledger = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY"),
    base_url="https://api.ledger.example.com",
    flush_interval=5.0,
    flush_size=100,
    max_buffer_size=10000
)
```

**Characteristics**:

- Balanced performance/latency
- ~10MB memory overhead
- Flushes every 5s or 100 logs

---

### High-Volume API

**Use case**: API handling >1000 req/sec

```python
ledger = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY"),
    flush_interval=2.0,       # Flush sooner
    flush_size=500,           # Larger batches
    max_buffer_size=50000,    # More memory
    http_pool_size=20,        # More connections
    rate_limit_buffer=0.95    # Use more of rate limit
)
```

**Characteristics**:

- Higher throughput
- ~50MB memory overhead
- Flushes every 2s or 500 logs

---

### Low-Volume API

**Use case**: API handling <100 req/sec

```python
ledger = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY"),
    flush_interval=10.0,      # Flush less often
    flush_size=50,            # Smaller batches
    max_buffer_size=1000,     # Less memory
    http_pool_size=5          # Fewer connections
)
```

**Characteristics**:

- Lower resource usage
- ~1MB memory overhead
- Flushes every 10s or 50 logs

---

### Development/Testing

**Use case**: Local development, debugging

```python
ledger = LedgerClient(
    api_key="ldg_proj_1_test...",
    base_url="http://localhost:8000",
    flush_interval=1.0,       # Flush quickly (see logs sooner)
    flush_size=10,            # Small batches
    debug=True,               # Enable debug logging
    log_level="DEBUG"         # Verbose output
)
```

**Characteristics**:

- Low latency (see logs quickly)
- Verbose stderr output
- Easy debugging

---

### Background Workers (Celery, RQ)

**Use case**: Async task processing

```python
ledger = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY"),
    flush_interval=30.0,      # Very lazy flushing
    flush_size=1000,          # Max batch size
    max_buffer_size=10000,
    http_timeout=10.0         # Longer timeout (workers can wait)
)
```

**Characteristics**:

- Efficient batching
- Low API call frequency
- Can tolerate higher latency

---

## Environment Variables

The SDK supports configuration via environment variables:

```bash
# Required
export LEDGER_API_KEY="ldg_proj_1_abc123..."

# Optional
export LEDGER_BASE_URL="https://api.ledger.example.com"
export LEDGER_FLUSH_INTERVAL="5.0"
export LEDGER_FLUSH_SIZE="100"
export LEDGER_MAX_BUFFER_SIZE="10000"
export LEDGER_DEBUG="false"
```

**Priority**: Constructor args > Environment variables > Defaults

**Usage**:

```python
# Automatically reads from environment
ledger = LedgerClient()  # Uses LEDGER_API_KEY from env

# Override with constructor
ledger = LedgerClient(api_key="custom_key")  # Ignores env var
```

---

## Middleware Configuration

### FastAPI

```python
from ledger.integrations.fastapi import LedgerMiddleware

app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,

    # Path Filtering
    exclude_paths=["/health", "/metrics"],
    include_paths=None,  # If set, only log these paths

    # Privacy
    capture_request_body=False,
    capture_response_body=False,
    capture_headers=False,
    capture_query_params=True,

    # Custom Attributes
    extra_attributes={"service": "payment-api"},
)
```

**Path filtering examples**:

```python
# Exclude health checks
exclude_paths=["/health", "/ping", "/metrics"]

# Exclude regex patterns (future)
exclude_patterns=[r"/static/.*", r"/assets/.*"]

# Include only API endpoints
include_paths=["/api/*"]
```

---

## Dynamic Configuration

### Runtime Configuration Changes

```python
# Change flush interval at runtime
ledger.set_flush_interval(10.0)

# Change batch size
ledger.set_flush_size(500)

# Update rate limits (after fetching new settings)
await ledger.refresh_settings()
```

### Conditional Logging

```python
# Only log errors in production
if os.getenv("ENVIRONMENT") == "production":
    middleware_options = {"capture_only_errors": True}
else:
    middleware_options = {}

app.add_middleware(LedgerMiddleware, ledger_client=ledger, **middleware_options)
```

---

## Advanced Configuration

### Health Monitoring

```python
# Quick health check
if not ledger.is_healthy():
    print("SDK is unhealthy!")

# Detailed health status
status = ledger.get_health_status()
# Returns: {
#   "status": "healthy" | "degraded" | "unhealthy",
#   "healthy": bool,
#   "issues": ["Circuit breaker open", ...] or None,
#   "buffer_utilization_percent": 42.5,
#   "circuit_breaker_open": false,
#   "consecutive_failures": 0
# }

# Comprehensive metrics
metrics = ledger.get_metrics()
# Returns comprehensive metrics from all SDK components
```

### FastAPI Health Endpoints

```python
@app.get("/sdk/health")
async def sdk_health():
    return ledger.get_health_status()

@app.get("/sdk/metrics")
async def sdk_metrics():
    return ledger.get_metrics()
```

---

## Validation & Constraints

Settings are hardcoded with production defaults (no server fetch required):

```python
# Hardcoded production constraints
{
    "max_message_length": 10000,
    "max_error_message_length": 5000,
    "max_stack_trace_length": 50000,
    "max_attributes_size_bytes": 102400,
    "max_batch_size": 1000
}
```

**Configuration Validation**:
All configuration parameters are validated on initialization:

```python
try:
    ledger = LedgerClient(
        api_key="invalid_key",  # Must start with 'ldg_'
        flush_interval=-1       # Must be positive
    )
except ValueError as e:
    # Raises: "Invalid Ledger SDK configuration:
    #          - api_key must start with 'ldg_' prefix
    #          - flush_interval must be positive, got -1"
    pass
```

---

## Performance Tuning

### Optimize for Throughput

**Goal**: Send as many logs as possible

```python
ledger = LedgerClient(
    flush_interval=1.0,       # Flush very often
    flush_size=1000,          # Max batch size
    max_buffer_size=100000,   # Large buffer
    http_pool_size=50         # Many connections
)
```

**Trade-offs**:

- Higher memory usage (~100MB)
- More API calls
- Lower latency (logs appear faster)

### Optimize for Resource Efficiency

**Goal**: Minimize memory and API calls

```python
ledger = LedgerClient(
    flush_interval=30.0,      # Flush rarely
    flush_size=1000,          # Max batch size
    max_buffer_size=1000,     # Small buffer
    http_pool_size=2          # Minimal connections
)
```

**Trade-offs**:

- Lower memory usage (~1MB)
- Fewer API calls
- Higher latency (logs appear slower)

### Optimize for Low Latency

**Goal**: See logs in Ledger ASAP

```python
ledger = LedgerClient(
    flush_interval=0.5,       # Flush every 500ms
    flush_size=10,            # Small batches
    max_buffer_size=1000,
    http_pool_size=10
)
```

**Trade-offs**:

- More API calls (may hit rate limits)
- More network overhead
- Logs appear very quickly

---

## Monitoring Configuration

```python
# Enable metrics collection
ledger = LedgerClient(
    api_key="...",
    enable_metrics=True,
    metrics_interval=60.0  # Log metrics every 60s
)

# Access metrics
metrics = ledger.get_metrics()
# {
#   "logs_buffered": 150,
#   "logs_sent": 10245,
#   "logs_dropped": 0,
#   "api_calls": 105,
#   "errors": {"429": 2}
# }
```

---

## Configuration Validation

**Automatic validation on initialization**:

```python
try:
    ledger = LedgerClient(
        api_key="invalid_key",
        flush_interval=-1
    )
except ValueError as e:
    # Detailed error message with all validation issues
    print(f"Configuration error: {e}")
    sys.exit(1)
```

**Validation rules**:

- `api_key`: Must be non-empty string starting with `ldg_`
- `base_url`: Must be valid HTTP/HTTPS URL
- `flush_interval`: Must be positive number
- `flush_size`: Must be positive integer
- `max_buffer_size`: Must be positive integer
- `http_timeout`: Must be positive number
- `http_pool_size`: Must be positive integer
- `rate_limit_buffer`: Must be between 0 and 1

**Pros**: Fail fast if misconfigured, no network dependency
**Cons**: Cannot validate API key validity (only format)

---

## Best Practices

1. **Use environment variables** for API keys (don't hardcode)
2. **Start with defaults** and tune only if needed
3. **Enable debug mode** in development
4. **Monitor metrics** in production
5. **Test configuration** in staging before production
6. **Document custom settings** in your project

---

## Configuration Examples

### Example 1: Microservice

```python
# config.py
import os
from ledger import LedgerClient

ledger = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY"),
    flush_interval=5.0,
    max_buffer_size=10000,
    extra_attributes={
        "service": os.getenv("SERVICE_NAME"),
        "version": os.getenv("SERVICE_VERSION"),
        "environment": os.getenv("ENVIRONMENT")
    }
)
```

### Example 2: Kubernetes

```yaml
# deployment.yaml
env:
  - name: LEDGER_API_KEY
    valueFrom:
      secretKeyRef:
        name: ledger-secret
        key: api-key
  - name: LEDGER_FLUSH_INTERVAL
    value: "5.0"
  - name: LEDGER_MAX_BUFFER_SIZE
    value: "10000"
```

### Example 3: Docker Compose

```yaml
# docker-compose.yml
services:
  app:
    environment:
      - LEDGER_API_KEY=${LEDGER_API_KEY}
      - LEDGER_BASE_URL=http://ledger-server:8000
      - LEDGER_DEBUG=true
```

---

## Troubleshooting

### Configuration not applied

**Problem**: Settings don't seem to take effect

**Solution**: Check priority (constructor > env vars > defaults)

### High memory usage

**Problem**: App using too much memory

**Solution**: Reduce `max_buffer_size`

### Logs not appearing

**Problem**: Logs not showing up in Ledger

**Solution**:

1. Enable debug mode
2. Check API key validity
3. Verify network connectivity
4. Check buffer metrics

---

## Next Steps

- See [PERFORMANCE.md](PERFORMANCE.md) for tuning recommendations
- See [ERROR_HANDLING.md](ERROR_HANDLING.md) for retry configuration
