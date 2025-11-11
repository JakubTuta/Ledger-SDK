# SDK Components

Detailed design of each SDK component.

## Component Overview

```
LedgerClient
    ├─ SettingsManager      - Fetches and caches server settings
    ├─ LogBuffer            - In-memory queue with auto-flush
    ├─ RateLimiter          - Client-side rate limiting
    ├─ HTTPClient           - Connection pooling and request handling
    ├─ Validator            - Field validation and truncation
    └─ BackgroundFlusher    - Async task for batch sending
```

---

## 1. LedgerClient

**Purpose**: Main entry point for SDK, orchestrates all components.

**Responsibilities**:
- Initialize all sub-components
- Provide public API for logging
- Manage lifecycle (startup, shutdown)
- Coordinate settings refresh

**Key Methods**:
```python
__init__(api_key, base_url, **options)
    # Initialize components with configuration validation

def log_info(message, **attributes)
    # Add info-level log to buffer

def log_error(message, **attributes)
    # Add error-level log to buffer

def log_exception(exception, **attributes)
    # Capture exception with stack trace

async def shutdown(timeout=10.0)
    # Flush remaining logs, close connections

def get_metrics() -> dict
    # Return comprehensive SDK metrics

def is_healthy() -> bool
    # Quick health check (boolean)

def get_health_status() -> dict
    # Detailed health status with issues
```

**State**:
- `api_key`: Bearer token for authentication
- `base_url`: Ledger server URL
- `_settings_manager`: Settings component
- `_buffer`: Log buffer component
- `_rate_limiter`: Rate limiter component
- `_http_client`: HTTP client component
- `_flusher_task`: Background asyncio.Task
- `_shutdown_event`: asyncio.Event for graceful shutdown

---

## 2. SettingsManager

**Purpose**: Manage server configuration with hardcoded defaults.

**Responsibilities**:
- Provide hardcoded production defaults
- Cache settings in memory
- Return rate limits and constraints
- No server fetch (no /api/v1/settings endpoint exists)

**Key Methods**:
```python
def get_rate_limits()
    # Return rate limit configuration

def get_constraints()
    # Return validation constraints (max lengths, etc.)

def _get_default_settings()
    # Return hardcoded production defaults
```

**Settings Strategy**:
- **Storage**: Hardcoded in-memory dictionary
- **No server fetch**: Server has no /api/v1/settings endpoint
- **Based on**: Documented Ledger API limits
- **Updates**: Require SDK code change

**Default Settings**:
```python
{
    "rate_limits": {
        "requests_per_minute": 1000,
        "requests_per_hour": 50000
    },
    "constraints": {
        "max_batch_size": 1000,
        "max_message_length": 10000,
        "max_error_message_length": 5000,
        "max_stack_trace_length": 50000,
        "max_attributes_size_bytes": 102400
    }
}
```

---

## 3. LogBuffer

**Purpose**: In-memory queue with automatic flushing.

**Responsibilities**:
- Store logs in thread-safe queue
- Trigger flush on size or time
- Handle overflow (drop oldest)
- Provide batch extraction

**Key Methods**:
```python
def add(log_entry: dict)
    # Add log to buffer (O(1), non-blocking)

def get_batch(max_size: int) -> list
    # Extract up to max_size logs

def size() -> int
    # Return current buffer size

def is_empty() -> bool
    # Check if buffer is empty

def clear()
    # Remove all logs (used after successful flush)
```

**Implementation Details**:
- **Data structure**: `asyncio.Queue` (thread-safe, async-native)
- **Max size**: 10,000 logs (configurable)
- **Overflow handling**: Drop oldest (FIFO), log warning to stderr
- **Flush triggers**:
  - Size: 100 logs (configurable via `flush_size`)
  - Time: 5 seconds (configurable via `flush_interval`)

**Memory Management**:
- Average log size: ~1KB
- Max memory: ~10MB (10,000 logs)
- No disk persistence (in-memory only)

---

## 4. RateLimiter

