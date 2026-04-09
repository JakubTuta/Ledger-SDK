## [1.3.0] - 2026-04-09

### Added

- **Sync host support** - Flask and Django WSGI applications now actually flush logs via a dedicated daemon thread with its own asyncio event loop (`ThreadedFlusher`)
- `log_warning()` method on `LedgerClient` for warning-level messages
- `log_endpoint()` public method on `LedgerClient` replacing internal `_log()` calls from middlewares
- `shutdown_sync()` method on `LedgerClient` for use in `atexit` handlers and other sync shutdown hooks
- `path_params` captured and sent for all frameworks (FastAPI `request.path_params`, Flask `request.view_args`, Django `resolver_match.kwargs`)
- Django middleware now supports async ASGI hosts via `async_capable = True` and `__acall__`
- `requeue()` method on `LogBuffer` — failed batches are pushed back to the front of the queue instead of being silently dropped
- `flush_size` now triggers an immediate wakeup of the flusher instead of waiting for the next interval
- `SendResult` enum in flusher distinguishing `OK`, `DROPPED`, and `RETRY_EXHAUSTED` outcomes
- Half-open circuit breaker state for probe-based recovery after the timeout window
- `DEFAULT_RATE_LIMITS` and `DEFAULT_CONSTRAINTS` constants in `config.py` (absorbed from deleted `settings.py`)
- `ledger._logging` module — all internal SDK log output now goes through `logging.getLogger("ledger")` with a `NullHandler`; configure via standard Python logging

### Fixed

- Flask and Django integrations silently never flushed — no running event loop at client construction time (critical)
- Batches lost on retry exhaustion — logs are now requeued to the buffer front on failure
- Shutdown could not drain through an open circuit breaker — breaker is bypassed during shutdown
- `_run` loop only processed one batch per flush interval — inner drain loop now runs until buffer is empty
- `flush_size` config had no effect — flusher is now notified via wakeup event when the threshold is reached
- 400 responses counted as successful flushes — now correctly classified as `DROPPED`
- Partial 202 responses: `total_logs_sent` now reflects only the accepted count, not the full batch size
- 429/503 sleep caused double backoff on next retry — sleep is now handled before returning `RETRY_EXHAUSTED`
- `_circuit_breaker_opened_at` initialized to `None` causing `TypeError` on first arithmetic — now `0.0`
- Flask `errorhandler(Exception)` prevented downstream error handlers from running — replaced with `got_request_exception` signal
- `asyncio.Lock` in `LogBuffer.get_batch()` was incompatible with sync callers — replaced with `threading.Lock`
- `or`-based config defaults silently replaced valid zero-ish values — replaced with `is not None` checks
- User-Agent hardcoded to `ledger-sdk-python/1.0.0` — now uses the actual installed version
- Redundant header merge in `HTTPClient.post()` / `get()` removed
- `typing.Pattern` (deprecated since 3.9) replaced with `re.Pattern` across all files
- `SettingsManager` was dead indirection returning hardcoded dicts — deleted
- `Validator._normalize_timestamp()` was a no-op — removed
- `_validate_attributes()` serialized large attribute dicts twice — fast path added for small typed dicts
- URL normalization regex `[a-z0-9_-]{20,}` collapsed readable slugs — now requires at least one digit
- `exclude_paths` stored as `list` causing O(n) lookup per request — changed to `set`
- FastAPI middleware duplicated route-resolution logic across success and exception branches — extracted to `_resolve_path()`
- Validator constants were mutable `set` — changed to `frozenset`
- Rate limiter timestamp deques had no size cap — `maxlen` safety net added
- `test_shutdown` asserted a tautology (`is_empty() or not is_empty()`) — replaced with a meaningful assertion

### Changed

- `LedgerClient.__init__` detects whether a running event loop exists and selects `BackgroundFlusher` (async mode) or `ThreadedFlusher` (sync mode) automatically
- Middlewares call `ledger.log_endpoint()` instead of the private `ledger._log()`
- `exclude_paths` in `BaseMiddleware` is now a `set` (O(1) lookups)
- `_version.py` uses `importlib.metadata.version("ledger-sdk")` with a hardcoded fallback
- All internal `sys.stderr.write` calls replaced with `logging.getLogger("ledger")` calls
- Constraint keys in `Validator.__init__` are now required (`KeyError` on missing key) rather than silently falling back to defaults
- Buffer drop warnings are throttled to at most once every 5 seconds

## [1.2.2] - 2025-12-12

### Fixed

- Fixed RuntimeError when initializing LedgerClient at module level before event loop is running
- BackgroundFlusher now gracefully handles missing event loop and starts lazily on first log call
- Resolved "no running event loop" error in Flask and FastAPI applications

## [1.2.1] - 2025-12-09

### Changed

- Added comprehensive docstrings to LedgerClient class and all public methods for improved API documentation

