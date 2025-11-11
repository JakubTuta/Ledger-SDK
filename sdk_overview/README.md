# Ledger SDK Overview

This directory contains comprehensive documentation for the Ledger SDK project.

## Current Status: Phase 1 - Python SDK (FastAPI)

The SDK project Phase 1 is **production-ready**. Implementation is located in `../python/`. Version 1.0.0 includes:

- **Language**: Python 3.9+
- **Framework**: FastAPI (async-first web framework)
- **Package**: Available on PyPI as `ledger-sdk`
- **Core Features**:
  - Automatic endpoint traffic logging
  - Automatic error capture and reporting
  - Non-blocking async operation (<0.1ms overhead)
  - Intelligent batching and buffering
- **Production Features**:
  - Circuit breaker pattern (5 failure threshold, 60s timeout)
  - Exponential backoff retry logic (3 retries max)
  - Dual rate limiting (per-minute and per-hour)
  - Comprehensive metrics and monitoring
  - Health checks and diagnostics
  - Configuration validation on startup
  - Enhanced validation with detailed warnings
  - Graceful shutdown with connection draining

## Documentation Structure

### Core Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - High-level system architecture and data flow
- **[COMPONENTS.md](COMPONENTS.md)** - Detailed design of SDK components
- **[FASTAPI_INTEGRATION.md](FASTAPI_INTEGRATION.md)** - FastAPI middleware implementation strategy
- **[PERFORMANCE.md](PERFORMANCE.md)** - Performance optimization strategies
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration options and tuning
- **[ERROR_HANDLING.md](ERROR_HANDLING.md)** - Error handling and retry strategies

### Quick Reference

**Server API Reference**: See `../server_overview/SDK_REFERENCE.md` for REST API specification

**Server Architecture**: See `../server_overview/ARCHITECTURE.md` for backend system design

## Design Principles

1. **Non-Blocking Performance**: SDK operations never slow down client applications
2. **Fail Gracefully**: Buffer → Retry → Drop (only as last resort)
3. **Respect Server Limits**: Client-side rate limiting and batch size constraints
4. **Observable**: Clear error logging and metrics for debugging
5. **Configurable**: Tune behavior for different workloads
6. **Future-Proof**: Architecture designed for multi-language, multi-framework expansion

## Getting Started

### Using the SDK

**For end users:**

```bash
pip install ledger-sdk[fastapi]
```

See the [Python SDK README](../python/README.md) for complete quick start guide.

**For contributors:**

1. Clone the repository
2. Install in development mode: `cd python && pip install -e ".[dev]"`
3. Run tests: `pytest`
4. See `python/examples/basic_app.py` for a complete working example

### Understanding the Design

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) for system overview
2. Review [COMPONENTS.md](COMPONENTS.md) for implementation details
3. Check [FASTAPI_INTEGRATION.md](FASTAPI_INTEGRATION.md) for FastAPI specifics

## Project Vision

Ledger SDK aims to provide production-grade observability for high-performance applications across multiple languages and frameworks. Starting with Python/FastAPI, we will expand to support the entire modern web development ecosystem.
