"""Derive caller/origin metadata (channel, truncated IP, UA breakdown) from an
inbound request's headers and peer address.

Owns everything privacy- and spoofing-sensitive about this: IP truncation
happens here so a raw address never leaves the customer's process, and the
right-to-left `X-Forwarded-For` walk only trusts a header at all once the
direct TCP peer (`socket_ip`) is itself inside `trusted_proxies` -- otherwise
an attacker hitting the server directly could forge any client address they
want by sending their own `X-Forwarded-For` header.

`describe()` is the sole public entrypoint. It returns a flat dict of
`ledger.client.*` attributes with empty/default fields omitted entirely
(smaller export payloads, and callers can distinguish "not detected" from
"detected as falsy").
"""

import functools
import ipaddress
import re
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

import ledger._logging as logging_module

IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

# Cap applied both to the stored `user_agent` attribute and to the UA
# classifier's cache key. A single constant keeps them from drifting apart --
# if the cache were keyed on the untruncated string, a 100 KB attacker-
# supplied User-Agent would be retained verbatim in the LRU cache.
_MAX_USER_AGENT_CHARS = 512

_CRAWLER_UA_RE = re.compile(
    r"bot|crawl|spider|slurp|facebookexternalhit|lighthouse|headlesschrome", re.IGNORECASE
)
_TOOL_UA_RE = re.compile(
    r"curl/|wget|python-requests|httpx/|okhttp|go-http-client|java/|axios/|postman|insomnia",
    re.IGNORECASE,
)
_BROWSER_TOKEN_RE = re.compile(r"Chrome|Safari|Firefox|Edg|OPR")

_BROWSER_FAMILY_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"Edg/"), "Edge"),
    (re.compile(r"OPR/"), "Opera"),
    (re.compile(r"Chrome/"), "Chrome"),
    (re.compile(r"Firefox/"), "Firefox"),
    (re.compile(r"Safari/"), "Safari"),
)
_OS_FAMILY_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    # iOS UAs embed "like Mac OS X" (e.g. "CPU iPhone OS 17_0 like Mac OS X"),
    # so the iOS check must run before the macOS one or every iPhone/iPad
    # misclassifies as macOS.
    (re.compile(r"iPhone|iPad|iPod"), "iOS"),
    (re.compile(r"Windows"), "Windows"),
    (re.compile(r"Mac OS X"), "macOS"),
    (re.compile(r"Android"), "Android"),
    (re.compile(r"Linux"), "Linux"),
)
_TABLET_UA_RE = re.compile(r"iPad|Tablet|PlayBook|Kindle", re.IGNORECASE)
_MOBILE_UA_RE = re.compile(r"Mobile|iPhone|iPod", re.IGNORECASE)

# Priority order: the first CDN header present wins. Cloudflare's "XX" is a
# documented sentinel for "unknown country" and "T1" for Tor exit traffic --
# neither is a real ISO 3166-1 code, so both are rejected.
_CDN_COUNTRY_HEADERS: tuple[str, ...] = (
    "cf-ipcountry",
    "x-vercel-ip-country",
    "cloudfront-viewer-country",
    "fastly-client-country",
)
_CDN_COUNTRY_SENTINELS = frozenset({"XX", "T1"})

_AUTH_SCHEMES = frozenset({"bearer", "basic", "apikey"})


class _WarnOnceLatches:
    """Mutable holder for the one-time misconfiguration warning flags.

    An attribute-mutating object sidesteps `global` reassignment entirely,
    which keeps `_warn_*` free of module-global rebinding.
    """

    def __init__(self) -> None:
        self.missing_trusted_proxies = False
        self.private_after_walk = False


_warn_latches = _WarnOnceLatches()


def parse_trusted_proxies(raw: Sequence[str] | None) -> tuple[IpNetwork, ...]:
    """Parse `trusted_proxies` kwarg values once, at middleware construction.

    Invalid entries are dropped with a warning rather than raising, so a typo
    degrades to "trusted_proxies effectively unset" instead of crashing
    application startup.
    """
    if not raw:
        return ()

    networks: list[IpNetwork] = []
    for entry in raw:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logging_module.get_logger().warning(
                "Ledger: trusted_proxies entry %r is not a valid IP network, ignoring", entry
            )
    return tuple(networks)


def _in_any_network(
    addr: "ipaddress.IPv4Address | ipaddress.IPv6Address", networks: Sequence[IpNetwork]
) -> bool:
    return any(addr in network for network in networks)


