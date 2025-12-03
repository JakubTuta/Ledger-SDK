from unittest.mock import MagicMock

import pytest
from flask import Flask

from ledger import LedgerClient
from ledger.integrations.flask import LedgerMiddleware


class TestFlaskIntegration:
    @pytest.fixture
    def mock_ledger_client(self):
        client = MagicMock(spec=LedgerClient)
        client._log = MagicMock()
        client.log_exception = MagicMock()
        return client

    @pytest.fixture
    def app_with_middleware(self, mock_ledger_client):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["LEDGER_CLIENT"] = mock_ledger_client

        @app.route("/users/<int:user_id>")
        def get_user(user_id):
            return {"user_id": user_id}

        @app.route("/posts/<int:post_id>/comments/<int:comment_id>")
        def get_comment(post_id, comment_id):
            return {"post_id": post_id, "comment_id": comment_id}

        @app.route("/articles/<slug>")
        def get_article(slug):
            return {"slug": slug}

        @app.route("/files/<path:filepath>")
        def get_file(filepath):
            return {"filepath": filepath}

        @app.route("/sessions/<uuid:session_id>")
        def get_session(session_id):
            return {"session_id": str(session_id)}

        @app.route("/v2/match/active/<match_id>")
        def get_match(match_id):
            return {"match_id": match_id}

        @app.route("/error")
        def trigger_error():
            raise ValueError("Test error")

        @app.route("/health")
        def health():
            return {"status": "ok"}

        LedgerMiddleware(app, ledger_client=mock_ledger_client)

        return app, mock_ledger_client

    def test_middleware_logs_request(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        response = client.get("/users/123")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/users/{user_id}"

    def test_uses_route_path_not_normalized_path(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        response = client.get("/posts/456/comments/789")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/posts/{post_id}/comments/{comment_id}"

    def test_handles_int_converter(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        response = client.get("/users/123")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/users/{user_id}"

    def test_handles_string_converter(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        response = client.get("/articles/my-article")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/articles/{slug}"

    def test_handles_path_converter(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        response = client.get("/files/path/to/file.txt")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/files/{filepath}"

    def test_handles_uuid_converter(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        response = client.get("/sessions/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/sessions/{session_id}"

    def test_fallback_to_normalization_for_404(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        with pytest.raises(Exception):
            client.get("/nonexistent/123")

        assert mock_client.log_exception.called

        call_args = mock_client.log_exception.call_args
        logged_path = call_args.kwargs["attributes"]["path"]

        assert logged_path == "/nonexistent/{id}"

    def test_middleware_excludes_paths(self, mock_ledger_client):
        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/health")
        def health():
            return {"status": "ok"}

        LedgerMiddleware(
            app, ledger_client=mock_ledger_client, exclude_paths=["/health"]
        )

        client = app.test_client()
        response = client.get("/health")

        assert response.status_code == 200
        assert not mock_ledger_client._log.called

    def test_middleware_filters_ignored_paths(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        try:
            client.get("/robots.txt")
        except Exception:
            pass

        assert not mock_client._log.called
        assert not mock_client.log_exception.called

    def test_middleware_logs_exception(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        with pytest.raises(Exception):
            client.get("/error")

        assert mock_client.log_exception.called

        call_args = mock_client.log_exception.call_args
        logged_path = call_args.kwargs["attributes"]["path"]

        assert logged_path == "/error"

    def test_middleware_captures_query_params(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        response = client.get("/users/123?page=1&limit=10")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        query_params = call_args.kwargs["attributes"]["endpoint"].get("query_params")

        assert query_params == "page=1&limit=10"

    def test_middleware_can_disable_normalization(self, mock_ledger_client):
        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/users/<int:user_id>")
        def get_user(user_id):
            return {"user_id": user_id}

        LedgerMiddleware(app, ledger_client=mock_ledger_client, normalize_paths=False)

        client = app.test_client()
        response = client.get("/users/123")

        assert response.status_code == 200
        assert mock_ledger_client._log.called

        call_args = mock_ledger_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/users/123"

    def test_middleware_can_disable_filtering(self, mock_ledger_client):
        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/test")
        def test_route():
            return {"ok": True}

        LedgerMiddleware(
            app, ledger_client=mock_ledger_client, filter_ignored_paths=False
        )

        client = app.test_client()

        try:
            client.get("/robots.txt")
        except Exception:
            pass

        assert mock_ledger_client.log_exception.called

    def test_handles_base64_ids_with_route_path(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = app.test_client()

        long_id = "HzZdSjYiiTw9S_L9VfgtxhiYdHHlIeruc6frms50HMISlqooPYrTxK1qCGG9jYWOfzsKwDO6GC7a1Q"
        response = client.get(f"/v2/match/active/{long_id}")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/v2/match/active/{match_id}"

    def test_auto_discovers_client_from_config(self, mock_ledger_client):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["LEDGER_CLIENT"] = mock_ledger_client

        @app.route("/test")
        def test_route():
            return {"ok": True}

        LedgerMiddleware(app)

        client = app.test_client()
        response = client.get("/test")

        assert response.status_code == 200
        assert mock_ledger_client._log.called

    def test_raises_error_if_client_not_found(self):
        app = Flask(__name__)
        app.config["TESTING"] = True

        with pytest.raises(ValueError, match="LedgerClient not found"):
            LedgerMiddleware(app)
