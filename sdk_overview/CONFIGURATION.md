# Configuration Guide

How to tune Ledger for your workload.

## The Defaults Work for Most Apps

The SDK comes with sensible defaults that work for typical web APIs:

```python
ledger = LedgerClient(
    api_key="ledger_proj_1_your_key",
    base_url="https://ledger-server.jtuta.cloud"
)
```

That's usually all you need.

## When to Customize

Only tune these settings if you're experiencing issues or have unusual requirements:

### High-Traffic APIs (>1000 requests/sec)

```python
ledger = LedgerClient(
    api_key="...",
    flush_interval=2.0,        # Send logs more often
    flush_size=500,             # Bigger batches
    max_buffer_size=50000,      # More memory for buffering
)
```

This helps the SDK keep up with high request volumes.

### Low-Traffic APIs (<100 requests/sec)

```python
ledger = LedgerClient(
    api_key="...",
    flush_interval=10.0,        # Send logs less often
    flush_size=50,               # Smaller batches
    max_buffer_size=1000,        # Less memory usage
)
```

This reduces resource usage when you don't need high throughput.

### Development/Testing

```python
ledger = LedgerClient(
    api_key="...",
    base_url="http://localhost:8000",
    flush_interval=1.0,          # See logs quickly
    debug=True,                  # Print debug info to console
)
```

This gives you faster feedback when debugging.

## Configuration Options

### Basic Settings

**api_key** (required) - Your Ledger API key. Get one from the [dashboard](https://ledger.jtuta.cloud).

**base_url** (default: `http://localhost:8000`) - URL of the Ledger server.

### Buffer Settings

**flush_interval** (default: `5.0`) - Seconds between sending batches. Lower = logs appear faster, but more network requests.

**flush_size** (default: `1000`) - Send a batch when this many logs accumulate. Lower = logs appear faster, but more network requests.

**max_buffer_size** (default: `10000`) - Max logs to keep in memory. If exceeded, oldest logs are dropped.

### HTTP Settings

**http_timeout** (default: `5.0`) - Seconds to wait for server response.

**http_pool_size** (default: `10`) - Number of HTTP connections to maintain.

### Middleware Settings

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"],  # Don't log these paths
)
```

## Environment Variables

You can configure via environment variables instead:

```bash
export LEDGER_API_KEY="ledger_proj_1_your_key"
export LEDGER_BASE_URL="https://ledger-server.jtuta.cloud"
export LEDGER_FLUSH_INTERVAL="5.0"
```

Then:

```python
ledger = LedgerClient()  # Reads from environment
```

Constructor arguments override environment variables.

## Monitoring Configuration

Check if your settings are working well:

```python
metrics = ledger.get_metrics()

print(f"Buffered logs: {metrics['buffer']['current_size']}")
print(f"Dropped logs: {metrics['buffer']['total_dropped']}")
print(f"Failed flushes: {metrics['flusher']['failed_flushes']}")
```

**Warning signs:**

- `total_dropped` increasing = Buffer is too small or Ledger server is slow
- `failed_flushes` increasing = Network or server issues
- `current_size` always near `max_size` = You might need a bigger buffer

## Troubleshooting

### Logs not appearing

1. Check your API key is correct
2. Verify network connectivity to Ledger server
3. Enable debug mode: `LedgerClient(debug=True)`
4. Check metrics: `ledger.get_metrics()`

### High memory usage

Reduce `max_buffer_size` or increase `flush_interval`.

### Logs appearing slowly

Decrease `flush_interval` or `flush_size`.

## Next Steps

- [PERFORMANCE.md](PERFORMANCE.md) - Performance implications of settings
- [ERROR_HANDLING.md](ERROR_HANDLING.md) - What happens when things fail
