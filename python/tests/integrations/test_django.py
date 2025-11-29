from unittest.mock import MagicMock, Mock

import pytest

from ledger import LedgerClient
from ledger.integrations.django import LedgerMiddleware


class MockResolverMatch:
    def __init__(self, route):
        self.route = route


class MockRequest:
    def __init__(self, path, method="GET", query_string="", route=None):
        self.path = path
        self.method = method
        self.META = {"QUERY_STRING": query_string} if query_string else {}
        if route:
            self.resolver_match = MockResolverMatch(route)
        else:
            self.resolver_match = None


class MockResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


class TestDjangoIntegration:
    @pytest.fixture
    def mock_ledger_client(self):
        client = MagicMock(spec=LedgerClient)
        client._log = MagicMock()
        client.log_exception = MagicMock()
        return client

    @pytest.fixture
    def get_response(self):
        def _get_response(request):
            return MockResponse(200)

        return _get_response

    @pytest.fixture
    def middleware(self, mock_ledger_client, get_response):
        return LedgerMiddleware(
            get_response=get_response, ledger_client=mock_ledger_client
        )

    def test_middleware_logs_request(self, middleware, mock_ledger_client):
        request = MockRequest("/users/123", route="users/<int:user_id>")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "users/{user_id}"

    def test_uses_route_path_not_normalized_path(self, middleware, mock_ledger_client):
        request = MockRequest("/posts/456/comments/789", route="posts/<post_id>/comments/<comment_id>")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "posts/{post_id}/comments/{comment_id}"

    def test_handles_converters_in_route(self, middleware, mock_ledger_client):
        request = MockRequest("/users/123", route="users/<int:user_id>")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "users/{user_id}"

    def test_handles_slug_converter(self, middleware, mock_ledger_client):
        request = MockRequest("/posts/my-first-post", route="posts/<slug:post_slug>")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "posts/{post_slug}"

    def test_handles_uuid_converter(self, middleware, mock_ledger_client):
        request = MockRequest(
            "/sessions/550e8400-e29b-41d4-a716-446655440000",
            route="sessions/<uuid:session_id>",
        )
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "sessions/{session_id}"

    def test_fallback_to_normalization_for_no_route(
        self, middleware, mock_ledger_client
    ):
        request = MockRequest("/nonexistent/123")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/nonexistent/{id}"

    def test_middleware_excludes_paths(self, mock_ledger_client, get_response):
        middleware = LedgerMiddleware(
            get_response=get_response,
            ledger_client=mock_ledger_client,
            exclude_paths=["/health", "/metrics"],
        )

        request = MockRequest("/health")
        response = middleware(request)

        assert response.status_code == 200
        assert not mock_ledger_client._log.called

    def test_middleware_filters_ignored_paths(self, middleware, mock_ledger_client):
        request = MockRequest("/robots.txt")
        response = middleware(request)

        assert response.status_code == 200
        assert not mock_ledger_client._log.called

    def test_middleware_logs_exception(self, mock_ledger_client):
        def get_response_with_exception(request):
            raise ValueError("Test exception")

        middleware = LedgerMiddleware(
            get_response=get_response_with_exception, ledger_client=mock_ledger_client
        )

        request = MockRequest("/users/123", route="users/<int:user_id>")

        with pytest.raises(ValueError):
            middleware(request)

        assert mock_ledger_client.log_exception.called

        call_args = mock_ledger_client.log_exception.call_args
        logged_path = call_args.kwargs["attributes"]["path"]

        assert logged_path == "users/{user_id}"

    def test_middleware_captures_query_params(self, middleware, mock_ledger_client):
        request = MockRequest("/users/123", route="users/<int:user_id>", query_string="page=1&limit=10")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        query_params = call_args.kwargs["attributes"]["endpoint"].get("query_params")

        assert query_params == "page=1&limit=10"

    def test_middleware_can_disable_normalization(self, mock_ledger_client, get_response):
        middleware = LedgerMiddleware(
            get_response=get_response,
            ledger_client=mock_ledger_client,
            normalize_paths=False,
        )

        request = MockRequest("/users/123")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/users/123"

    def test_middleware_can_disable_filtering(self, mock_ledger_client, get_response):
        middleware = LedgerMiddleware(
            get_response=get_response,
            ledger_client=mock_ledger_client,
            filter_ignored_paths=False,
        )

        request = MockRequest("/robots.txt")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

    def test_handles_base64_ids_with_route_path(self, middleware, mock_ledger_client):
        long_id = "HzZdSjYiiTw9S_L9VfgtxhiYdHHlIeruc6frms50HMISlqooPYrTxK1qCGG9jYWOfzsKwDO6GC7a1Q"
        request = MockRequest(
            f"/v2/match/active/{long_id}",
            route="v2/match/active/<str:match_id>",
        )
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "v2/match/active/{match_id}"

    def test_normalizes_path_without_converter(self, middleware, mock_ledger_client):
        request = MockRequest("/items/abc123", route="items/<item_id>")
        response = middleware(request)

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "items/{item_id}"
