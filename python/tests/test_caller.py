import pytest

import ledger.core.caller as caller_module


@pytest.fixture(autouse=True)
def _reset_caller_warnings():
    caller_module._reset_warning_state()
    yield
    caller_module._reset_warning_state()


class TestTruncateIp:
    def test_ipv4_truncates_to_slash_24(self):
        assert caller_module.truncate_ip("203.0.113.42") == "203.0.113.0/24"

    def test_ipv6_truncates_to_slash_48(self):
        assert caller_module.truncate_ip("2001:db8:abcd:1234::1") == "2001:db8:abcd::/48"

    def test_invalid_address_returns_none(self):
        assert caller_module.truncate_ip("not-an-ip") is None

    def test_private_address_still_truncates(self):
        assert caller_module.truncate_ip("10.1.2.3") == "10.1.2.0/24"


class TestResolveClientIp:
    def test_no_trusted_proxies_uses_socket(self):
        headers = {"x-forwarded-for": "1.2.3.4"}
        ip, source = caller_module.resolve_client_ip(headers, "9.9.9.9", ())
        assert (ip, source) == ("9.9.9.9", "socket")

    def test_untrusted_socket_peer_ignores_xff(self):
        # Attacker hits the server directly and forges XFF; socket peer is
        # not in trusted_proxies, so the header must never be consulted.
        trusted = caller_module.parse_trusted_proxies(["10.0.0.0/8"])
        headers = {"x-forwarded-for": "1.2.3.4"}
        ip, source = caller_module.resolve_client_ip(headers, "6.6.6.6", trusted)
        assert (ip, source) == ("6.6.6.6", "socket")

    def test_trusted_socket_peer_walks_xff_right_to_left(self):
        trusted = caller_module.parse_trusted_proxies(["10.0.0.0/8"])
        headers = {"x-forwarded-for": "198.51.100.7, 10.0.0.5"}
        ip, source = caller_module.resolve_client_ip(headers, "10.0.0.5", trusted)
        assert (ip, source) == ("198.51.100.7", "xff")

    def test_trusted_socket_peer_skips_multiple_trusted_hops(self):
        trusted = caller_module.parse_trusted_proxies(["10.0.0.0/8"])
        headers = {"x-forwarded-for": "198.51.100.7, 10.0.0.1, 10.0.0.5"}
        ip, source = caller_module.resolve_client_ip(headers, "10.0.0.5", trusted)
        assert (ip, source) == ("198.51.100.7", "xff")

    def test_forged_left_hand_entry_is_unreachable(self):
        # A conforming proxy appends; it never rewrites earlier hops. Even if
        # an attacker prepends a forged entry, walking right-to-left from the
        # trusted end reaches the real client before ever seeing it.
        trusted = caller_module.parse_trusted_proxies(["10.0.0.0/8"])
        headers = {"x-forwarded-for": "1.1.1.1, 198.51.100.7, 10.0.0.5"}
        ip, source = caller_module.resolve_client_ip(headers, "10.0.0.5", trusted)
        assert (ip, source) == ("198.51.100.7", "xff")

    def test_falls_back_to_x_real_ip(self):
        trusted = caller_module.parse_trusted_proxies(["10.0.0.0/8"])
        headers = {"x-real-ip": "198.51.100.7"}
        ip, source = caller_module.resolve_client_ip(headers, "10.0.0.5", trusted)
        assert (ip, source) == ("198.51.100.7", "x_real_ip")

    def test_falls_back_to_cf_connecting_ip(self):
        trusted = caller_module.parse_trusted_proxies(["10.0.0.0/8"])
        headers = {"cf-connecting-ip": "198.51.100.7"}
        ip, source = caller_module.resolve_client_ip(headers, "10.0.0.5", trusted)
        assert (ip, source) == ("198.51.100.7", "cf")

    def test_no_headers_falls_back_to_socket_even_when_trusted(self):
        trusted = caller_module.parse_trusted_proxies(["10.0.0.0/8"])
        ip, source = caller_module.resolve_client_ip({}, "10.0.0.5", trusted)
        assert (ip, source) == ("10.0.0.5", "socket")

    def test_invalid_trusted_proxy_entries_are_dropped(self):
        trusted = caller_module.parse_trusted_proxies(["not-a-cidr", "10.0.0.0/8"])
        assert len(trusted) == 1


