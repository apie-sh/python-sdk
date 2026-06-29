from __future__ import annotations

import pytest

import apie.apie as apie_module
from apie.apie import Apie, AsyncApie
from apie.types import AgentRun, ApieSession, GuardDecision, RegisterResponse


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


def _enabled_config() -> dict:
    return {
        "api_key": "apie_sk_test_xxxxxxxx",
        "agent": {"key": "test-agent", "name": "Test"},
        "base_url": "http://localhost:3000",
        "flush_interval_ms": 60_000,
    }


def test_send_test_event_single_mode(monkeypatch) -> None:
    calls = {"create_session": 0, "create_child_run": 0, "record_handoff": 0, "complete_run": 0}
    child_index = {"value": 0}

    monkeypatch.setattr(apie_module.EventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "flush", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "stop", lambda self: None)
    monkeypatch.setattr(apie_module, "identify_agent", lambda *_: _registration())
    monkeypatch.setattr(
        apie_module, "evaluate_guard", lambda *args, **kwargs: GuardDecision()
    )

    def create_session(*args, **kwargs):
        calls["create_session"] += 1
        return ApieSession(id="ses_test1", status="running", started_at="2026-01-01T00:00:00Z")

    def complete_session(*args, **kwargs):
        return None

    def create_child_run(*args, **kwargs):
        calls["create_child_run"] += 1
        child_index["value"] += 1
        run_id = "run_orch" if child_index["value"] == 1 else "run_worker"
        return AgentRun(
            id=run_id,
            session_id="ses_test1",
            status="running",
            started_at="2026-01-01T00:00:00Z",
        )

    def record_handoff(*args, **kwargs):
        calls["record_handoff"] += 1
        return {"id": "hof_1", "status": "requested"}

    def complete_run(*args, **kwargs):
        calls["complete_run"] += 1
        return None

    monkeypatch.setattr(apie_module, "create_session", create_session)
    monkeypatch.setattr(apie_module, "complete_session", complete_session)
    monkeypatch.setattr(apie_module, "create_child_run", create_child_run)
    monkeypatch.setattr(apie_module, "record_handoff", record_handoff)
    monkeypatch.setattr(apie_module, "complete_run", complete_run)

    apie = Apie(_enabled_config())
    result = apie.send_test_event({"mode": "single"})
    apie.shutdown()

    assert result.session_id == "ses_test1"
    assert result.run_ids == ["run_orch"]
    assert result.mode == "single"
    assert calls["create_session"] == 1
    assert calls["create_child_run"] == 1
    assert calls["record_handoff"] == 0
    assert calls["complete_run"] == 1


def test_send_test_event_pipeline_mode(monkeypatch) -> None:
    calls = {"create_session": 0, "create_child_run": 0, "record_handoff": 0, "complete_run": 0}
    child_index = {"value": 0}

    monkeypatch.setattr(apie_module.EventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "flush", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "stop", lambda self: None)
    monkeypatch.setattr(apie_module, "identify_agent", lambda *_: _registration())
    monkeypatch.setattr(
        apie_module, "evaluate_guard", lambda *args, **kwargs: GuardDecision()
    )

    def create_session(*args, **kwargs):
        calls["create_session"] += 1
        return ApieSession(id="ses_test1", status="running", started_at="2026-01-01T00:00:00Z")

    def complete_session(*args, **kwargs):
        return None

    def create_child_run(*args, **kwargs):
        calls["create_child_run"] += 1
        child_index["value"] += 1
        run_id = "run_orch" if child_index["value"] == 1 else "run_worker"
        return AgentRun(
            id=run_id,
            session_id="ses_test1",
            status="running",
            started_at="2026-01-01T00:00:00Z",
        )

    def record_handoff(*args, **kwargs):
        calls["record_handoff"] += 1
        return {"id": "hof_1", "status": "requested"}

    def complete_run(*args, **kwargs):
        calls["complete_run"] += 1
        return None

    monkeypatch.setattr(apie_module, "create_session", create_session)
    monkeypatch.setattr(apie_module, "complete_session", complete_session)
    monkeypatch.setattr(apie_module, "create_child_run", create_child_run)
    monkeypatch.setattr(apie_module, "record_handoff", record_handoff)
    monkeypatch.setattr(apie_module, "complete_run", complete_run)

    apie = Apie(_enabled_config())
    result = apie.send_test_event({"mode": "pipeline"})
    apie.shutdown()

    assert result.session_id == "ses_test1"
    assert result.run_ids == ["run_orch", "run_worker"]
    assert result.mode == "pipeline"
    assert calls["create_session"] == 1
    assert calls["create_child_run"] == 2
    assert calls["record_handoff"] == 1
    assert calls["complete_run"] == 2


