"""Built-in PII scrubbers usable as (or composed into) a `before_send` hook.

These are opt-in: `LedgerLogRecordProcessor` never applies them unless a
caller builds a scrubbing `before_send` (see `build_pii_scrubber`) and wires
it in explicitly, or constructs `LedgerClient(..., scrub_pii=True)`.

Each scrubber takes and returns the same `before_send` record shape:
    {"body": ..., "attributes": {...}, "severity_number": ..., "severity_text": ...}
and mutates it in place (also returning it, so scrubbers can be chained with
a simple reduce via `build_pii_scrubber`).
"""

import re
from collections.abc import Callable, Sequence
from typing import Any

REDACTED = "[REDACTED]"

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Matches common credit-card groupings (13-19 digits, optionally separated
# into groups of 4 by spaces or dashes). Intentionally conservative to avoid
# clobbering unrelated numeric IDs.
_CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[ -]?){3}\d{1,4}\b")

# Attribute keys (case-insensitive, dashes/underscores normalized) treated as
# sensitive HTTP headers regardless of where they end up in `.attributes`.
_SENSITIVE_HEADER_KEYS = frozenset(
    {
        "authorization",
        "x-api-key",
        "x-auth-token",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        "x-csrf-token",
    }
)

# Substrings that, when found in an attribute key (case-insensitive), mark
# the value as a likely secret regardless of exact header naming.
_SENSITIVE_KEY_SUBSTRINGS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
)


def _normalize_key(key: str) -> str:
    return key.lower().replace("_", "-")


def scrub_emails(record: dict[str, Any]) -> dict[str, Any] | None:
    """Redact email-like substrings from the log body."""
    body = record.get("body")
    if isinstance(body, str):
        record["body"] = _EMAIL_RE.sub(REDACTED, body)
    return record


def scrub_credit_cards(record: dict[str, Any]) -> dict[str, Any] | None:
    """Redact credit-card-like digit sequences from the log body."""
    body = record.get("body")
    if isinstance(body, str):
        record["body"] = _CREDIT_CARD_RE.sub(REDACTED, body)
    return record


def scrub_sensitive_headers(record: dict[str, Any]) -> dict[str, Any] | None:
    """Redact attribute values whose key names a known sensitive HTTP header.

    Matches by attribute key name (e.g. `http.request.header.authorization`,
    `Authorization`, `X-API-Key`), not by scanning attribute values, since
    that's both cheaper and more reliable.
    """
    attributes = record.get("attributes")
    if isinstance(attributes, dict):
        for key in list(attributes.keys()):
            normalized = _normalize_key(key)
            if (
                normalized in _SENSITIVE_HEADER_KEYS
                or normalized.rsplit(".", 1)[-1].replace("_", "-") in _SENSITIVE_HEADER_KEYS
            ):
                attributes[key] = REDACTED
    return record


def scrub_secret_keys(record: dict[str, Any]) -> dict[str, Any] | None:
    """Redact attribute values whose key name looks like a secret.

    Matches attribute keys containing common secret-ish substrings
    (password, secret, token, api_key, ...) case-insensitively.
    """
    attributes = record.get("attributes")
    if isinstance(attributes, dict):
        for key in list(attributes.keys()):
            lowered = key.lower()
            if any(substring in lowered for substring in _SENSITIVE_KEY_SUBSTRINGS):
                attributes[key] = REDACTED
    return record


DEFAULT_SCRUBBERS: tuple[Callable[[dict[str, Any]], dict[str, Any] | None], ...] = (
    scrub_sensitive_headers,
    scrub_secret_keys,
    scrub_emails,
    scrub_credit_cards,
)


def build_pii_scrubber(
    scrubbers: Sequence[Callable[[dict[str, Any]], dict[str, Any] | None]] = DEFAULT_SCRUBBERS,
) -> Callable[[dict[str, Any]], dict[str, Any] | None]:
    """Compose a list of scrubbers into a single `before_send`-shaped callable.

    Runs each scrubber in order; if any scrubber returns None, the record is
    dropped and later scrubbers are skipped.

    Example:
        >>> before_send = build_pii_scrubber()
        >>> client = LedgerClient(api_key="ledger_...", before_send=before_send)
    """

    def _scrub(record: dict[str, Any]) -> dict[str, Any] | None:
        current: dict[str, Any] | None = record
        for scrubber in scrubbers:
            if current is None:
                return None
            current = scrubber(current)
        return current

    return _scrub