class TestClassifyChannel:
    def test_bot_from_crawler_ua(self):
        headers = {"user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
        assert caller_module.classify_channel(headers) == "bot"

    def test_headless_chrome_is_bot(self):
        headers = {"user-agent": "Mozilla/5.0 HeadlessChrome/120.0"}
        assert caller_module.classify_channel(headers) == "bot"

    def test_api_client_from_curl(self):
        headers = {"user-agent": "curl/8.4.0"}
        assert caller_module.classify_channel(headers) == "api_client"

    def test_api_client_from_python_requests(self):
        headers = {"user-agent": "python-requests/2.31.0"}
        assert caller_module.classify_channel(headers) == "api_client"

    def test_browser_navigation_from_sec_fetch_mode(self):
        headers = {
            "user-agent": "Mozilla/5.0 Chrome/120.0",
            "sec-fetch-mode": "navigate",
        }
        assert caller_module.classify_channel(headers) == "browser_navigation"

    def test_browser_xhr_from_sec_fetch_mode_cors(self):
        headers = {
            "user-agent": "Mozilla/5.0 Chrome/120.0",
            "sec-fetch-mode": "cors",
        }
        assert caller_module.classify_channel(headers) == "browser_xhr"

    def test_browser_xhr_from_sec_fetch_dest_empty(self):
        headers = {
            "user-agent": "Mozilla/5.0 Chrome/120.0",
            "sec-fetch-dest": "empty",
        }
        assert caller_module.classify_channel(headers) == "browser_xhr"

    def test_browser_xhr_from_x_requested_with(self):
        headers = {
            "user-agent": "Mozilla/5.0 Chrome/120.0",
            "x-requested-with": "XMLHttpRequest",
        }
        assert caller_module.classify_channel(headers) == "browser_xhr"

    def test_bearer_without_cookie_is_api_client(self):
        headers = {
            "user-agent": "Mozilla/5.0 Chrome/120.0",
            "authorization": "Bearer abc123",
        }
        assert caller_module.classify_channel(headers) == "api_client"

    def test_ssr_proxy_with_forwarded_browser_ua_stays_api_client(self):
        # Rule 6 must outrank 7/9: a Nuxt/Next SSR proxy calling the API
        # forwards the end user's browser UA and Origin, but authenticates
        # with a bearer token and no cookie -- it must not read as browser
        # traffic.
        headers = {
            "user-agent": "Mozilla/5.0 Chrome/120.0",
            "authorization": "Bearer server-side-token",
            "origin": "https://app.example.com",
        }
        assert caller_module.classify_channel(headers) == "api_client"

    def test_bearer_with_cookie_is_not_api_client(self):
        headers = {
            "user-agent": "Mozilla/5.0 Chrome/120.0",
            "authorization": "Bearer abc123",
            "cookie": "session=xyz",
        }
        assert caller_module.classify_channel(headers) != "api_client"

    def test_no_sec_fetch_safari_with_origin_is_browser_xhr(self):
        # Safari only shipped Sec-Fetch-* in 16.4; this is the documented
        # fallback path for older Safari making an in-page fetch().
        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 Safari/605.1.15",
            "origin": "https://app.example.com",
        }
        assert caller_module.classify_channel(headers) == "browser_xhr"

    def test_no_sec_fetch_safari_html_navigation(self):
        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 Safari/605.1.15",
            "accept": "text/html,application/xhtml+xml",
        }
        assert caller_module.classify_channel(headers) == "browser_navigation"

    def test_json_accept_without_browser_token_is_api_client(self):
        headers = {"user-agent": "MyServiceClient/1.0", "accept": "application/json"}
        assert caller_module.classify_channel(headers) == "api_client"

    def test_spoofed_bot_ua_still_wins_as_bot(self):
        # Documented false negative: header-level classification cannot
        # distinguish a spoofed UA from a real crawler.
        headers = {"user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://google.com/bot)"}
        assert caller_module.classify_channel(headers) == "bot"

    def test_no_signals_is_unknown(self):
        assert caller_module.classify_channel({}) == "unknown"


