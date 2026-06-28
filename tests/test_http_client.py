from __future__ import annotations

import json

import httpx
import pytest

from apie.client import ApieClient
from apie.errors import ApieError
from apie.http import (
    ApieClientOptions,
    AsyncApieClientOptions,
    AsyncHttpClient,
    HttpClient,
)


def _json_response(
    data: dict, status_code: int = 200, headers: dict | None = None
) -> httpx.Response:
    return httpx.Response(
        status_code,
        headers={"content-type": "application/json", **(headers or {})},
        text=json.dumps(data),
    )


def test_http_client_get_and_auth_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        assert request.headers.get("Authorization") == "Bearer test_key"
        return _json_response({"status": "ok", "database": "connected"})

    client = HttpClient(
        ApieClientOptions(
            base_url="http://localhost:3000",
            api_key="test_key",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )

    assert client.get("/health") == {"status": "ok", "database": "connected"}


def test_http_client_raises_apie_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(
            {"error": "unavailable"},
            status_code=503,
            headers={"x-request-id": "req_123", "retry-after": "2"},
        )

    client = HttpClient(
        ApieClientOptions(
            base_url="http://localhost:3000",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )

    with pytest.raises(ApieError) as exc:
        client.get("/health")

    assert exc.value.status == 503
    assert exc.value.request_id == "req_123"
    assert exc.value.retry_after_ms == 2000
    assert exc.value.body == {"error": "unavailable"}


def test_http_client_timeout_maps_to_408() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    client = HttpClient(
        ApieClientOptions(
            base_url="http://localhost:3000",
            timeout=50,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )

    with pytest.raises(ApieError) as exc:
        client.get("/")

    assert exc.value.status == 408
    assert str(exc.value) == "Request timed out"


@pytest.mark.asyncio
async def test_async_http_client_basics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/"
        return _json_response({"name": "apie", "status": "ok"})

    client = AsyncHttpClient(
        AsyncApieClientOptions(
            base_url="http://localhost:3000",
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
    )
    assert await client.get("/") == {"name": "apie", "status": "ok"}


def test_apie_client_health_resource() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return _json_response({"name": "apie", "status": "ok"})
        return _json_response({"status": "ok", "database": "connected"})

    client = ApieClient(
        ApieClientOptions(
            base_url="http://localhost:3000",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )
    assert client.health.get_info()["name"] == "apie"
    assert client.health.check()["status"] == "ok"
