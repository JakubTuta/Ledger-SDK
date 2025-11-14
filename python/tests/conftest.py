from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def mock_http_client():
    client = Mock()
    client.post = AsyncMock()
    client.get = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def api_key():
    return "ledger_proj_1_test_key_12345"


@pytest.fixture
def base_url():
    return "http://localhost:8000"
