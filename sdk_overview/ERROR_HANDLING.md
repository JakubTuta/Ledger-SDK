# Error Handling & Retry Strategies

Comprehensive error handling design for the Ledger SDK.

## Error Categories

### 1. Client Errors (4xx) - Don't Retry

```
400 Bad Request
    → Validation error (malformed data)
    → Action: Log to stderr, drop batch, DON'T retry
    → Cause: SDK bug or constraint mismatch

401 Unauthorized
    → Invalid/revoked API key
    → Action: Refresh settings, log warning, STOP sending
    → Cause: API key expired or revoked

404 Not Found
    → Project doesn't exist
    → Action: Log error, STOP sending
    → Cause: Wrong API key or project deleted

429 Too Many Requests
    → Rate limit exceeded
    → Action: Read Retry-After header, sleep, RETRY
    → Cause: Too many requests or client-side rate limiter failed
```

**Philosophy**: Client errors indicate a problem with the request. Retrying won't fix it (except 429).

---

### 2. Server Errors (5xx) - Retry with Backoff

```
500 Internal Server Error
    → Temporary server issue
    → Action: Exponential backoff, retry up to 3 times
    → Cause: Server bug, database issue

503 Service Unavailable
    → Queue full (backpressure)
    → Action: Read Retry-After header, sleep, RETRY
    → Cause: High server load, queue full
```

**Philosophy**: Server errors are temporary. Retry with backoff to allow recovery.

---

### 3. Network Errors - Retry with Backoff

```
Connection Timeout
Connection Refused
DNS Resolution Failed
SSL/TLS Error
```

**Action**: Exponential backoff, retry indefinitely (keep logs in buffer)

**Philosophy**: Network is unreliable. Keep retrying until it recovers.

---

## Retry Strategy

### Exponential Backoff Algorithm

```python
async def send_with_retry(batch: list, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            response = await http_client.post(url, json={"logs": batch})

            # Success
            if response.status_code == 202:
                return response

            # Client errors (don't retry except 429)
            if 400 <= response.status_code < 500:
                if response.status_code == 429:
                    # Rate limit: respect Retry-After
                    retry_after = int(response.headers.get("Retry-After", 60))
                    await asyncio.sleep(retry_after)
                    continue
                else:
                    # Other 4xx: don't retry
                    raise ClientError(f"Client error: {response.status_code}")

            # Server errors: retry with exponential backoff
            if 500 <= response.status_code < 600:
                if response.status_code == 503:
                    # Service unavailable: respect Retry-After
                    retry_after = int(response.headers.get("Retry-After", 60))
                    await asyncio.sleep(retry_after)
                else:
                    # Other 5xx: exponential backoff
                    delay = (2 ** attempt) * 1.0  # 1s, 2s, 4s
                    await asyncio.sleep(delay)
                continue

        except NetworkError as e:
            # Network error: exponential backoff
            if attempt < max_retries - 1:
                delay = (2 ** attempt) * 5.0  # 5s, 10s, 20s
                await asyncio.sleep(delay)
            else:
                # Max retries reached: keep in buffer, try again later
                raise
```

### Backoff Schedules

**For 5xx errors** (server issues):

```
Attempt 1: Immediate
Attempt 2: Wait 1 second
Attempt 3: Wait 2 seconds
Attempt 4: Wait 4 seconds
Give up: Drop batch, log error
```

**For network errors** (connectivity issues):

```
Attempt 1: Immediate
Attempt 2: Wait 5 seconds
Attempt 3: Wait 10 seconds
Attempt 4: Wait 20 seconds
Attempt 5: Wait 40 seconds (max)
Continue: Keep waiting with 40s delay
```

**For 429 errors** (rate limit):

```
Read Retry-After header (e.g., 60 seconds)
Wait exactly Retry-After seconds
Retry immediately after
```

**For 503 errors** (queue full):

```
Read Retry-After header (default 60 seconds)
Wait Retry-After seconds
Retry
If persistent, slow down flush rate
```

---

## Error Response Handling

### 202 Accepted (Success)

```python
if response.status_code == 202:
    data = response.json()
    # {
    #   "accepted": 98,
    #   "rejected": 2,
    #   "errors": ["Log 5: Invalid timestamp", "Log 12: Message too long"]
    # }

    if data["rejected"] > 0:
        stderr.write(f"[Ledger SDK] WARNING: {data['rejected']} logs rejected\n")
        for error in data.get("errors", []):
            stderr.write(f"  - {error}\n")

    # Clear buffer (even if some rejected)
    buffer.clear()
```

**Philosophy**: Partial success is still success. Clear buffer and move on.

---

### 400 Bad Request (Validation Error)

