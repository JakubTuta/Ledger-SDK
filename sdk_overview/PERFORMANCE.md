# Performance Guide

Why Ledger is fast and how to keep it that way.

## The Numbers

**Request overhead:** Less than 0.1ms per request

**Memory usage:** About 10MB for 10,000 buffered logs

**CPU usage:** Less than 0.5% of one CPU core

Your users won't notice Ledger is there.

## Why It's Fast

### Your Code Never Waits

When the middleware captures a log, it adds it to an in-memory buffer and returns immediately. No network requests, no file writes, no waiting.

The actual sending happens in a separate background task that runs every few seconds.

### Batching Reduces Network Overhead

Instead of sending 1000 separate HTTP requests per second, Ledger sends one batch of 1000 logs every 5 seconds.

This is 200x fewer requests, which means less network overhead, less server load, and fewer chances to hit rate limits.

### Connection Pooling

HTTP connections stay open and get reused. This avoids the overhead of establishing new connections (TCP handshake, TLS negotiation) for every request.

### Async Everything

All I/O uses Python's asyncio, which means a single thread can handle thousands of operations without blocking.

## Keeping It Fast

### Don't Capture Request/Response Bodies

By default, Ledger doesn't capture request or response bodies. If you enable this, your logs will be much larger and slower to send.

Only enable if you really need it:

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    capture_request_body=True,   # Only if needed
    capture_response_body=True,  # Only if needed
)
```

### Exclude Health Check Endpoints

Health check endpoints can generate a lot of noise. Exclude them:

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"],
)
```

### Tune Buffer Settings for Your Traffic

**High traffic?** Increase `flush_size` and `max_buffer_size` to handle bursts.

**Low traffic?** Decrease them to use less memory.

See [CONFIGURATION.md](CONFIGURATION.md) for details.

## Monitoring Performance

Check SDK metrics to see if it's keeping up:

```python
metrics = ledger.get_metrics()

print(f"Logs buffered: {metrics['buffer']['current_size']}")
print(f"Logs dropped: {metrics['buffer']['total_dropped']}")
```

**Good:** `current_size` stays low, `total_dropped` is zero

**Bad:** `current_size` keeps growing, `total_dropped` is increasing

If you're dropping logs, either increase `max_buffer_size` or check if the Ledger server is reachable.

## Common Performance Issues

### High Memory Usage

**Symptom:** Your app's memory usage is higher than expected.

**Cause:** Buffer is too large or logs aren't being sent.

**Fix:**
1. Check if Ledger server is reachable
2. Reduce `max_buffer_size`
3. Check `get_metrics()` to see how many logs are buffered

### Slow Requests

**Symptom:** Your API requests are slower after adding Ledger.

**Cause:** Middleware is blocking (shouldn't happen with default settings).

**Fix:**
1. Verify you're using the async version
2. Check if you're capturing request/response bodies (don't unless needed)
3. Profile your code to find the bottleneck

### Logs Appearing Slowly

**Symptom:** Logs don't show up in the dashboard for several seconds.

**Cause:** Batching delays. This is normal.

**Fix:** If you need faster log visibility, decrease `flush_interval` to 1-2 seconds. Be aware this increases network requests.

## Next Steps

- [CONFIGURATION.md](CONFIGURATION.md) - Tune settings for your workload
- [ARCHITECTURE.md](ARCHITECTURE.md) - Understand why it's fast
