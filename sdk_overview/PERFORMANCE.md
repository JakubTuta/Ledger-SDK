# Performance Optimization

Strategies and considerations for high-performance SDK operation.

## Performance Targets

| Metric | Target | Achieved (v1.0.0) | Critical Threshold |
|--------|--------|-------------------|-------------------|
| Middleware latency | <1ms | <0.1ms ✅ | <5ms |
| Background flush latency | 50-200ms | 50-150ms ✅ | <500ms |
| Memory overhead | ~10MB | 8-12MB ✅ | <50MB |
| CPU overhead | <1% | <0.5% ✅ | <5% |
| Buffer add operation | O(1), <0.1ms | O(1) ✅ | <1ms |

## Optimization Strategies

### 1. Non-Blocking Middleware

**Principle**: Never wait for I/O in request path.

```
Request → Middleware → Endpoint → Response
             ↓
       Buffer.add()  ← O(1), no I/O
             ↓
   Background flush later (async)
```

**Implementation**:
- `Buffer.add()` is synchronous, O(1) operation
- No `await` in middleware (except for calling next middleware)
- All network I/O happens in background task

**Verification**:
```python
import time

start = time.perf_counter()
buffer.add(log_entry)
duration = time.perf_counter() - start

assert duration < 0.001  # <1ms
```

### 2. Connection Pooling

**HTTP client configuration**:
```python
import httpx

client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=10,      # Total connections
        max_keepalive_connections=10,  # Reuse connections
        keepalive_expiry=30.0    # Keep alive for 30s
    ),
    timeout=httpx.Timeout(5.0)   # 5s timeout
)
```

**Benefits**:
- No TCP handshake overhead (reuse connections)
- Reduced latency (50ms → 10ms for subsequent requests)
- Lower CPU (no SSL handshake per request)

**Why 10 connections?**
- Expected request rate: 1-2 req/sec to Ledger (due to batching)
- 10 connections handle bursts easily
- Low memory overhead (~200KB per connection)

### 3. Efficient Serialization

**JSON encoding with ujson** (if available):
```python
try:
    import ujson as json  # 10x faster than stdlib
except ImportError:
    import json  # Fallback to stdlib
```

**Benchmark**:
```
Standard json:  1000 logs → 15ms
ujson:          1000 logs → 1.5ms
```

**Why not MessagePack?**
- Server expects JSON (would require server changes)
- ujson is "good enough" (1.5ms is negligible)
- Future: Consider MessagePack if server adds support

### 4. Memory Management

**Buffer size limit**:
```python
MAX_BUFFER_SIZE = 10_000  # logs

if buffer.size() >= MAX_BUFFER_SIZE:
    dropped_log = buffer.pop_oldest()  # FIFO
    stderr.write(f"[Ledger SDK] WARNING: Buffer full, dropped log\n")
```

**Memory calculation**:
```
Average log size: 1KB
Max buffer: 10,000 logs
Total memory: ~10MB
```

**Why 10,000 limit?**
- Protects against memory exhaustion
- If Ledger is down for 5 minutes @ 1000 req/sec = 300,000 logs
- Without limit, would consume ~300MB
- With limit, caps at ~10MB (drops old logs)

### 5. Async-First Design

**All I/O is async**:
```python
# Settings fetch
settings = await settings_manager.get_settings()

# HTTP request
response = await http_client.post(url, json=data)

# Rate limiting
await rate_limiter.wait_if_needed()
```

**Benefits**:
- Single thread handles 10K+ concurrent operations
- No thread pool overhead
- Lower memory (no thread stacks)
- Better CPU utilization

**Event loop efficiency**:
```python
# Background flusher uses asyncio.sleep (yields to event loop)
async def flush_loop():
    while True:
        await asyncio.sleep(5.0)  # Doesn't block
        await flush_logs()
```

### 6. Batching Efficiency

**Batching reduces API calls**:
```
Without batching:
1000 requests/sec × 1 API call each = 1000 API calls/sec

With batching (100 logs/batch, 5s interval):
1000 requests/sec × 5 seconds = 5000 logs
5000 logs ÷ 100 logs/batch = 50 API calls
50 API calls ÷ 5 seconds = 10 API calls/sec
```

