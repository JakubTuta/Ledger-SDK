import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware


class TestFastAPIIntegration:
    @pytest.mark.asyncio
    async def test_middleware_logs_request(self, api_key, base_url):
        app = FastAPI()
        ledger = LedgerClient(api_key=api_key, base_url=base_url)

        app.add_middleware(
            LedgerMiddleware,
            ledger_client=ledger,
            exclude_paths=["/health"],
        )

        @app.get("/")
        async def root():
            return {"message": "Hello World"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")

            assert response.status_code == 200
            assert response.json() == {"message": "Hello World"}

        await ledger.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_middleware_excludes_paths(self, api_key, base_url):
        app = FastAPI()
        ledger = LedgerClient(api_key=api_key, base_url=base_url)

        app.add_middleware(
            LedgerMiddleware,
            ledger_client=ledger,
            exclude_paths=["/health"],
        )

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

            assert response.status_code == 200

        await ledger.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_middleware_logs_exception(self, api_key, base_url):
        app = FastAPI()
        ledger = LedgerClient(api_key=api_key, base_url=base_url)

        app.add_middleware(
            LedgerMiddleware,
            ledger_client=ledger,
        )

        @app.get("/error")
        async def error():
            raise ValueError("Test error")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with pytest.raises(ValueError):
                await client.get("/error")

        await ledger.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_middleware_filters_ignored_paths(self, api_key, base_url):
        app = FastAPI()
        ledger = LedgerClient(api_key=api_key, base_url=base_url)

        app.add_middleware(
            LedgerMiddleware,
            ledger_client=ledger,
        )

        @app.get("/robots.txt")
        async def robots():
            return {"message": "robots"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/robots.txt")

            assert response.status_code == 200

        await ledger.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_middleware_normalizes_paths(self, api_key, base_url):
        app = FastAPI()
        ledger = LedgerClient(api_key=api_key, base_url=base_url)

        app.add_middleware(
            LedgerMiddleware,
            ledger_client=ledger,
        )

        @app.get("/users/{user_id}")
        async def get_user(user_id: int):
            return {"user_id": user_id}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/users/123")

            assert response.status_code == 200
            assert response.json() == {"user_id": 123}

        await ledger.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_middleware_can_disable_filtering(self, api_key, base_url):
        app = FastAPI()
        ledger = LedgerClient(api_key=api_key, base_url=base_url)

        app.add_middleware(
            LedgerMiddleware,
            ledger_client=ledger,
            filter_ignored_paths=False,
        )

        @app.get("/robots.txt")
        async def robots():
            return {"message": "robots"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/robots.txt")

            assert response.status_code == 200

        await ledger.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_middleware_can_disable_normalization(self, api_key, base_url):
        app = FastAPI()
        ledger = LedgerClient(api_key=api_key, base_url=base_url)

        app.add_middleware(
            LedgerMiddleware,
            ledger_client=ledger,
            normalize_paths=False,
        )

        @app.get("/users/{user_id}")
        async def get_user(user_id: int):
            return {"user_id": user_id}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/users/123")

            assert response.status_code == 200
            assert response.json() == {"user_id": 123}

        await ledger.shutdown(timeout=0.1)
