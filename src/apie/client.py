from __future__ import annotations

from .http import (
    ApieClientOptions,
    AsyncApieClientOptions,
    AsyncHttpClient,
    HttpClient,
)
from .resources import AsyncHealthResource, HealthResource


class ApieClient:
    def __init__(self, options: ApieClientOptions) -> None:
        self._http = HttpClient(options)
        self.health = HealthResource(self._http)

    def close(self) -> None:
        self._http.close()


class AsyncApieClient:
    def __init__(self, options: AsyncApieClientOptions) -> None:
        self._http = AsyncHttpClient(options)
        self.health = AsyncHealthResource(self._http)

    async def aclose(self) -> None:
        await self._http.aclose()
