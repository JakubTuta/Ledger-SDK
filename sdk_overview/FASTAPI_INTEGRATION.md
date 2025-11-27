# FastAPI Integration

How the Ledger middleware works with FastAPI.

## What It Does

The Ledger middleware wraps your FastAPI endpoints and automatically logs:

- Every request (method, URL, timestamp)
- Every response (status code, duration)
- Every exception (error type, message, stack trace)

You don't write any logging code. Just add the middleware and it works.

## Basic Setup

```python
from fastapi import FastAPI
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware

app = FastAPI()

ledger = LedgerClient(api_key="ledger_proj_1_your_key")

app.add_middleware(LedgerMiddleware, ledger_client=ledger)

@app.get("/")
async def root():
    return {"message": "Hello World"}  # Automatically logged
```

Every request to any endpoint is now logged.

## What Gets Logged

### Successful Requests

```python
{
    "level": "info",
    "message": "GET /api/users/{id} - 200 (45ms)",
    "attributes": {
        "endpoint": {
            "method": "GET",
            "path": "/api/users/{id}",  # Automatically normalized
            "status_code": 200,
            "duration_ms": 45
        }
    }
}
```

Note: URLs with dynamic segments are automatically normalized (e.g., `/api/users/123` becomes `/api/users/{id}`).

### Failed Requests

```python
{
    "level": "error",
    "message": "POST /api/payment - Exception",
    "error_type": "ValueError",
    "error_message": "Amount must be positive",
    "stack_trace": "Traceback (most recent call last):\n...",
    "attributes": {
        "http": {
            "method": "POST",
            "url": "/api/payment",
            "duration_ms": 12
        }
    }
}
```

## Configuration

### Exclude Paths

Don't log health checks or metrics endpoints:

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics", "/docs"],
)
```

### URL Filtering and Normalization

By default, the middleware automatically filters out common noise and normalizes URL patterns for better analytics.

#### Default Filtering

The middleware automatically ignores requests to:
- Common attack targets: `/.git/config`, `/.env`, `/robots.txt`, `/favicon.ico`
- Admin panels: `/wp-admin/`, `/admin/`
- Suspicious extensions: `.php`, `.asp`, `.aspx`, `.jsp`

This prevents cluttering your logs with bot traffic and malicious scanning attempts.

#### Path Normalization

The middleware uses **FastAPI's actual route patterns** for accurate path logging:

```python
# Your route definition
@app.get("/users/{user_id}/posts/{post_id}")
async def get_post(user_id: int, post_id: int):
    ...

# What gets logged
"/users/{user_id}/posts/{post_id}"  # Exact parameter names!
```

This is done by accessing `request.scope["route"].path` after the request is processed.

**Benefits:**
- ✅ Uses exact parameter names from your route definitions
- ✅ No false positives from regex patterns
- ✅ Works with any parameter type (IDs, slugs, usernames, etc.)
- ✅ Simpler and more reliable than pattern matching

**Fallback for unmatched routes:**

For 404s and unmatched requests, the middleware falls back to regex normalization:

```python
"/users/123"        -> "/users/{id}"
"/posts/456/edit"   -> "/posts/{id}/edit"
"/api/v1/users/789" -> "/api/v1/users/{id}"
```

**Supported ID formats (fallback):**
- Numeric IDs: `123`, `456`
- UUIDs: `550e8400-e29b-41d4-a716-446655440000`
- MongoDB ObjectIDs: `507f1f77bcf86cd799439011`
- Base64-url-safe: `HzZdSjYiiTw9S_L9Vfgtx...` (with `_` and `-`)
- Long hashes: any alphanumeric string 20+ characters

#### Configuration Options

Disable filtering or normalization:

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    filter_ignored_paths=False,  # Log everything, including bots
    normalize_paths=False,        # Keep original URLs with IDs
)
```

Use colon-style templates (`:id` instead of `{id}`):

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    template_style="colon",  # "/users/:id" instead of "/users/{id}"
)
```

Add custom filters:

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    custom_ignored_paths=["/internal", "/debug"],
    custom_ignored_prefixes=["/private/", "/temp/"],
    custom_ignored_extensions=[".bak", ".old"],
)
```

Add custom normalization patterns:

```python
import re

patterns = [
    (re.compile(r"/users/([a-z]+)"), "/users/{username}"),
    (re.compile(r"/posts/([a-z0-9-]+)"), "/posts/{slug}"),
]

app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    normalization_patterns=patterns,  # Replaces default patterns
)
```

### Capture Request/Response Bodies (Not Recommended)

By default, request and response bodies aren't captured for privacy and performance.

If you need them:

```python
app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    capture_request_body=True,   # Use with caution
    capture_response_body=True,  # Use with caution
)
```

**Warning:** This can capture sensitive data (passwords, credit cards) and make logs much larger.

## Performance

The middleware adds less than 0.1ms to each request.

It works by:

1. Noting the start time
2. Calling your endpoint
3. Recording the status code and duration
4. Adding a log entry to the buffer (instant, no I/O)
5. Returning the response

Your users get their response immediately. Sending logs to Ledger happens later in the background.

## Exception Handling

The middleware catches exceptions, logs them, and re-raises them.

Your app's error handling still works normally. Ledger just makes sure the exception is logged first.

```python
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    if user_id == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id}
```

The `HTTPException` is logged by Ledger, then handled by FastAPI as usual.

## Middleware Order

Add Ledger middleware **last** (so it executes first):

```python
app.add_middleware(CORSMiddleware)       # Executes 3rd
app.add_middleware(GZipMiddleware)       # Executes 2nd
app.add_middleware(LedgerMiddleware)     # Executes 1st
```

This way Ledger sees everything that happens, including errors from other middleware.

## Manual Logging

You can also log custom events:

```python
@app.post("/payment")
async def process_payment(amount: float):
    ledger.log_info(f"Processing payment: ${amount}", user_id=request.state.user_id)

    result = charge_card(amount)

    ledger.log_info(f"Payment successful", transaction_id=result.id)

    return {"status": "success"}
```

## Privacy

By default, the middleware doesn't capture:

- Request bodies
- Response bodies
- Headers (which might contain auth tokens)
- Cookies

It only captures:

- Request method (GET, POST, etc.)
- Request URL path (normalized)
- Query parameters (optional)
- Status code
- Duration
- Exception details (if an exception occurs)

This prevents accidentally logging sensitive data.

Additionally, the automatic URL filtering prevents logging:
- Bot traffic and malicious scanning attempts
- Requests to sensitive files (`.env`, `.git/config`)
- Attack vectors targeting common vulnerabilities

This keeps your logs clean and focused on legitimate application traffic.

## Next Steps

- [CONFIGURATION.md](CONFIGURATION.md) - Middleware configuration options
- [PERFORMANCE.md](PERFORMANCE.md) - Performance implications
- [ERROR_HANDLING.md](ERROR_HANDLING.md) - Exception handling details
