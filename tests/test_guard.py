from __future__ import annotations

import apie.apie as apie_module
from apie.apie import Apie
from apie.types import GuardDecision, RegisterResponse


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


def _config(mode: str = "monitor") -> dict:
    return {
        "api_key": "apie_sk_test_xxxxxxxx",
        "agent": {"key": "test-agent", "name": "Test"},
        "base_url": "http://localhost:3000",
        "mode": mode,
    }


def test_monitor_mode_converts_block_to_allow(monkeypatch) -> None:
    monkeypatch.setattr(apie_module.EventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "flush", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "stop", lambda self: None)
    monkeypatch.setattr(apie_module, "identify_agent", lambda *_: _registration())
    monkeypatch.setattr(
        apie_module,
        "evaluate_guard",
        lambda *args, **kwargs: GuardDecision(
            policy_decision="block",
            effective_decision="allow",
            mode="monitor",
            enforcement_action="proceed",
            reason="blocked",
        ),
    )

    apie = Apie(_config(mode="monitor"))
    decision = apie.guard(
        {
            "action": {"type": "execute", "name": "deploy"},
            "resource": {"type": "deployment_event"},
        }
    )
    apie.shutdown()

    assert decision.policy_decision == "block"
    assert decision.effective_decision == "allow"
    assert decision.enforcement_action == "proceed"


def test_monitor_mode_preserves_warn(monkeypatch) -> None:
    monkeypatch.setattr(apie_module.EventQueue, "start", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "flush", lambda self: None)
    monkeypatch.setattr(apie_module.EventQueue, "stop", lambda self: None)
    monkeypatch.setattr(apie_module, "identify_agent", lambda *_: _registration())
    monkeypatch.setattr(
        apie_module,
        "evaluate_guard",
        lambda *args, **kwargs: GuardDecision(
            policy_decision="warn",
            effective_decision="warn",
            mode="monitor",
            enforcement_action="warn",
            reason="warning",
        ),
    )

    apie = Apie(_config(mode="monitor"))
    decision = apie.guard(
        {
            "action": {"type": "execute", "name": "deploy"},
            "resource": {"type": "deployment_event"},
        }
    )
    apie.shutdown()

    assert decision.policy_decision == "warn"
    assert decision.effective_decision == "warn"
