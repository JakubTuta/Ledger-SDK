# How Ledger Works

This guide explains how logs flow from your application to the Ledger dashboard.

## The Big Picture

```
Your Application
    ↓ (captures request info)
Ledger SDK
    ↓ (adds to buffer)
Background Task
    ↓ (sends batches)
Ledger Server
    ↓ (stores and indexes)
Ledger Dashboard
```

## Step by Step

### 1. Your App Receives a Request

When someone hits your API, FastAPI processes the request normally. The Ledger middleware quietly notes the timestamp, method, and URL.

**Time added:** Less than 0.1ms

### 2. Your Endpoint Runs

Your code executes as usual. If an exception happens, Ledger catches it (and re-raises it so your app can handle it normally).

### 3. Response is Sent

Before sending the response back to the user, Ledger records the status code and duration. This log entry goes into a buffer in memory.

**Time added:** Less than 0.1ms

**User gets their response immediately** - no waiting for network requests.

### 4. Background Task Sends Batches

Every 5 seconds (or when 1000 logs accumulate), a background task wakes up and sends the buffered logs to the Ledger server.

This happens completely separately from your request handling. Your API stays fast even if Ledger is slow.

### 5. Server Stores Logs

The Ledger server receives the batch, validates it, and stores it in the database. You can then search and analyze logs in the dashboard.

## What If Things Go Wrong?

### Ledger Server is Down

Logs stay in the buffer. The SDK automatically retries with backoff (waits 2s, then 4s, then 8s). Logs aren't lost unless the buffer fills up.

### Buffer Fills Up

If logs can't be sent for a while and the buffer reaches 10,000 logs, the SDK starts dropping the oldest ones. This prevents your app from running out of memory.

### Network is Slow

Doesn't matter. All network operations happen in the background. Your app never waits.

### Rate Limit Hit

The SDK has built-in rate limiting to avoid hitting server limits. If you do hit a limit, it backs off automatically.

## Why It's Fast

**Non-blocking design** - Log capture returns instantly. Network requests happen later.

**Batching** - Instead of 1000 separate requests per second, the SDK sends 1 batch with 1000 logs every 5 seconds.

**Connection pooling** - HTTP connections stay open and get reused, avoiding slow connection setup.

**Async everything** - All I/O uses Python's asyncio, so a single thread can handle thousands of concurrent operations.

## Next Steps

- [CONFIGURATION.md](CONFIGURATION.md) - Tune the SDK for your traffic
- [ERROR_HANDLING.md](ERROR_HANDLING.md) - Learn about retry behavior
- [PERFORMANCE.md](PERFORMANCE.md) - Performance details