```python
if response.status_code == 400:
    stderr.write(f"[Ledger SDK] ERROR: Validation error: {response.text}\n")
    stderr.write(f"[Ledger SDK] Dropping batch of {len(batch)} logs\n")

    # Drop batch (don't retry)
    buffer.clear()

    # This shouldn't happen if SDK validates correctly
    # Log to metrics for investigation
    metrics["validation_errors"] += 1
```

**Philosophy**: Don't retry validation errors. Drop and investigate.

---

### 401 Unauthorized (Invalid API Key)

```python
if response.status_code == 401:
    stderr.write(f"[Ledger SDK] ERROR: Invalid API key\n")

    # Try refreshing settings (maybe key was rotated)
    try:
        await settings_manager.refresh()
        stderr.write(f"[Ledger SDK] Settings refreshed, retrying\n")
        # Retry with new settings
        continue
    except Exception:
        stderr.write(f"[Ledger SDK] CRITICAL: API key is invalid, stopping log ingestion\n")
        # Set flag to stop background flusher
        self._api_key_invalid = True
        raise
```

**Philosophy**: Try refreshing once, then stop sending to avoid wasting resources.

---

### 429 Too Many Requests (Rate Limit)

```python
if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", 60))

    stderr.write(f"[Ledger SDK] WARNING: Rate limit exceeded, sleeping {retry_after}s\n")

    # Put logs back in buffer
    buffer.prepend(batch)

    # Sleep
    await asyncio.sleep(retry_after)

    # Retry
    continue
```

**Philosophy**: Respect server rate limits. Wait and retry.

---

### 500 Internal Server Error

```python
if response.status_code == 500:
    stderr.write(f"[Ledger SDK] ERROR: Server error (500), retrying with backoff\n")

    # Exponential backoff
    delay = (2 ** attempt) * 1.0
    await asyncio.sleep(delay)

    # Retry
    continue
```

**Philosophy**: Server issues are temporary. Retry with backoff.

---

### 503 Service Unavailable (Queue Full)

```python
if response.status_code == 503:
    retry_after = int(response.headers.get("Retry-After", 60))

    stderr.write(f"[Ledger SDK] WARNING: Queue full, sleeping {retry_after}s\n")

    # Put logs back in buffer
    buffer.prepend(batch)

    # Sleep
    await asyncio.sleep(retry_after)

    # If persistent, slow down flush rate
    if consecutive_503_count > 3:
        self.flush_interval *= 2  # Double flush interval
        stderr.write(f"[Ledger SDK] Slowing down: flush_interval now {self.flush_interval}s\n")

    # Retry
    continue
```

**Philosophy**: Server is overloaded. Back off and give it time to recover.

---

### Network Errors

```python
try:
    response = await http_client.post(url, json=data)
except (TimeoutError, ConnectionError, DNSError) as e:
    stderr.write(f"[Ledger SDK] ERROR: Network error: {e}\n")

    # Exponential backoff
    delay = min((2 ** attempt) * 5.0, 40.0)  # Max 40s
    await asyncio.sleep(delay)

    # Keep retrying (don't give up on network errors)
    continue
```

**Philosophy**: Network is unreliable. Keep retrying indefinitely.

---

## Buffer Management During Errors

### Buffer Overflow

```python
if buffer.size() >= max_buffer_size:
    dropped_log = buffer.pop_oldest()  # FIFO

    stderr.write(f"[Ledger SDK] WARNING: Buffer full, dropped 1 log\n")

    metrics["logs_dropped"] += 1
```

**Philosophy**: Protect client app from memory exhaustion. Drop old logs.

---

### Batch Re-queuing

```python
# On retryable error, put logs back in buffer
def requeue_batch(batch: list):
    # Add to front of buffer (LIFO for retry)
    for log in reversed(batch):
        buffer.prepend(log)
```

**Philosophy**: Don't lose logs on temporary errors. Re-queue and retry.

---

## Graceful Degradation

### Settings Fetch Failure

```python
try:
    settings = await fetch_settings()
except Exception as e:
    stderr.write(f"[Ledger SDK] WARNING: Failed to fetch settings: {e}\n")
    stderr.write(f"[Ledger SDK] Using default settings\n")

    settings = {
        "rate_limits": {"requests_per_minute": 1000},
        "constraints": {"max_batch_size": 100}
    }
```

**Philosophy**: Operate with defaults if server is unreachable.

---

### API Key Invalid

```python
if api_key_invalid:
    # Stop sending logs
    stderr.write(f"[Ledger SDK] ERROR: API key invalid, buffering logs locally\n")

    # Keep buffering (don't drop)
    # User can fix API key and call refresh_settings()
```

