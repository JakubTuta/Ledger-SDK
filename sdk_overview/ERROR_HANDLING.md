# Error Handling

What happens when things go wrong and how Ledger handles it.

## The Philosophy

Ledger is designed to never break your application. Even if Ledger's server is completely down, your API keeps working.

Logs might be lost, but your users don't suffer.

## Common Scenarios

### Ledger Server is Down

**What happens:** Logs stay in the buffer. The SDK retries with increasing delays (2s, 4s, 8s).

**What you do:** Nothing. It's automatic.

**When logs are lost:** Only if the buffer fills up (10,000 logs by default). This would take a while.

### Network is Slow or Flaky

**What happens:** Same as above. Retries with backoff.

**What you do:** Check metrics to see if logs are being dropped: `ledger.get_metrics()['buffer']['total_dropped']`

### Rate Limit Hit

**What happens:** The SDK has built-in rate limiting to avoid this. But if you do hit a limit, it backs off for the time specified by the server.

**What you do:** Nothing. It's automatic.

### Invalid API Key

**What happens:** The SDK logs an error and stops trying to send logs.

**What you do:** Fix your API key and restart your app.

### Server Returns Validation Error

**What happens:** The SDK logs the error and drops that batch of logs.

**What you do:** This shouldn't happen with correct SDK usage. If it does, check the error messages and report a bug.

## Circuit Breaker

If Ledger fails 5 times in a row, the SDK opens a "circuit breaker" and stops trying for 60 seconds.

This prevents wasting resources on a server that's clearly having issues.

After 60 seconds, it tries again. If it succeeds, normal operation resumes.

**Check if it's open:**

```python
status = ledger.get_health_status()
if status["circuit_breaker_open"]:
    print("Circuit breaker is open - too many failures")
```

## Buffer Overflow

If logs can't be sent and the buffer reaches its limit (10,000 by default), the oldest logs are dropped.

This is a last resort to prevent your app from running out of memory.

**Avoid this by:**
- Making sure Ledger server is reachable
- Increasing `max_buffer_size` if you have high traffic
- Monitoring `total_dropped` in metrics

## What Gets Logged to stderr

The SDK writes error messages to stderr (not to Ledger, to avoid infinite loops):

```
[Ledger SDK] ERROR: Failed to send batch: Network error
[Ledger SDK] WARNING: Buffer full, dropped 1 log
[Ledger SDK] INFO: Circuit breaker: OPEN (too many failures)
```

Watch your application logs for these messages.

## Monitoring

Check SDK health in your own health endpoint:

```python
@app.get("/health")
async def health():
    ledger_healthy = ledger.is_healthy()
    return {
        "status": "healthy" if ledger_healthy else "degraded",
        "ledger": ledger.get_health_status()
    }
```

Your app can still be "healthy" even if Ledger isn't. Ledger is observability, not critical infrastructure.

## Retry Behavior

**Server errors (500, 503):** Retry up to 3 times with exponential backoff (2s, 4s, 8s).

**Network errors:** Retry up to 3 times with longer backoff (5s, 10s, 20s).

**Rate limits (429):** Wait for the time specified by the server, then retry.

**Client errors (400, 401, 404):** Don't retry. These mean something is wrong with your configuration.

## Next Steps

- [ARCHITECTURE.md](ARCHITECTURE.md) - Understand the retry flow
- [CONFIGURATION.md](CONFIGURATION.md) - Tune buffer and retry settings