def test_send_test_event_defaults_to_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(apie_module.EventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "flush", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "stop", lambda self: None)
    monkeypatch.setattr(apie_module, "identify_agent", lambda *_: _registration())
    monkeypatch.setattr(
        apie_module, "evaluate_guard", lambda *args, **kwargs: GuardDecision()
    )
    monkeypatch.setattr(
        apie_module,
        "create_session",
        lambda *args, **kwargs: ApieSession(
            id="ses_test1", status="running", started_at="2026-01-01T00:00:00Z"
        ),
    )
    index = {"value": 0}

    def create_child_run(*args, **kwargs):
        index["value"] += 1
        return AgentRun(
            id="run_orch" if index["value"] == 1 else "run_worker",
            session_id="ses_test1",
            status="running",
            started_at="2026-01-01T00:00:00Z",
        )

    monkeypatch.setattr(apie_module, "create_child_run", create_child_run)
    monkeypatch.setattr(apie_module, "record_handoff", lambda *args, **kwargs: {"id": "hof_1"})
    monkeypatch.setattr(apie_module, "complete_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(apie_module, "complete_session", lambda *args, **kwargs: None)

    apie = Apie(_enabled_config())
    result = apie.send_test_event()
    apie.shutdown()

    assert result.mode == "pipeline"
    assert len(result.run_ids) == 2


@pytest.mark.asyncio
async def test_async_send_test_event_pipeline_mode(monkeypatch) -> None:
    calls = {"create_child_run": 0, "record_handoff": 0}
    child_index = {"value": 0}

    async def async_noop(*args, **kwargs):
        return None

    async def async_identify(*args, **kwargs):
        return _registration()

    async def async_create_session(*args, **kwargs):
        return ApieSession(id="ses_test1", status="running", started_at="2026-01-01T00:00:00Z")

    async def async_create_child_run(*args, **kwargs):
        calls["create_child_run"] += 1
        child_index["value"] += 1
        run_id = "run_orch" if child_index["value"] == 1 else "run_worker"
        return AgentRun(
            id=run_id,
            session_id="ses_test1",
            status="running",
            started_at="2026-01-01T00:00:00Z",
        )

    async def async_record_handoff(*args, **kwargs):
        calls["record_handoff"] += 1
        return {"id": "hof_1", "status": "requested"}

    async def async_allow_guard(*args, **kwargs):
        return GuardDecision()

    monkeypatch.setattr(apie_module.AsyncEventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.AsyncEventQueue, "flush", async_noop)
    monkeypatch.setattr(apie_module.AsyncEventQueue, "stop", async_noop)
    monkeypatch.setattr(apie_module, "async_identify_agent", async_identify)
    monkeypatch.setattr(apie_module, "async_create_session", async_create_session)
    monkeypatch.setattr(apie_module, "async_complete_session", async_noop)
    monkeypatch.setattr(apie_module, "async_create_child_run", async_create_child_run)
    monkeypatch.setattr(apie_module, "async_complete_run", async_noop)
    monkeypatch.setattr(apie_module, "async_record_handoff", async_record_handoff)
    monkeypatch.setattr(apie_module, "async_evaluate_guard", async_allow_guard)

    apie = AsyncApie(_enabled_config())
    result = await apie.send_test_event({"mode": "pipeline"})
    await apie.shutdown()

    assert result.session_id == "ses_test1"
    assert result.run_ids == ["run_orch", "run_worker"]
    assert calls["create_child_run"] == 2
    assert calls["record_handoff"] == 1
