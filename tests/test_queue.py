from __future__ import annotations

import httpx
import pytest

import apie.queue as queue_module
from apie.errors import ApieError
from apie.http import ApieClientOptions, AsyncApieClientOptions, AsyncHttpClient, HttpClient
from apie.queue import AsyncEventQueue, EventQueue


def _make_sync_http(requests: list[httpx.Request]) -> HttpClient:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            text='{"warnings":[]}',
        )

    return HttpClient(
        ApieClientOptions(
            base_url="http://localhost:3000",
            api_key="apie_sk_test_x",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )


def test_queue_flush_calls_ingest_endpoint() -> None:
    requests: list[httpx.Request] = []
    http = _make_sync_http(requests)
    queue = EventQueue(http)
    queue.enqueue({"type": "agent.tool.called", "agentKey": "agent", "eventId": "evt_1"})
    queue.flush()
    assert requests
    assert requests[0].url.path == "/v1/events"
    assert requests[0].method == "POST"


def test_queue_persists_and_restores(tmp_path) -> None:
    requests: list[httpx.Request] = []
    http = _make_sync_http(requests)
    queue_file = tmp_path / "queue.json"

    queue = EventQueue(http, durable_storage_path=str(queue_file))
    queue.enqueue({"type": "agent.tool.called", "agentKey": "agent", "eventId": "evt_1"})
    assert queue_file.exists()

    restored = EventQueue(http, durable_storage_path=str(queue_file))
    assert restored.get_diagnostics().queue_size == 1


def test_queue_deduplicates_by_event_id() -> None:
    requests: list[httpx.Request] = []
    http = _make_sync_http(requests)
    queue = EventQueue(http, max_queue_size=5)
    queue.enqueue({"type": "agent.tool.called", "agentKey": "agent", "eventId": "dup"})
    queue.enqueue({"type": "agent.tool.called", "agentKey": "agent", "eventId": "dup"})
    diagnostics = queue.get_diagnostics()
    assert diagnostics.queue_size == 1
    assert diagnostics.deduplicated_count == 1


@pytest.mark.asyncio
async def test_async_queue_flush() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            text='{"warnings":[]}',
        )

    http = AsyncHttpClient(
        AsyncApieClientOptions(
            base_url="http://localhost:3000",
            api_key="apie_sk_test_x",
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
    )
    queue = AsyncEventQueue(http)
    queue.enqueue({"type": "agent.tool.called", "agentKey": "agent", "eventId": "evt_1"})
    await queue.flush()
    assert requests


def test_queue_honors_retry_after_and_retries(monkeypatch) -> None:
    requests: list[httpx.Request] = []
    http = _make_sync_http(requests)
    queue = EventQueue(http, retry_attempts=2, retry_base_delay_ms=10)
    queue.enqueue({"type": "agent.tool.called", "agentKey": "agent", "eventId": "evt_retry"})

    call_count = {"value": 0}
    sleep_calls: list[float] = []

    def fake_send_events(_http, _batch):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise ApieError("rate_limited", status=429, retry_after_ms=100)
        return {"warnings": []}

    monkeypatch.setattr(queue_module, "send_events", fake_send_events)
    monkeypatch.setattr(queue_module.random, "random", lambda: 0.0)
    monkeypatch.setattr(queue_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    queue.flush()

    assert call_count["value"] == 2
    assert sleep_calls == [0.075]


def test_queue_does_not_retry_non_retryable_errors(monkeypatch) -> None:
    requests: list[httpx.Request] = []
    http = _make_sync_http(requests)
    errors: list[Exception] = []
    queue = EventQueue(http, retry_attempts=3, retry_base_delay_ms=10, on_error=errors.append)
    queue.enqueue({"type": "agent.tool.called", "agentKey": "agent", "eventId": "evt_bad_request"})

    call_count = {"value": 0}

    def fake_send_events(_http, _batch):
        call_count["value"] += 1
        raise ApieError("validation_error", status=400)

    monkeypatch.setattr(queue_module, "send_events", fake_send_events)
    queue.flush()

    assert call_count["value"] == 1
    assert len(errors) == 1