## [1.2.0] - 2025-12-03

### Added

- **Flask support** - Full middleware integration for Flask applications
- Flask middleware uses `request.url_rule.rule` for exact parameter names
- Flask middleware auto-discovers `LedgerClient` from app config (`LEDGER_CLIENT` or `ledger`)
- Comprehensive test coverage for Flask integration (16 tests, 94% coverage)

### Changed

- Flask middleware normalizes path converters (`<int:user_id>` → `{user_id}`)
- Flask middleware `ledger_client` parameter is optional (auto-discovered from app.config)
- Added `examples/flask/` with complete working Flask application
- Updated documentation to include Flask in supported frameworks

## [1.1.0] - 2025-11-29

### Added

- **Django support** - Full middleware integration for Django applications
- Django middleware uses `request.resolver_match.route` for exact parameter names
- Django middleware auto-discovers `LedgerClient` from settings (`LEDGER_CLIENT` or `ledger`)
- Comprehensive test coverage for Django integration (14 tests, 84% coverage)

### Changed

- Django middleware normalizes path converters (`<int:user_id>` → `{user_id}`)
- Django middleware `ledger_client` parameter is optional (auto-discovered from settings)
- Simplified examples structure: `examples/fastapi/` and `examples/django/`

## [1.0.7] - 2025-11-29

### Fixed

- URL normalization pattern now handles base64-url-safe encoded IDs with underscores and hyphens
- FastAPI middleware now uses actual route patterns (e.g., `/users/{user_id}`) instead of generic normalized paths (e.g., `/users/{id}`)

### Changed

- FastAPI middleware prioritizes `request.scope["route"].path` for accurate parameter names
- Regex normalization serves as fallback for unmatched routes and 404s
- Updated documentation to emphasize framework routes over regex normalization

## [1.0.6] - 2025-11-26

### Added

- Automatic URL filtering to ignore bot traffic and malicious scanning attempts (/.git/, /robots.txt, .php files, etc.)
- URL path normalization for analytics grouping (/users/123 -> /users/{id})
- URLProcessor utility in core module for framework-agnostic URL processing
- BaseMiddleware class for shared middleware logic across frameworks
- Support for custom URL filtering patterns and normalization rules
- Configurable template style for path normalization (curly braces or colon style)

### Changed

- Refactored FastAPI middleware to inherit from BaseMiddleware (reduced from 141 to 74 lines)
- Updated integrations/**init**.py to prevent naming conflicts for future framework additions
- Improved code reuse with 80% of middleware logic now shared across frameworks

### Architecture

- Created scalable foundation for Flask, Django, and other framework integrations
- All filtering and normalization logic is framework-agnostic and reusable

## [1.0.5] - 2025-11-23

### Fixed

- Removed invalid `network` log type from validator (not supported by server)
- Fixed FastAPI middleware to use `log_type="endpoint"` instead of `"console"`
- Fixed FastAPI middleware attributes structure to nest endpoint data under `endpoint` key as required by server

## [1.0.4] - 2025-01-17

### Fixed

- Updated ingestion call with newest server API docs

## [1.0.3] - 2025-01-14

### Changed

- Hotfixed Ledger project api key prefix

## [1.0.2] - 2025-01-14

### Added

- Support for Pydantic Settings integration for configuration management
- Starlette compatibility improvements for FastAPI middleware

### Changed

- Updated dependencies to latest versions

## [1.0.1] - 2025-01-13

### Added

- config file instead of hard coded values

### Changed

- README.md with relevant links

## [1.0.0] - 2025-01-11

### Added

- Initial release of Ledger SDK for Python
- Core LedgerClient with automatic log buffering and batching
- FastAPI middleware integration for automatic request/response logging
- Non-blocking async operation with <0.1ms overhead
- Intelligent batching (every 5s or 100 logs)
- Dual rate limiting (per-minute and per-hour)
- Circuit breaker pattern (5 failure threshold, 60s timeout)
- Exponential backoff retry logic (max 3 retries)
- Comprehensive metrics and health checks
- Configuration validation on startup
- Graceful shutdown with connection draining
- Production-ready features for high-traffic APIs

### Features

- Automatic exception capture with full stack traces
- Structured logging to stderr
- HTTP connection pooling (10 persistent connections)
- Redis-compatible settings management
- Field validation and truncation
- Background flusher with async processing

### Integrations

- FastAPI (via LedgerMiddleware)

[1.3.0]: https://github.com/JakubTuta/ledger-sdk/compare/v1.2.2...v1.3.0
[1.2.2]: https://github.com/JakubTuta/ledger-sdk/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/JakubTuta/ledger-sdk/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/JakubTuta/ledger-sdk/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.7...v1.1.0
[1.0.7]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/JakubTuta/ledger-sdk/releases/tag/v1.0.0
