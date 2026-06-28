from __future__ import annotations

from apie.events import (
    build_action_completed_event,
    build_action_requested_event,
    build_tool_call_event,
    build_workflow_event,
    redact_event,
)


def test_build_tool_call_event_sets_type_and_id() -> None:
    event = build_tool_call_event(
        "test-agent",
        {
            "runId": "run_1",
            "sequenceNumber": 1,
            "tool": {"name": "read_incident", "provider": "ops"},
            "action": {"type": "read", "name": "read_incident"},
        },
    )
    assert event["type"] == "agent.tool.called"
    assert event["eventId"]
    assert event["sequenceNumber"] == 1


def test_build_action_lifecycle_events() -> None:
    requested = build_action_requested_event(
        "test-agent",
        {
            "runId": "run_1",
            "action": {"type": "execute", "name": "deploy"},
            "resource": {"type": "pipeline_run", "environment": "production"},
        },
    )
    completed = build_action_completed_event(
        "test-agent",
        {
            "runId": "run_1",
            "action": {"type": "execute", "name": "deploy"},
            "resource": {"type": "pipeline_run"},
        },
    )
    assert requested["type"] == "agent.action.requested"
    assert completed["type"] == "agent.action.completed"


def test_build_workflow_event_keeps_session_sequence_fields() -> None:
    event = build_workflow_event(
        "agent.llm.called",
        "test-agent",
        {
            "runId": "run_1",
            "sessionId": "ses_1",
            "sessionSequenceNumber": 3,
            "stepName": "Summarize",
            "payloadSummary": {"model": "gpt-4", "tokens": 120},
        },
    )
    assert event["type"] == "agent.llm.called"
    assert event["sessionId"] == "ses_1"
    assert event["sessionSequenceNumber"] == 3
    assert event["eventCategory"] == "llm"


def test_redact_event_keys_and_patterns() -> None:
    event = {
        "type": "agent.tool.called",
        "agentKey": "test",
        "metadata": {
            "Authorization": "Bearer super-secret-token",
            "nested": {"Api_Key": "apikey-value", "raw": "pk_live_1234567890"},
            "allowed": {"token": "visible-token"},
        },
    }
    redacted = redact_event(
        event,
        redact_allow_paths=["metadata.allowed.token"],
        redact_deny_patterns=["pk_live_[A-Za-z0-9]+"],
    )
    assert redacted["metadata"]["Authorization"] == "[REDACTED]"
    assert redacted["metadata"]["nested"]["Api_Key"] == "[REDACTED]"
    assert redacted["metadata"]["nested"]["raw"] == "[REDACTED]"
    assert redacted["metadata"]["allowed"]["token"] == "visible-token"


def test_redact_event_truncates_large_payloads() -> None:
    event = {
        "type": "agent.tool.called",
        "agentKey": "test",
        "metadata": {"message": "x" * 4096},
        "tool": {"name": "big-payload"},
    }
    redacted = redact_event(event, max_payload_bytes=256)
    assert redacted["metadata"]["apie_payload_truncated"] is True
    assert redacted["tool"] is None
