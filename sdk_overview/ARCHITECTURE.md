# Ledger SDK Architecture

High-level architecture for the Ledger SDK system.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT APPLICATION                        │
│                                                              │
│  User Request → FastAPI → LedgerMiddleware                  │
│                              ↓                               │
│                      Capture log data                        │
│                              ↓                               │
│                      Buffer.add(log)  ← O(1), non-blocking  │
│                              ↓                               │
│                      Return response to user                 │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ Background task (async)
                               ↓
┌─────────────────────────────────────────────────────────────┐
│                    LEDGER SDK                                │
│                                                              │
│  ┌────────────────┐          ┌──────────────┐              │
│  │  Log Buffer    │──────────│ Rate Limiter │              │
│  │  (Queue)       │          │              │              │
│  └────────┬───────┘          └──────┬───────┘              │
│           │                         │                       │
│           │  Every 5s OR 100 logs   │                       │
│           ↓                         ↓                       │
│  ┌─────────────────────────────────────────┐               │
│  │  Background Flusher                     │               │
│  │  1. Check rate limit                    │               │
│  │  2. Batch up to 1000 logs               │               │
│  │  3. Send to Ledger                      │               │
│  │  4. Handle retries                      │               │
│  └─────────────────┬───────────────────────┘               │
│                    │                                        │
└────────────────────┼────────────────────────────────────────┘
                     │
                     │ HTTP POST /api/v1/ingest/batch
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                    LEDGER SERVER                             │
│                                                              │
│  Gateway → Auth → Ingestion Service → Redis Queue           │
└─────────────────────────────────────────────────────────────┘
```

## Initialization Flow

```
Application Startup
    ↓
Initialize LedgerClient(api_key, base_url, options)
    ↓
Create internal components:
    ├─ HTTP Client (connection pool: 10 connections)
    ├─ Settings Manager (lazy-loads on first use)
    ├─ Log Buffer (in-memory queue)
    ├─ Rate Limiter (sliding window tracker)
    └─ Background Flusher (async task)
    ↓
Register middleware with FastAPI app
    ↓
App ready to serve requests
```

**Key Decision**: Settings are lazy-loaded on first log, not during initialization. This prevents blocking app startup if Ledger server is unreachable.

## Request/Response Lifecycle

```
User Request to Client's API
    ↓
FastAPI receives request
    ↓
LedgerMiddleware.dispatch() called
    ↓
┌─────────────────────────────────────┐
│ BEFORE REQUEST                      │
│ - Capture: timestamp, method, URL   │
│ - Store in request.state            │
└─────────────────────────────────────┘
    ↓
Call next middleware / endpoint handler
    ↓
Endpoint executes (business logic)
    ↓
┌─────────────────────────────────────┐
│ IF EXCEPTION OCCURS:                │
│ - Catch exception                   │
│ - Extract: error type, message,     │
│   stack trace                       │
│ - Add to buffer (non-blocking)      │
│ - Re-raise exception                │
│   (app handles normally)            │
└─────────────────────────────────────┘
    ↓
Response ready
    ↓
┌─────────────────────────────────────┐
│ AFTER RESPONSE                      │
│ - Calculate duration                │
│ - Capture: status code, duration    │
│ - Create log entry                  │
│ - Add to buffer (non-blocking)      │
│   Buffer.add(log) → instant return  │
└─────────────────────────────────────┘
    ↓
Return response to user (NO waiting for Ledger)
```

## Log Buffer & Background Flushing

```
┌──────────────────────────────────────────────────┐
│  In-Memory Log Buffer (Thread-safe Queue)        │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐                    │
│  │Log1│ │Log2│ │Log3│ │Log4│ ... (max 10,000)   │
│  └────┘ └────┘ └────┘ └────┘                    │
└──────────────────────────────────────────────────┘
         ↓                        ↓
    Size trigger              Time trigger
  (100 logs reached)         (5 seconds passed)
         ↓                        ↓
         └────────┬───────────────┘
                  ↓
      ┌───────────────────────┐
      │ Background Flusher    │
      │ (asyncio.Task)        │
      └───────────────────────┘
                  ↓
      1. Pop up to 1,000 logs from buffer
      2. Check rate limiter (can we send now?)
         ├─ YES → Continue to step 3
         └─ NO → Sleep until next available slot
      3. Send batch to Ledger API
         POST /api/v1/ingest/batch
      4. Handle response:
         ├─ 202 Accepted → Success, clear buffer
         ├─ 429 Too Many Requests → Backoff, retry
         ├─ 503 Service Unavailable → Queue full, backoff
         └─ Network error → Keep in buffer, retry later
      5. Repeat every 5 seconds
```

## Settings Management

```
First log call
    ↓
Settings Manager checks: do we have cached settings?
    ├─ YES → Use cached settings
    └─ NO → Fetch from server
              ↓
        GET /api/v1/settings
              ↓
        ┌─────────────────────────────────┐
        │ Cache settings in memory:       │
        │ - Rate limits (1000/min)        │
        │ - Max batch size (1000)         │
        │ - Field length limits           │
        │ - Daily quota info              │
        │ TTL: Lifetime of SDK instance   │
        └─────────────────────────────────┘
              ↓
        Configure SDK components:
        ├─ Rate Limiter (set limits)
        ├─ Buffer (set max batch size)
        └─ Validator (set field limits)
```

**Cache Strategy**:
- **In-memory only** (no disk cache for Phase 1)
- **Lifetime**: Until SDK process restarts
- **Refresh triggers**:
  - Manual: `client.refresh_settings()` method
  - Automatic: On 401 Unauthorized response
- **Fallback**: If settings fetch fails, use conservative defaults

## Performance Characteristics

| Metric | Target | Notes |
|--------|--------|-------|
| Middleware latency | <1ms | Non-blocking buffer add |
| Background flush latency | 50-200ms | Depends on batch size |
| Memory overhead | ~10MB | 10,000 logs @ 1KB each |
| HTTP connections | 10 persistent | Connection pooling |
| CPU overhead | <1% | Minimal, async I/O |

## Failure Modes & Handling

### Buffer Overflow
- **Trigger**: Buffer exceeds 10,000 logs
- **Action**: Drop oldest logs (FIFO), log warning to stderr
- **Recovery**: Automatic when flush succeeds

### Ledger Server Unreachable
- **Trigger**: Network error, timeout
- **Action**: Keep logs in buffer, exponential backoff
- **Recovery**: Retry when network recovers

### Rate Limit Exceeded
- **Trigger**: 429 Too Many Requests
- **Action**: Sleep for Retry-After duration
- **Recovery**: Automatic after cooldown

### API Key Invalid
- **Trigger**: 401 Unauthorized
- **Action**: Refresh settings, log error to stderr
- **Recovery**: Manual (user must fix API key)

## Security Considerations

1. **API Key Storage**: Never log API keys to Ledger or stderr
2. **Data Privacy**: Middleware doesn't capture request/response bodies by default
3. **Memory Safety**: Buffer size limit prevents memory exhaustion
4. **Secure Transport**: HTTPS for production Ledger endpoints

## Scalability

### Vertical Scaling
- Single SDK instance handles 10K+ req/sec (client app traffic)
- Batching reduces Ledger API calls to 1-2 per second
- Memory footprint stays constant (~10MB)

### Horizontal Scaling
- Multiple app instances (load balanced) each have independent SDK instance
- Server-side aggregation handles distributed logs
- No coordination needed between SDK instances

## Next Steps

See [COMPONENTS.md](COMPONENTS.md) for detailed component design.
