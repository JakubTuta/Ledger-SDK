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