**Philosophy**: Don't silently drop logs. Buffer and wait for user to fix.

---

## Monitoring & Alerting

### SDK Error Metrics

```python
{
    "errors": {
        "400": 0,     # Validation errors (shouldn't happen)
        "401": 1,     # API key invalid
        "429": 5,     # Rate limit exceeded
        "500": 2,     # Server errors
        "503": 10,    # Queue full
        "network": 3  # Network errors
    },
    "logs_dropped": 100,  # Buffer overflow
    "logs_sent": 10000,
    "api_calls": 105
}
```

**Alert on**:

- `errors["401"] > 0` → API key issue
- `errors["400"] > 0` → SDK bug
- `logs_dropped > 0` → Buffer overflowing

---

## Error Logging

**To stderr** (not to Ledger, to avoid recursion):

```python
import sys

def log_error(message: str, level: str = "ERROR"):
    timestamp = datetime.utcnow().isoformat()
    sys.stderr.write(f"[{timestamp}] [Ledger SDK] [{level}] {message}\n")
    sys.stderr.flush()
```

**Examples**:

```
[2025-11-01T10:30:45.123Z] [Ledger SDK] [ERROR] Failed to send batch: Network error
[2025-11-01T10:30:45.124Z] [Ledger SDK] [WARNING] Rate limit exceeded, sleeping 60s
[2025-11-01T10:30:45.125Z] [Ledger SDK] [INFO] Buffer flush: sent 245 logs in 120ms
```

---

## Circuit Breaker Pattern (Production)

**Prevent cascading failures**: Implemented in `BackgroundFlusher`

**Configuration**:

- **Failure threshold**: 5 consecutive failures
- **Timeout**: 60 seconds
- **Recovery**: Automatic after timeout

**Implementation**:

```python
class BackgroundFlusher:
    def __init__(self):
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60.0
        self._circuit_breaker_open = False
        self._circuit_breaker_opened_at = None
        self._metrics["consecutive_failures"] = 0

    async def _attempt_flush(self):
        # Check circuit breaker
        if self._circuit_breaker_open:
            if time.time() - self._circuit_breaker_opened_at > self._circuit_breaker_timeout:
                # Timeout passed, try recovery
                self._circuit_breaker_open = False
                stderr.write("[Ledger SDK] Circuit breaker: Attempting recovery\n")
            else:
                # Still open, skip flush
                return

        try:
            success = await self._send_batch(batch)

            if success:
                # Reset on success
                self._metrics["consecutive_failures"] = 0

        except Exception:
            # Increment failures
            self._metrics["consecutive_failures"] += 1

            # Check threshold
            if self._metrics["consecutive_failures"] >= self._circuit_breaker_threshold:
                self._circuit_breaker_open = True
                self._circuit_breaker_opened_at = time.time()
                stderr.write("[Ledger SDK] Circuit breaker: OPEN (too many failures)\n")
```

**States**:

- **Closed**: Normal operation, requests go through
- **Open**: Too many failures, requests blocked
- **Recovery**: After timeout, attempts one request to test

**Monitoring**:

- Track via `get_metrics()["flusher"]["circuit_breaker_open"]`
- Health check fails when circuit breaker is open
- Exposed in health status endpoint

---

## Best Practices

1. **Never lose logs silently**: Buffer, retry, only drop as last resort
2. **Respect server signals**: Retry-After headers, rate limits
3. **Fail gracefully**: Use defaults, degrade service, don't crash
4. **Log errors**: To stderr, not to Ledger (avoid recursion)
5. **Monitor metrics**: Track error rates, buffer overflow
6. **Test failure modes**: Network errors, server errors, rate limits

---

## Testing Error Handling

```python
# Test 429 handling
async def test_rate_limit():
    mock_response = Mock(status_code=429, headers={"Retry-After": "5"})

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        await ledger.flush()

    # Should sleep 5 seconds and retry
    assert buffer.size() == 0  # Logs eventually sent

# Test network error
async def test_network_error():
    with patch("httpx.AsyncClient.post", side_effect=NetworkError()):
        await ledger.flush()

    # Should keep logs in buffer
    assert buffer.size() > 0

# Test buffer overflow
async def test_buffer_overflow():
    for i in range(15000):  # More than max_buffer_size
        ledger.log_info(f"Log {i}")

    # Should drop oldest logs
    assert buffer.size() == 10000
    assert metrics["logs_dropped"] > 0
```

---

## Next Steps

- See [PERFORMANCE.md](PERFORMANCE.md) for retry performance impact
- See [CONFIGURATION.md](CONFIGURATION.md) for retry tuning options