**Purpose**: Client-side dual-window rate limiting to avoid 429 errors.

**Responsibilities**:
- Track request timestamps in dual windows (per-minute and per-hour)
- Enforce per-minute and per-hour limits simultaneously
- Calculate sleep time if either limit reached
- Stay under server limits (90% buffer)

**Key Methods**:
```python
async def wait_if_needed()
    # Sleep if either rate limit reached

def get_current_rate() -> int
    # Return requests in last minute

def get_current_hourly_rate() -> int
    # Return requests in last hour

def is_at_limit() -> bool
    # Check if at either limit
```

**Algorithm** (Dual Sliding Window):
```python
1. Remove timestamps older than 60 seconds from minute window
2. Remove timestamps older than 3600 seconds from hour window
3. Count remaining timestamps in each window
4. If either count >= (limit * 0.9):  # 90% buffer
     calculate sleep_time from appropriate window
     await asyncio.sleep(sleep_time)
5. Add timestamp to both windows
```

**Configuration**:
- Per-minute limit: 1000 requests (90% = 900)
- Per-hour limit: 50,000 requests (90% = 45,000)
- Buffer: 90% of limit (to leave safety margin)

**Why dual windows?**
- Prevents short-term bursts AND long-term overuse
- Per-minute: Protects against sudden spikes
- Per-hour: Ensures compliance with daily quotas

**Why 90% buffer?**
- Accounts for clock skew
- Prevents edge cases (requests in flight)
- Better UX (no sudden rate limit errors)

---

## 5. HTTPClient

**Purpose**: HTTP request handling with connection pooling.

**Responsibilities**:
- Maintain connection pool
- Send requests with retries
- Handle timeouts
- Parse responses

**Key Methods**:
```python
async def post(url: str, json: dict, headers: dict)
    # Send POST request

async def get(url: str, headers: dict)
    # Send GET request

async def close()
    # Close all connections
```

**Configuration**:
- **Library**: `httpx` (supports both async and sync)
- **Connection pool**: 10 connections
- **Timeout**: 5 seconds
- **Keepalive**: Enabled
- **Retries**: Handled by SDK, not HTTP client

**Why httpx?**
- Supports both async and sync (future Flask support)
- Modern, well-maintained
- Connection pooling built-in
- Timeout handling

**Alternative**: `aiohttp` (faster but async-only)

---

## 6. Validator

**Purpose**: Validate and truncate log fields before sending.

**Responsibilities**:
- Enforce field length limits
- Truncate oversized fields
- Validate required fields
- Convert timestamps to ISO 8601

**Key Methods**:
```python
def validate_log(log_entry: dict, constraints: dict) -> dict
    # Validate and truncate fields

def truncate_field(value: str, max_length: int) -> str
    # Truncate with "[truncated]" suffix

def validate_timestamp(timestamp: str) -> str
    # Ensure ISO 8601 format

def validate_level(level: str) -> bool
    # Check if level is valid (info, error, etc.)
```

**Validation Rules**:
```python
Required fields:
- timestamp (ISO 8601)
- level (debug/info/warning/error/critical)
- log_type (console/logger/exception/custom)
- importance (low/standard/high)

Optional fields (with limits):
- message: max 10,000 chars
- error_type: max 255 chars
- error_message: max 5,000 chars
- stack_trace: max 50,000 chars (errors only)
- attributes: max 100KB JSON
```

**Truncation Strategy**:
```python
if len(message) > max_length:
    message = message[:max_length - 15] + "... [truncated]"
```

**Why client-side validation?**
- Reduces 400 errors from server
- Faster feedback (immediate, not async)
- Reduces server load

---

## 7. BackgroundFlusher

**Purpose**: Async task that sends batches to Ledger with production-grade error handling.

**Responsibilities**:
- Run continuous flush loop
- Batch logs from buffer
- Check rate limiter
- Send to server
- Handle retries with exponential backoff
- Implement circuit breaker pattern
- Track comprehensive metrics

