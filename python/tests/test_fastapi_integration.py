from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware


class TestFastAPIIntegration:
    @pytest.fixture
    def mock_ledger_client(self):
        client = MagicMock(spec=LedgerClient)
        client._log = MagicMock()
        return client

    @pytest.fixture
    def app_with_middleware(self, mock_ledger_client):
        app = FastAPI()

        @app.get("/users/{user_id}")
        async def get_user(user_id: int):
            return {"user_id": user_id}

        @app.get("/posts/{post_id}/comments/{comment_id}")
        async def get_comment(post_id: int, comment_id: int):
            return {"post_id": post_id, "comment_id": comment_id}

        @app.get("/v2/match/active/{match_id}")
        async def get_active_match(match_id: str):
            return {"match_id": match_id}

        app.add_middleware(LedgerMiddleware, ledger_client=mock_ledger_client)
        return app, mock_ledger_client

    def test_uses_route_path_not_normalized_path(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = TestClient(app)

        response = client.get("/users/123")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/users/{user_id}"

    def test_preserves_parameter_names_from_route(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = TestClient(app)

        response = client.get("/posts/456/comments/789")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/posts/{post_id}/comments/{comment_id}"

    def test_handles_base64_ids_with_route_path(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = TestClient(app)

        long_id = "HzZdSjYiiTw9S_L9VfgtxhiYdHHlIeruc6frms50HMISlqooPYrTxK1qCGG9jYWOfzsKwDO6GC7a1Q"
        response = client.get(f"/v2/match/active/{long_id}")

        assert response.status_code == 200
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/v2/match/active/{match_id}"

    def test_fallback_to_normalization_for_404(self, app_with_middleware):
        app, mock_client = app_with_middleware
        client = TestClient(app)

        response = client.get("/nonexistent/123")

        assert response.status_code == 404
        assert mock_client._log.called

        call_args = mock_client._log.call_args
        logged_path = call_args.kwargs["attributes"]["endpoint"]["path"]

        assert logged_path == "/nonexistent/{id}"
