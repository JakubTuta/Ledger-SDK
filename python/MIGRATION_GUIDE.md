# Migration Guide

This document explains the changes made to restructure the Ledger SDK for multi-language support and PyPI best practices.

## What Changed

### Directory Structure

**Before:**
```
Ledger-SDK/
├── python/fastapi/
│   └── ledger/
```

**After:**
```
Ledger-SDK/
├── python/
│   ├── src/ledger/        # Source code (src layout)
│   │   ├── core/          # Framework-agnostic core
│   │   └── integrations/  # Framework integrations
│   ├── tests/             # Test suite
│   ├── examples/          # Usage examples
│   └── pyproject.toml     # Package configuration
│
├── javascript/            # Future: JS/TS SDK
└── ...                    # Future: Other language SDKs
```

### Import Changes

**Before:**
```python
from ledger.client import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware
```

**After:**
```python
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware
```

**Note:** The imports are actually simpler now! The main client is exported from the top-level package.

## Files Added

### Essential Package Files
- `src/ledger/__init__.py` - Package exports
- `src/ledger/_version.py` - Single source of truth for version
- `src/ledger/py.typed` - Type hints marker (PEP 561)
- `src/ledger/core/__init__.py` - Core module exports
- `src/ledger/integrations/__init__.py` - Integrations exports

### Packaging Files
- `LICENSE` - MIT License
- `MANIFEST.in` - Include non-Python files in distribution
- `setup.py` - Backward compatibility (calls setuptools)
- `CHANGELOG.md` - Version history

### Development Files
- `tests/` - Comprehensive test suite
  - `test_buffer.py`
  - `test_validator.py`
  - `test_client.py`
  - `integrations/test_fastapi.py`
  - `conftest.py` - Pytest fixtures
- `.github/workflows/` - CI/CD
  - `test.yml` - Run tests on multiple Python versions
  - `publish.yml` - Publish to PyPI on release
- `.gitignore` - Python project gitignore

### Documentation
- `python/README.md` - Moved from fastapi/README.md
- `python/MIGRATION_GUIDE.md` - This file
- `CHANGELOG.md` - Version history

## Files Modified

### pyproject.toml
- Updated to use `src` layout
- Added optional dependencies (`[fastapi]`, `[dev]`)
- Complete metadata with classifiers
- Tool configurations (black, ruff, mypy, pytest)

### Source Code
- Updated all internal imports to use `ledger.core.*` instead of `ledger.*`
- Version now imported from `ledger._version`

## Installation

### For Development
```powershell
cd python
pip install -e ".[dev]"
```

### For Users (after PyPI publication)
```powershell
# Core SDK only
pip install ledger-sdk

# With FastAPI support
pip install ledger-sdk[fastapi]

# All integrations
pip install ledger-sdk[all]
```

## Publishing to PyPI

### Prerequisites
1. Account on pypi.org
2. API token configured
3. Version bumped in `_version.py`
4. CHANGELOG.md updated

### Build and Test
```powershell
cd python

# Install build tools
pip install build twine

# Build distribution
python -m build

# Check distribution
twine check dist/*

# Test upload to TestPyPI
twine upload --repository testpypi dist/*
```

### Publish to PyPI
```powershell
# Upload to PyPI
twine upload dist/*
```

Or use GitHub Actions by creating a release on GitHub.

## Running Tests

```powershell
cd python

# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=ledger --cov-report=html

# Run specific test file
pytest tests/test_client.py

# Run integration tests only
pytest -m integration
```

## Cleanup Old Files

The old `fastapi/` directory should be removed after verifying the new structure works:

```powershell
cd python
Remove-Item -Recurse -Force fastapi/
```

## Troubleshooting

### Import errors
If you get import errors, make sure you've installed in editable mode:
```powershell
pip install -e ".[dev]"
```

### Tests failing
Make sure you're in the `python/` directory and have dev dependencies installed.

### Build errors
Ensure you have the latest setuptools:
```powershell
pip install --upgrade setuptools wheel build
```

## Benefits of New Structure

1. **Multi-language ready**: Easy to add JavaScript, Go, etc.
2. **PyPI best practices**: src layout, proper metadata, type hints
3. **Better testing**: Comprehensive test suite with CI/CD
4. **Cleaner imports**: Top-level package exports
5. **Professional packaging**: CHANGELOG, LICENSE, proper versioning
6. **Type safety**: py.typed marker for type checkers
7. **Development tools**: Configured linting, formatting, type checking

## Next Steps

1. Verify new structure works with your use cases
2. Run tests: `pytest`
3. Test local install: `pip install -e ".[dev]"`
4. Clean up old files: `rm -rf fastapi/`
5. Publish to PyPI (when ready)
