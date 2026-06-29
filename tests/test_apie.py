from __future__ import annotations

import pytest

import apie.apie as apie_module
from apie.apie import Apie, AsyncApie
from apie.types import RegisterResponse


def _disabled_config() -> dict:
    return {
        "api_key": "apie_sk_test_x",
        "enabled": False,
        "agent": {"key": "test-agent", "name": "Test Agent"},
    }


def test_apie_send_test_event_single_when_disabled() -> None:
    apie = Apie(_disabled_config())
    result = apie.send_test_event({"mode": "single"})
    assert result.mode == "single"
    assert result.session_id.startswith("disabled_session_")
    assert len(result.run_ids) == 1


def test_apie_send_test_event_proof_when_disabled() -> None:
    apie = Apie(_disabled_config())
    result = apie.send_test_event({"mode": "proof"})
    assert result.mode == "proof"
    assert result.session_id.startswith("disabled_session_")
    assert len(result.run_ids) == 1


def test_apie_doctor_fields() -> None:
    apie = Apie(_disabled_config())
    diagnosis = apie.doctor()
    assert diagnosis["enabled"] is False
    assert diagnosis["apiKeyConfigured"] is True
    assert diagnosis["mode"] == "monitor"
    assert "trustWarnings" in diagnosis


@pytest.mark.asyncio
async def test_async_apie_send_test_event_single_when_disabled() -> None:
    apie = AsyncApie(_disabled_config())
    result = await apie.send_test_event({"mode": "single"})
    assert result.mode == "single"
    assert result.session_id.startswith("disabled_session_")
    await apie.shutdown()


def _enabled_config() -> dict:
    return {
        "api_key": "apie_sk_test_x",
        "agent": {"key": "test-agent", "name": "Test Agent"},
        "base_url": "http://localhost:3000",
    }


def _registration() -> RegisterResponse:
    return RegisterResponse(
        agent_id="agt_test",
        agent_version_id="ver_test",
        workspace_id="ws_test",
        config_hash="hash",
        status="registered",
        created=True,
        version_created=True,
        ingest_url="http://localhost:3000/v1/events",
        recommended_next_step="track",
        dashboard_url="http://localhost:5173/agents/agt_test",
    )


def test_apie_eagerly_registers_enabled_clients(monkeypatch) -> None:
    calls = {"identify": 0}
    monkeypatch.setattr(apie_module.EventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "stop", lambda self: None)

    def _identify(*args, **kwargs):
        calls["identify"] += 1
        return _registration()

    monkeypatch.setattr(apie_module, "identify_agent", _identify)

    apie = Apie(_enabled_config())
    assert calls["identify"] == 1
    assert apie.agent_id == "agt_test"
    apie.shutdown()


def test_apie_ready_raises_startup_registration_error(monkeypatch) -> None:
    monkeypatch.setattr(apie_module.EventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "stop", lambda self: None)

    def _boom(*args, **kwargs):
        raise RuntimeError("registration failed")

    monkeypatch.setattr(apie_module, "identify_agent", _boom)
    apie = Apie({**_enabled_config(), "on_error": "silent"})

    with pytest.raises(RuntimeError, match="registration failed"):
        apie.ready()
    apie.shutdown()


@pytest.mark.asyncio
async def test_async_apie_ready_uses_background_registration(monkeypatch) -> None:
    calls = {"identify": 0}

    async def _identify(*args, **kwargs):
        calls["identify"] += 1
        return _registration()

    async def _async_noop(*args, **kwargs):
        return None

    monkeypatch.setattr(apie_module.AsyncEventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.AsyncEventQueue, "stop", _async_noop)
    monkeypatch.setattr(apie_module, "async_identify_agent", _identify)

    apie = AsyncApie(_enabled_config())
    registration = await apie.ready()
    await apie.shutdown()

    assert registration.agent_id == "agt_test"
    assert calls["identify"] == 1
