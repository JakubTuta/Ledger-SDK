import re

import pytest

from ledger.core.url_processor import URLProcessor


class TestURLProcessor:
    @pytest.fixture
    def default_processor(self):
        return URLProcessor()

    @pytest.fixture
    def no_filter_processor(self):
        return URLProcessor(filter_ignored_paths=False)

    @pytest.fixture
    def no_normalize_processor(self):
        return URLProcessor(normalize_paths=False)

    @pytest.fixture
    def colon_style_processor(self):
        return URLProcessor(template_style="colon")

    def test_filter_ignored_exact_paths(self, default_processor):
        assert default_processor.process_url("/robots.txt") is None
        assert default_processor.process_url("/favicon.ico") is None
        assert default_processor.process_url("/.env") is None
        assert default_processor.process_url("/ads.txt") is None

    def test_filter_ignored_prefixes(self, default_processor):
        assert default_processor.process_url("/.git/config") is None
        assert default_processor.process_url("/.git/HEAD") is None
        assert default_processor.process_url("/.well-known/security.txt") is None
        assert default_processor.process_url("/wp-admin/login.php") is None
        assert default_processor.process_url("/admin/panel") is None

    def test_filter_ignored_extensions(self, default_processor):
        assert default_processor.process_url("/api/test.php") is None
        assert default_processor.process_url("/script.asp") is None
        assert default_processor.process_url("/page.aspx") is None
        assert default_processor.process_url("/handler.jsp") is None

    def test_no_filter_allows_all(self, no_filter_processor):
        assert no_filter_processor.process_url("/robots.txt") == "/robots.txt"
        assert no_filter_processor.process_url("/.git/config") == "/.git/config"
        assert no_filter_processor.process_url("/test.php") == "/test.php"

    def test_normalize_numeric_ids(self, default_processor):
        assert default_processor.process_url("/users/123") == "/users/{id}"
        assert default_processor.process_url("/posts/456/comments") == "/posts/{id}/comments"
        assert default_processor.process_url("/api/v1/users/789") == "/api/v1/users/{id}"

    def test_normalize_uuid_paths(self, default_processor):
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert default_processor.process_url(f"/users/{uuid}") == "/users/{id}"
        assert default_processor.process_url(f"/api/sessions/{uuid}/data") == "/api/sessions/{id}/data"

    def test_normalize_mongodb_objectid(self, default_processor):
        object_id = "507f1f77bcf86cd799439011"
        assert default_processor.process_url(f"/posts/{object_id}") == "/posts/{id}"

    def test_normalize_long_identifiers(self, default_processor):
        long_hash = "a" * 30
        assert default_processor.process_url(f"/files/{long_hash}") == "/files/{id}"

    def test_normalize_base64_url_safe_identifiers(self, default_processor):
        base64_id = "HzZdSjYiiTw9S_L9VfgtxhiYdHHlIeruc6frms50HMISlqooPYrTxK1qCGG9jYWOfzsKwDO6GC7a1Q"
        assert default_processor.process_url(f"/v2/match/active/{base64_id}") == "/v2/match/active/{id}"

        base64_with_hyphen = "abc-def_ghi123456789012345"
        assert default_processor.process_url(f"/files/{base64_with_hyphen}") == "/files/{id}"

    def test_no_normalize_keeps_original(self, no_normalize_processor):
        assert no_normalize_processor.process_url("/users/123") == "/users/123"
        assert no_normalize_processor.process_url("/posts/456") == "/posts/456"

    def test_colon_style_templates(self, colon_style_processor):
        assert colon_style_processor.process_url("/users/123") == "/users/:id"
        assert colon_style_processor.process_url("/posts/456/edit") == "/posts/:id/edit"

    def test_preserve_valid_paths(self, default_processor):
        assert default_processor.process_url("/api/users") == "/api/users"
        assert default_processor.process_url("/health") == "/health"
        assert default_processor.process_url("/api/v1/status") == "/api/v1/status"

    def test_custom_ignored_paths(self):
        processor = URLProcessor(custom_ignored_paths=["/internal", "/debug"])
        assert processor.process_url("/internal") is None
        assert processor.process_url("/debug") is None
        assert processor.process_url("/api") == "/api"

    def test_custom_ignored_prefixes(self):
        processor = URLProcessor(custom_ignored_prefixes=["/private/", "/temp/"])
        assert processor.process_url("/private/data") is None
        assert processor.process_url("/temp/files") is None
        assert processor.process_url("/public/data") == "/public/data"

    def test_custom_ignored_extensions(self):
        processor = URLProcessor(custom_ignored_extensions=[".bak", ".old"])
        assert processor.process_url("/file.bak") is None
        assert processor.process_url("/config.old") is None
        assert processor.process_url("/file.txt") == "/file.txt"

    def test_custom_normalization_pattern(self):
        patterns = [
            (re.compile(r"/users/([a-z]+)"), "/users/{username}"),
            (re.compile(r"/posts/([a-z0-9-]+)"), "/posts/{slug}"),
        ]
        processor = URLProcessor(normalization_patterns=patterns)
        assert processor.process_url("/users/john") == "/users/{username}"
        assert processor.process_url("/posts/my-first-post") == "/posts/{slug}"

    def test_complex_path_normalization(self, default_processor):
        assert default_processor.process_url("/users/123/posts/456/comments/789") == "/users/{id}/posts/{id}/comments/{id}"

    def test_trailing_slash_handling(self, default_processor):
        assert default_processor.process_url("/users/123/") == "/users/{id}/"
        assert default_processor.process_url("/api/") == "/api/"

    def test_root_path(self, default_processor):
        assert default_processor.process_url("/") == "/"

    def test_query_params_not_in_path(self, default_processor):
        assert default_processor.process_url("/api/users") == "/api/users"

    def test_multiple_consecutive_ids(self, default_processor):
        assert default_processor.process_url("/a/123/b/456/c/789") == "/a/{id}/b/{id}/c/{id}"

    def test_should_ignore_path_method(self, default_processor):
        assert default_processor.should_ignore_path("/robots.txt") is True
        assert default_processor.should_ignore_path("/.git/config") is True
        assert default_processor.should_ignore_path("/api/users") is False

    def test_normalize_path_method(self, default_processor):
        assert default_processor.normalize_path("/users/123") == "/users/{id}"
        assert default_processor.normalize_path("/api/users") == "/api/users"
