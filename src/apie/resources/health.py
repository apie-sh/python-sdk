from __future__ import annotations

from typing import Any

from ..http import AsyncHttpClient, HttpClient


class HealthResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_info(self) -> dict[str, Any]:
        return self._http.get("/")

    def check(self) -> dict[str, Any]:
        return self._http.get("/health")


class AsyncHealthResource:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def get_info(self) -> dict[str, Any]:
        return await self._http.get("/")

    async def check(self) -> dict[str, Any]:
        return await self._http.get("/health")
