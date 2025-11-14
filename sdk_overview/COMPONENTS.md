# SDK Components

The internal pieces that make Ledger work.

## Overview

The Ledger SDK is built from several components that work together:

```
LedgerClient (main interface)
    ├─ LogBuffer (stores logs in memory)
    ├─ RateLimiter (prevents hitting server limits)
    ├─ HTTPClient (sends requests)
    ├─ Validator (checks log format)
    └─ BackgroundFlusher (sends batches)
```

You interact with `LedgerClient`. The other components work behind the scenes.

## LedgerClient

This is what you use in your code:

```python
ledger = LedgerClient(api_key="...", base_url="...")

ledger.log_info("Something happened", user_id=123)
ledger.log_error("Something went wrong", error_code="E001")

metrics = ledger.get_metrics()
healthy = ledger.is_healthy()
```

It coordinates all the other components.

## LogBuffer

An in-memory queue that stores logs until they're ready to be sent.

**Think of it like:** A bucket that collects logs. When it's full enough (or enough time passes), the logs get sent to Ledger.

**Key behavior:**
- Adds logs instantly (no waiting)
- Holds up to 10,000 logs by default
- Drops oldest logs if it fills up
- Thread-safe (multiple requests can add logs simultaneously)

## RateLimiter

Prevents the SDK from hitting Ledger's server rate limits.

**Think of it like:** A traffic cop that says "wait a bit" if you're sending too many requests too quickly.

**Key behavior:**
- Tracks how many requests were sent in the last minute and last hour
- Sleeps if you're approaching the limit
- Uses 90% of the limit as a safety buffer

Why both per-minute and per-hour? To prevent short bursts AND long-term overuse.

## HTTPClient

Handles all network communication with Ledger.

**Think of it like:** A mail carrier that delivers batches of logs to Ledger.

**Key behavior:**
- Reuses connections (faster than creating new ones each time)
- Has a 5-second timeout
- Maintains a pool of 10 connections

## Validator

Makes sure logs are valid before sending them.

**Think of it like:** Quality control that checks each log meets requirements.

**Key behavior:**
- Truncates messages that are too long
- Checks required fields are present
- Converts timestamps to the right format
- Ensures log structure matches what the server expects

This prevents errors from the server rejecting logs.

## BackgroundFlusher

An async task that runs continuously in the background, sending logs from the buffer to Ledger.

**Think of it like:** A scheduled mail pickup that comes by every few seconds to collect logs and send them.

**Key behavior:**
- Wakes up every 5 seconds (or when 1000 logs accumulate)
- Checks if there are logs to send
- Checks rate limiter
- Sends batch to server
- Handles retries if it fails
- Implements circuit breaker (stops trying if server is clearly down)

This is what makes Ledger non-blocking. Your code adds logs to the buffer and returns immediately. This task sends them later.

## How They Work Together

1. Your code calls `ledger.log_info("message")`
2. **Validator** checks the log is valid
3. **LogBuffer** adds it to the queue (instant)
4. Your code continues (no waiting)
5. **BackgroundFlusher** wakes up (after 5s or 1000 logs)
6. **RateLimiter** checks if it's okay to send
7. **HTTPClient** sends the batch to Ledger
8. If it fails, **BackgroundFlusher** retries with backoff

All of this happens automatically. You just call `log_info()` and it works.

## Why This Design?

**Non-blocking** - Your code never waits for network I/O

**Efficient** - Batching reduces network overhead

**Reliable** - Retries and circuit breaker handle failures

**Safe** - Rate limiting and buffer limits prevent resource exhaustion

## Next Steps

- [ARCHITECTURE.md](ARCHITECTURE.md) - See the big picture
- [ERROR_HANDLING.md](ERROR_HANDLING.md) - Learn about retry logic