class TestCdnCountry:
    def test_cloudflare_header(self):
        assert caller_module._extract_cdn_country({"cf-ipcountry": "de"}) == "DE"

    def test_vercel_header(self):
        assert caller_module._extract_cdn_country({"x-vercel-ip-country": "US"}) == "US"

    def test_unknown_sentinel_rejected(self):
        assert caller_module._extract_cdn_country({"cf-ipcountry": "XX"}) is None

    def test_tor_sentinel_rejected(self):
        assert caller_module._extract_cdn_country({"cf-ipcountry": "T1"}) is None

    def test_no_header_returns_none(self):
        assert caller_module._extract_cdn_country({}) is None

    def test_priority_order_first_header_wins(self):
        headers = {"cf-ipcountry": "DE", "x-vercel-ip-country": "US"}
        assert caller_module._extract_cdn_country(headers) == "DE"


class TestDescribe:
    def test_ua_over_512_chars_is_capped(self):
        long_ua = "Mozilla/5.0 Chrome/120.0 " + ("a" * 600)
        result = caller_module.describe({"user-agent": long_ua}, "203.0.113.5")
        assert len(result["ledger.client.user_agent"]) == 512

    def test_empty_optional_fields_are_omitted(self):
        result = caller_module.describe({}, None)
        assert result == {"ledger.client.channel": "unknown"}

    def test_ip_prefix_and_source_present_together(self):
        result = caller_module.describe({}, "203.0.113.5")
        assert result["ledger.client.ip_prefix"] == "203.0.113.0/24"
        assert result["ledger.client.ip_source"] == "socket"

    def test_referer_reduced_to_origin_only(self):
        headers = {"referer": "https://example.com/reset-password?token=secret123"}
        result = caller_module.describe(headers, None)
        assert result["ledger.client.referer_origin"] == "https://example.com"
        assert "token" not in str(result)

    def test_locale_reduced_to_primary_tag(self):
        headers = {"accept-language": "en-US,en;q=0.9,fr;q=0.8"}
        result = caller_module.describe(headers, None)
        assert result["ledger.client.locale"] == "en-US"

    def test_browser_family_and_device_populated(self):
        headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        result = caller_module.describe(headers, None)
        assert result["ledger.client.browser_family"] == "Chrome"
        assert result["ledger.client.os_family"] == "Windows"
        assert result["ledger.client.device"] == "desktop"

    def test_mobile_device_detected(self):
        headers = {
            "user-agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 Safari/604.1"
            )
        }
        result = caller_module.describe(headers, None)
        assert result["ledger.client.device"] == "mobile"
        assert result["ledger.client.os_family"] == "iOS"

    def test_missing_trusted_proxies_warns_once(self, caplog):
        with caplog.at_level("WARNING", logger="ledger"):
            caller_module.describe({"x-forwarded-for": "1.2.3.4"}, "9.9.9.9")
            caller_module.describe({"x-forwarded-for": "1.2.3.4"}, "9.9.9.9")

        warnings = [r for r in caplog.records if "trusted_proxies is not configured" in r.message]
        assert len(warnings) == 1
        assert "9.9.9.9" in warnings[0].message

    def test_private_after_walk_warns_once(self, caplog):
        trusted = caller_module.parse_trusted_proxies(["203.0.113.0/24"])
        with caplog.at_level("WARNING", logger="ledger"):
            caller_module.describe({"x-forwarded-for": "10.1.2.3"}, "203.0.113.5", trusted)
            caller_module.describe({"x-forwarded-for": "10.1.2.3"}, "203.0.113.5", trusted)

        warnings = [r for r in caplog.records if "private/loopback" in r.message]
        assert len(warnings) == 1

    def test_no_warning_when_trusted_proxies_configured_and_resolves_public(self, caplog):
        # 203.0.113.0/24 (the trusted proxy network) is an RFC 5737
        # documentation range, but that's irrelevant to trust matching --
        # only the *resolved* address (8.8.8.8, genuinely global) must be
        # non-private for this assertion to hold.
        trusted = caller_module.parse_trusted_proxies(["203.0.113.0/24"])
        with caplog.at_level("WARNING", logger="ledger"):
            caller_module.describe({"x-forwarded-for": "8.8.8.8"}, "203.0.113.5", trusted)

        assert len(caplog.records) == 0
