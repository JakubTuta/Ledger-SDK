from typing import Any

import httpx


class HTTPClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 5.0,
        pool_size: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=pool_size,
                max_keepalive_connections=pool_size,
                keepalive_expiry=30.0,
            ),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ledger-sdk-python/1.0.0",
            },
        )

    async def post(
        self,
        path: str,
        json_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        merged_headers = self._client.headers.copy()
        if headers:
            merged_headers.update(headers)

        response = await self._client.post(
            path,
            json=json_data,
            headers=merged_headers,
        )
        return response

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        merged_headers = self._client.headers.copy()
        if headers:
            merged_headers.update(headers)

        response = await self._client.get(
            path,
            params=params,
            headers=merged_headers,
        )
        return response

    async def close(self) -> None:
        await self._client.aclose()
