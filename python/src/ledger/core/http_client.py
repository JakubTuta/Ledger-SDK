import gzip
import json
from typing import Any

import httpx

from ledger._version import __version__


class HTTPClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 5.0,
        pool_size: int = 10,
        compress: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._compress = compress

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
                "User-Agent": f"ledger-sdk-python/{__version__}",
            },
        )

    async def post(
        self,
        path: str,
        json_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        body = json.dumps(json_data).encode()
        extra_headers: dict[str, str] = {}

        if self._compress:
            body = gzip.compress(body, compresslevel=6)
            extra_headers["Content-Encoding"] = "gzip"

        if headers:
            extra_headers.update(headers)

        response = await self._client.post(
            path,
            content=body,
            headers=extra_headers if extra_headers else None,
        )
        return response

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        response = await self._client.get(
            path,
            params=params,
            headers=headers,
        )
        return response

    async def close(self) -> None:
        await self._client.aclose()
