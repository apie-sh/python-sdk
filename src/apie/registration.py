from __future__ import annotations

from .http import AsyncHttpClient, HttpClient
from .types import ApieConfig, RegisterResponse
from .wire import build_register_payload, parse_register_response


def register_agent(http: HttpClient, config: ApieConfig) -> RegisterResponse:
    payload = build_register_payload(config)
    body = http.post("/v1/agents/identify", payload)
    return parse_register_response(body)


def identify_agent(http: HttpClient, config: ApieConfig) -> RegisterResponse:
    return register_agent(http, config)


async def async_register_agent(http: AsyncHttpClient, config: ApieConfig) -> RegisterResponse:
    payload = build_register_payload(config)
    body = await http.post("/v1/agents/identify", payload)
    return parse_register_response(body)


async def async_identify_agent(http: AsyncHttpClient, config: ApieConfig) -> RegisterResponse:
    return await async_register_agent(http, config)