**Main Loop**:
```python
async def run():
    while not shutdown_event.is_set():
        # Wait for trigger
        await asyncio.sleep(flush_interval)

        # Check if buffer has logs
        if buffer.is_empty():
            continue

        # Get batch
        logs = buffer.get_batch(max_batch_size)

        # Check rate limiter
        await rate_limiter.wait_if_needed()

        # Send batch
        try:
            response = await http_client.post(
                f"{base_url}/api/v1/ingest/batch",
                json={"logs": logs},
                headers={"Authorization": f"Bearer {api_key}"}
            )

            # Handle response
            await handle_response(response, logs)

        except Exception as e:
            await handle_error(e, logs)
```

**Response Handling**:
```python
202 Accepted:
    - Success, clear buffer
    - Reset circuit breaker consecutive failures
    - Log success to metrics

400 Bad Request:
    - Validation error
    - Log error to stderr
    - Drop batch (don't retry)

401 Unauthorized:
    - Invalid API key
    - Log error, stop ingestion
    - Don't retry

429 Too Many Requests:
    - Read Retry-After header
    - Sleep for Retry-After duration
    - Retry with backoff

503 Service Unavailable:
    - Queue full on server
    - Read Retry-After header
    - Sleep and retry

500 Internal Server Error:
    - Temporary server issue
    - Exponential backoff: 2s, 4s, 8s
    - Max 3 retries
    - Increment consecutive failures
    - Open circuit breaker if threshold reached

Network Error:
    - Exponential backoff: 5s, 10s, 20s
    - Max 3 retries per attempt
    - Increment consecutive failures
    - Open circuit breaker if threshold reached
```

**Circuit Breaker**:
- **Threshold**: 5 consecutive failures
- **Timeout**: 60 seconds
- **Behavior**: Stops sending when open, attempts recovery after timeout
- **Recovery**: Transitions to half-open, then closed on success

---

## Component Interaction Example

```
User request to /api/payment
    ↓
FastAPI receives request
    ↓
LedgerMiddleware.dispatch()
    ├─ Start timer
    └─ Call next()
    ↓
Endpoint handler executes
    ↓ (exception occurs)
Exception caught by middleware
    ↓
Middleware calls:
    LedgerClient.log_exception(exc)
        ↓
    Validator.validate_log(log_entry)
        ↓
    LogBuffer.add(validated_log)  ← Returns instantly
        ↓
    (Background) BackgroundFlusher detects 100 logs in buffer
        ↓
    RateLimiter.wait_if_needed()  ← Checks limits
        ↓
    HTTPClient.post(batch)  ← Sends to server
        ↓
    Response: 202 Accepted
        ↓
    LogBuffer.clear()  ← Remove sent logs
```

---

## Error Handling Philosophy

1. **Never block user requests**: All errors handled async
2. **Fail gracefully**: Degrade service, don't crash
3. **Observable failures**: Log to stderr, provide metrics
4. **Automatic recovery**: Retry with backoff
5. **Last resort**: Drop logs only when buffer full

---

## Performance Characteristics

| Component | Latency | Memory | CPU |
|-----------|---------|--------|-----|
| SettingsManager | 0ms (cached) / 20ms (fetch) | 1KB | <0.1% |
| LogBuffer.add() | <0.1ms (O(1)) | 10MB max | <0.1% |
| Validator | <0.1ms | 0 | <0.1% |
| RateLimiter | <0.1ms | 1KB | <0.1% |
| BackgroundFlusher | 50-200ms | 0 | <1% |
| HTTPClient | 50-200ms | 2MB | <1% |

**Total SDK overhead**: ~10MB memory, <1% CPU

---

## Production Status

All components are production-ready with:
1. **Error handling**: Circuit breaker, retries, graceful degradation
2. **Monitoring**: Comprehensive metrics and health checks
3. **Validation**: Configuration and log entry validation
4. **Testing**: Integration tested against real Ledger server

See `python/fastapi/PRODUCTION_READY.md` for complete production features documentation.
