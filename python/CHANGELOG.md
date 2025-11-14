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

[1.0.2]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/JakubTuta/ledger-sdk/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/JakubTuta/ledger-sdk/releases/tag/v1.0.0