def truncate_ip(ip_str: str) -> str | None:
    """Truncate an address to its /24 (IPv4) or /48 (IPv6) network prefix.

    Returns None if `ip_str` isn't a parseable IP address. Used both for the
    `ip_prefix` attribute below and directly by `integrations/common.py` to
    truncate the `client.address` span attribute -- a raw address must never
    leave the process on either path.
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return None
    prefix_len = 24 if isinstance(addr, ipaddress.IPv4Address) else 48
    network = ipaddress.ip_network(f"{addr}/{prefix_len}", strict=False)
    return str(network)


def _is_trusted_peer(socket_ip: str | None, trusted_networks: Sequence[IpNetwork]) -> bool:
    if not trusted_networks or not socket_ip:
        return False
    try:
        socket_addr = ipaddress.ip_address(socket_ip)
    except ValueError:
        return False
    return _in_any_network(socket_addr, trusted_networks)


def resolve_client_ip(
    headers: Mapping[str, str],
    socket_ip: str | None,
    trusted_networks: Sequence[IpNetwork],
) -> tuple[str | None, str]:
    """Resolve the real client address, honoring `trusted_proxies` if set.

    Returns `(ip, source)` where source is one of "socket", "xff",
    "x_real_ip", "cf". Falls back to `socket_ip`/"socket" whenever the
    direct peer isn't a trusted proxy -- an untrusted peer's headers are
    never consulted, since a header is just attacker-controlled input from
    that peer's point of view.
    """
    if not _is_trusted_peer(socket_ip, trusted_networks):
        return socket_ip, "socket"

    xff = headers.get("x-forwarded-for")
    if xff:
        candidates = [c.strip() for c in xff.split(",") if c.strip()]
        for candidate in reversed(candidates):
            try:
                candidate_addr = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if not _in_any_network(candidate_addr, trusted_networks):
                return candidate, "xff"

    x_real_ip = headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip, "x_real_ip"

    cf_connecting_ip = headers.get("cf-connecting-ip")
    if cf_connecting_ip:
        return cf_connecting_ip, "cf"

    return socket_ip, "socket"


def classify_channel(headers: Mapping[str, str]) -> str:
    """Classify a request as browser/API/bot traffic from headers alone.

    `bot` is a floor, not a ceiling: a spoofed User-Agent is indistinguishable
    from a real browser at header level, so nothing security-critical may be
    built on this classification.

    Rules are ordered, first match wins -- rule 6 (bearer/basic/apikey auth
    without a cookie) must stay above rules 7/9: an SSR proxy (e.g. a
    Nuxt/Next server calling the API) forwards the end user's browser
    User-Agent, and would otherwise misclassify as browser traffic.
    """
    user_agent = headers.get("user-agent", "")
    sec_fetch_mode = headers.get("sec-fetch-mode", "").lower()
    sec_fetch_dest = headers.get("sec-fetch-dest", "").lower()
    accept = headers.get("accept", "")
    auth_scheme = _extract_auth_scheme(headers)
    has_browser_token = user_agent.startswith("Mozilla/") and bool(
        _BROWSER_TOKEN_RE.search(user_agent)
    )

    rules: tuple[tuple[bool, str], ...] = (
        (bool(_CRAWLER_UA_RE.search(user_agent)), "bot"),
        (bool(_TOOL_UA_RE.search(user_agent)), "api_client"),
        (sec_fetch_mode == "navigate", "browser_navigation"),
        (
            sec_fetch_mode in {"cors", "same-origin", "no-cors"} or sec_fetch_dest == "empty",
            "browser_xhr",
        ),
        (headers.get("x-requested-with") == "XMLHttpRequest", "browser_xhr"),
        (auth_scheme in _AUTH_SCHEMES and "cookie" not in headers, "api_client"),
        (bool(headers.get("origin")) and has_browser_token, "browser_xhr"),
        (has_browser_token and accept.startswith("text/html"), "browser_navigation"),
        (has_browser_token, "browser_xhr"),
        ("application/json" in accept and not has_browser_token, "api_client"),
    )
    return next((result for matched, result in rules if matched), "unknown")


def _extract_auth_scheme(headers: Mapping[str, str]) -> str | None:
    authorization = headers.get("authorization")
    if not authorization:
        return None
    scheme = authorization.split(" ", 1)[0]
    return scheme.lower() if scheme else None


def _cap_user_agent(user_agent: str) -> str:
    return user_agent[:_MAX_USER_AGENT_CHARS]


@functools.lru_cache(maxsize=1024)
def _classify_user_agent(capped_user_agent: str) -> tuple[str | None, str | None, str | None]:
    browser_family = next(
        (name for pattern, name in _BROWSER_FAMILY_PATTERNS if pattern.search(capped_user_agent)),
        None,
    )
    os_family = next(
        (name for pattern, name in _OS_FAMILY_PATTERNS if pattern.search(capped_user_agent)),
        None,
    )
    if _TABLET_UA_RE.search(capped_user_agent):
        device = "tablet"
    elif _MOBILE_UA_RE.search(capped_user_agent):
        device = "mobile"
    elif browser_family is not None:
        device = "desktop"
    else:
        device = None
    return browser_family, os_family, device


def _extract_cdn_country(headers: Mapping[str, str]) -> str | None:
    for header_name in _CDN_COUNTRY_HEADERS:
        value = headers.get(header_name)
        if not value:
            continue
        code = value.strip().upper()
        if len(code) == 2 and code.isalpha() and code not in _CDN_COUNTRY_SENTINELS:
            return code
    return None


def _extract_locale(headers: Mapping[str, str]) -> str | None:
    accept_language = headers.get("accept-language")
    if not accept_language:
        return None
    primary = accept_language.split(",", 1)[0].split(";", 1)[0].strip()
    return primary or None


def _extract_referer_origin(headers: Mapping[str, str]) -> str | None:
    referer = headers.get("referer")
    if not referer:
        return None
    parts = urlsplit(referer)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def _warn_missing_trusted_proxies(observed_address: str) -> None:
    if _warn_latches.missing_trusted_proxies:
        return
    _warn_latches.missing_trusted_proxies = True
    logging_module.get_logger().warning(
        "Ledger: X-Forwarded-For present but trusted_proxies is not configured, so the "
        "recorded client address is your proxy (%s), not the visitor. Country will be "
        "empty. Fix: LedgerMiddleware(..., trusted_proxies=[...]).",
        observed_address,
    )


def _warn_private_after_walk(resolved_address: str) -> None:
    if _warn_latches.private_after_walk:
        return
    _warn_latches.private_after_walk = True
    logging_module.get_logger().warning(
        "Ledger: resolved client address (%s) is private/loopback even after applying "
        "trusted_proxies. This usually means trusted_proxies doesn't match the address "
        "your app actually receives connections from.",
        resolved_address,
    )


def _reset_warning_state() -> None:
    """Test-only: clear the one-time warning latches between test cases."""
    _warn_latches.missing_trusted_proxies = False
    _warn_latches.private_after_walk = False


def describe(
    headers: Mapping[str, str],
    socket_ip: str | None,
    trusted_networks: Sequence[IpNetwork] = (),
) -> dict[str, object]:
    """Derive the full `ledger.client.*` attribute set for one request."""
    normalized_headers = {k.lower(): v for k, v in headers.items()}

    ip, ip_source = resolve_client_ip(normalized_headers, socket_ip, trusted_networks)

    if not trusted_networks and socket_ip:
        proxy_header_present = any(
            normalized_headers.get(name)
            for name in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip")
        )
        if proxy_header_present:
            _warn_missing_trusted_proxies(socket_ip)
    elif trusted_networks and ip_source != "socket" and ip is not None:
        try:
            if ipaddress.ip_address(ip).is_private:
                _warn_private_after_walk(ip)
        except ValueError:
            pass

    result: dict[str, object] = {"ledger.client.channel": classify_channel(normalized_headers)}

    if ip is not None:
        ip_prefix = truncate_ip(ip)
        if ip_prefix is not None:
            result["ledger.client.ip_prefix"] = ip_prefix
            result["ledger.client.ip_source"] = ip_source

    cdn_country = _extract_cdn_country(normalized_headers)
    if cdn_country is not None:
        result["ledger.client.country"] = cdn_country

    raw_user_agent = normalized_headers.get("user-agent")
    if raw_user_agent:
        capped_user_agent = _cap_user_agent(raw_user_agent)
        result["ledger.client.user_agent"] = capped_user_agent
        browser_family, os_family, device = _classify_user_agent(capped_user_agent)
        if browser_family is not None:
            result["ledger.client.browser_family"] = browser_family
        if os_family is not None:
            result["ledger.client.os_family"] = os_family
        if device is not None:
            result["ledger.client.device"] = device

    referer_origin = _extract_referer_origin(normalized_headers)
    if referer_origin is not None:
        result["ledger.client.referer_origin"] = referer_origin

    origin = normalized_headers.get("origin")
    if origin:
        result["ledger.client.origin"] = origin

    sec_fetch_site = normalized_headers.get("sec-fetch-site")
    if sec_fetch_site:
        result["ledger.client.sec_fetch_site"] = sec_fetch_site

    sec_fetch_mode = normalized_headers.get("sec-fetch-mode")
    if sec_fetch_mode:
        result["ledger.client.sec_fetch_mode"] = sec_fetch_mode

    purpose = normalized_headers.get("sec-purpose") or normalized_headers.get("purpose")
    if purpose and "prefetch" in purpose.lower():
        result["ledger.client.prefetch"] = True

    auth_scheme = _extract_auth_scheme(normalized_headers)
    if auth_scheme is not None:
        result["ledger.client.auth_scheme"] = auth_scheme

    locale = _extract_locale(normalized_headers)
    if locale is not None:
        result["ledger.client.locale"] = locale

    request_id = normalized_headers.get("x-request-id")
    if request_id:
        result["ledger.client.request_id"] = request_id

    return result
