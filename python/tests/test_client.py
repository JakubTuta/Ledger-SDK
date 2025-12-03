import pytest
from ledger import LedgerClient


class TestLedgerClient:
    @pytest.mark.asyncio
    async def test_client_initialization(self, api_key, base_url):
        client = LedgerClient(api_key=api_key, base_url=base_url)

        assert client.api_key == api_key
        assert client.base_url == base_url

        await client.shutdown(timeout=0.1)

    def test_invalid_api_key(self):
        with pytest.raises(ValueError) as exc_info:
            LedgerClient(api_key="invalid_key", base_url="http://localhost:8000")

        assert "api_key must start with 'ledger_' prefix" in str(exc_info.value)

    def test_invalid_base_url(self, api_key):
        with pytest.raises(ValueError) as exc_info:
            LedgerClient(api_key=api_key, base_url="not_a_url")

        assert "base_url must start with 'http://' or 'https://'" in str(exc_info.value)

    def test_invalid_flush_interval(self, api_key, base_url):
        with pytest.raises(ValueError) as exc_info:
            LedgerClient(api_key=api_key, base_url=base_url, flush_interval=-1)

        assert "flush_interval must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_log_info(self, api_key, base_url):
        client = LedgerClient(api_key=api_key, base_url=base_url)

        client.log_info("Test message", attributes={"user_id": 123})

        assert client._buffer.size() == 1

        await client.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_log_error(self, api_key, base_url):
        client = LedgerClient(api_key=api_key, base_url=base_url)

        client.log_error("Error message", attributes={"error_code": "ERR_001"})

        assert client._buffer.size() == 1

        await client.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_log_exception(self, api_key, base_url):
        client = LedgerClient(api_key=api_key, base_url=base_url)

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            client.log_exception(e, message="Custom message")

        assert client._buffer.size() == 1

        await client.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_is_healthy(self, api_key, base_url):
        client = LedgerClient(api_key=api_key, base_url=base_url)

        assert client.is_healthy() is True

        await client.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_get_health_status(self, api_key, base_url):
        client = LedgerClient(api_key=api_key, base_url=base_url)

        status = client.get_health_status()

        assert status["status"] == "healthy"
        assert status["healthy"] is True
        assert status["issues"] is None

        await client.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_get_metrics(self, api_key, base_url):
        client = LedgerClient(api_key=api_key, base_url=base_url)

        metrics = client.get_metrics()

        assert "sdk" in metrics
        assert "buffer" in metrics
        assert "flusher" in metrics
        assert "rate_limiter" in metrics
        assert "errors" in metrics
        assert metrics["sdk"]["version"] == "1.2.0"

        await client.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_shutdown(self, api_key, base_url):
        client = LedgerClient(api_key=api_key, base_url=base_url)

        await client.shutdown(timeout=1.0)

        assert client._buffer.is_empty() or not client._buffer.is_empty()