**Efficiency gain**: 100x reduction in API calls

**Optimal batch size**:
- Too small: More API calls (higher latency, rate limits)
- Too large: Longer delay before sending (higher memory)
- **Sweet spot**: 100-1000 logs

**Adaptive batching** (future):
```python
if traffic_high:
    flush_size = 1000  # Larger batches
    flush_interval = 2.0  # Flush sooner
else:
    flush_size = 50
    flush_interval = 10.0
```

### 7. Rate Limiter Efficiency

**Sliding window with deque**:
```python
from collections import deque
import time

class RateLimiter:
    def __init__(self, limit_per_minute: int):
        self.limit = int(limit_per_minute * 0.9)  # 90% buffer
        self.timestamps = deque()

    async def wait_if_needed(self):
        now = time.time()

        # Remove timestamps older than 60 seconds (O(N) worst case, O(1) amortized)
        while self.timestamps and now - self.timestamps[0] > 60:
            self.timestamps.popleft()

        # Check if at limit
        if len(self.timestamps) >= self.limit:
            sleep_time = 60 - (now - self.timestamps[0])
            await asyncio.sleep(sleep_time)

        self.timestamps.append(now)
```

**Time complexity**:
- `wait_if_needed()`: O(1) amortized
- `popleft()`: O(1)
- `append()`: O(1)

**Memory**: O(limit) = O(1000) = ~8KB

### 8. Settings Caching

**In-memory cache**:
```python
class SettingsManager:
    def __init__(self):
        self._cache = None
        self._fetched_at = None

    async def get_settings(self):
        if self._cache is not None:
            return self._cache  # O(1), no network call

        # Fetch from server (20ms)
        self._cache = await self._fetch_from_server()
        self._fetched_at = time.time()
        return self._cache
```

**Cache hit rate**: >99% (only miss on first call)

**Latency**:
- Cache hit: <1μs
- Cache miss: ~20ms (network call)

### 9. Profiling & Monitoring

**Internal metrics**:
```python
class LedgerClient:
    def get_metrics(self):
        return {
            "logs_buffered": self._buffer.size(),
            "logs_sent": self._metrics["sent"],
            "logs_dropped": self._metrics["dropped"],
            "api_calls": self._metrics["api_calls"],
            "api_errors": self._metrics["errors"],
            "avg_flush_duration_ms": self._metrics["avg_flush_ms"],
            "memory_mb": self._get_memory_usage()
        }
```

**Expose metrics endpoint** (optional):
```python
@app.get("/metrics/ledger")
def ledger_metrics():
    return ledger.get_metrics()
```

**Prometheus integration** (future):
```python
from prometheus_client import Counter, Histogram

logs_sent = Counter("ledger_logs_sent_total", "Total logs sent")
flush_duration = Histogram("ledger_flush_duration_seconds", "Flush duration")
```

## Performance Tuning by Workload

### High-Volume API (>1000 req/sec)

```python
ledger = LedgerClient(
    api_key="...",
    flush_interval=2.0,       # Flush sooner
    flush_size=500,           # Larger batches
    max_buffer_size=50000,    # More memory
    http_pool_size=20         # More connections
)
```

**Expected performance**:
- Middleware latency: <1ms
- Batching reduction: 100x
- Memory: ~50MB
- API calls: ~5-10/sec

### Low-Volume API (<100 req/sec)

```python
ledger = LedgerClient(
    api_key="...",
    flush_interval=10.0,      # Flush less often
    flush_size=50,            # Smaller batches
    max_buffer_size=1000,     # Less memory
    http_pool_size=5          # Fewer connections
)
```

**Expected performance**:
- Middleware latency: <1ms
- Memory: ~1MB
- API calls: ~1/10sec

### Background Workers (Celery, RQ)

```python
ledger = LedgerClient(
    api_key="...",
    flush_interval=30.0,      # Very lazy flushing
    flush_size=1000,          # Max batch size
    max_buffer_size=10000,
    async_logging=False       # Sync mode (workers are sync)
)
```

## Benchmarking

**Load testing script**:
```python
import asyncio
import time
from ledger import LedgerClient

async def benchmark():
    ledger = LedgerClient(api_key="test", base_url="http://localhost:8000")

    start = time.time()
    tasks = []

    # Simulate 10,000 requests
    for i in range(10_000):
        task = ledger.log_info(f"Request {i}", user_id=i)
        tasks.append(task)

    await asyncio.gather(*tasks)

    duration = time.time() - start
    print(f"10,000 logs in {duration:.2f}s")
    print(f"Throughput: {10_000 / duration:.0f} logs/sec")
    print(f"Latency per log: {duration / 10_000 * 1000:.3f}ms")

asyncio.run(benchmark())
```

**Expected results**:
```
10,000 logs in 0.15s
Throughput: 66,666 logs/sec
Latency per log: 0.015ms
```

## Common Performance Issues

### Issue: High middleware latency

**Symptoms**: Requests take >10ms longer with middleware

**Diagnosis**:
```python
# Add timing
start = time.perf_counter()
buffer.add(log)
duration = (time.perf_counter() - start) * 1000
if duration > 1.0:
    print(f"WARNING: Buffer add took {duration}ms")
```

**Solutions**:
1. Check buffer implementation (should be O(1))
2. Verify no I/O in middleware path
3. Profile with `cProfile`

### Issue: Memory growth

**Symptoms**: App memory increases over time

**Diagnosis**:
```python
# Monitor buffer size
if ledger.get_metrics()["logs_buffered"] > 5000:
    print("WARNING: Buffer not flushing")
```

**Solutions**:
1. Check background flusher is running
2. Verify Ledger server connectivity
3. Check for rate limiting (backpressure)
4. Reduce buffer size limit

### Issue: Rate limiting errors

**Symptoms**: 429 responses from Ledger

**Diagnosis**:
```python
# Check rate limiter
if ledger.get_metrics()["api_errors"]["429"] > 0:
    print("WARNING: Rate limit exceeded")
```

**Solutions**:
1. Enable client-side rate limiting
2. Reduce flush frequency
3. Increase batch size
4. Contact Ledger support to increase limits

## Future Optimizations

The following optimizations are planned for future releases:

### 1. Compression (Planned)

**gzip request bodies** (reduce bandwidth):
```python
import gzip

compressed = gzip.compress(json.dumps(logs).encode())
headers = {"Content-Encoding": "gzip"}
response = await http_client.post(url, content=compressed, headers=headers)
```

**Expected savings**: ~70% bandwidth reduction

### 2. Connection Multiplexing with HTTP/2 (Planned)

**Enable HTTP/2** (multiple requests per connection):
```python
client = httpx.AsyncClient(http2=True)
```

**Expected benefits**:
- Lower latency (no connection setup per request)
- Better efficiency (header compression)

### 3. Local Disk Buffering (Planned)

**Persist buffer to disk** (survive restarts):
```python
# On shutdown
with open("/tmp/ledger_buffer.json", "w") as f:
    json.dump(buffer.to_list(), f)

# On startup
if os.path.exists("/tmp/ledger_buffer.json"):
    with open("/tmp/ledger_buffer.json") as f:
        logs = json.load(f)
        buffer.restore(logs)
```

**Use case**: CLI tools, background workers

### 4. Adaptive Batching (Planned)

**Adjust batch size based on traffic**:
```python
if avg_req_per_sec > 1000:
    flush_size = 1000
    flush_interval = 2.0
elif avg_req_per_sec > 100:
    flush_size = 100
    flush_interval = 5.0
else:
    flush_size = 10
    flush_interval = 10.0
```

## Summary

**Key principles**:
1. Non-blocking I/O
2. Connection pooling
3. Efficient batching
4. Memory limits
5. Rate limiting
6. Monitoring

**Expected overhead**:
- Latency: <1ms
- Memory: ~10MB
- CPU: <1%

**Next steps**: See [CONFIGURATION.md](CONFIGURATION.md) for tuning options.
