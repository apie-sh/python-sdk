from __future__ import annotations

from typing import Literal, Optional

from .http import AsyncHttpClient, HttpClient
from .types import AgentRun, ApieSession, JsonDict

SessionKind = Literal["single_agent", "multi_agent", "pipeline", "activation_proof"]
SessionStatus = Literal["completed", "failed", "cancelled"]


def create_session(
    http: HttpClient,
    *,
    kind: Optional[SessionKind] = None,
    orchestrator_agent_key: Optional[str] = None,
    orchestrator_agent_id: Optional[str] = None,
    environment: Optional[str] = None,
    input_summary: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
) -> ApieSession:
    body = http.post(
        "/v1/sessions",
        {
            "kind": kind,
            "orchestrator_agent_key": orchestrator_agent_key,
            "orchestrator_agent_id": orchestrator_agent_id,
            "environment": environment,
            "input_summary": input_summary,
            "metadata": metadata,
        },
    )
    return ApieSession(
        id=str(body.get("id", "")),
        status=str(body.get("status", "")),
        started_at=body.get("started_at"),
    )


def complete_session(
    http: HttpClient,
    session_id: str,
    *,
    status: SessionStatus,
    output_summary: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
) -> None:
    http.post(
        f"/v1/sessions/{session_id}/complete",
        {
            "status": status,
            "output_summary": output_summary,
            "metadata": metadata,
        },
    )


def create_child_run(
    http: HttpClient,
    session_id: str,
    *,
    agent_key: Optional[str] = None,
    agent_id: Optional[str] = None,
    agent_version_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    trigger_event_id: Optional[str] = None,
    step_key: Optional[str] = None,
    step_name: Optional[str] = None,
    step_index: Optional[int] = None,
    role: Optional[str] = None,
    environment: Optional[str] = None,
    input_summary: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
) -> AgentRun:
    body = http.post(
        f"/v1/sessions/{session_id}/runs",
        {
            "agent_key": agent_key,
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "parent_run_id": parent_run_id,
            "trigger_event_id": trigger_event_id,
            "step_key": step_key,
            "step_name": step_name,
            "step_index": step_index,
            "role": role,
            "environment": environment,
            "input_summary": input_summary,
            "metadata": metadata,
        },
    )
    return AgentRun(
        id=str(body.get("id", "")),
        session_id=str(body.get("session_id", session_id)),
        status=str(body.get("status", "")),
        started_at=body.get("started_at"),
    )


def record_handoff(
    http: HttpClient,
    session_id: str,
    *,
    source_run_id: Optional[str] = None,
    source_agent_id: Optional[str] = None,
    target_run_id: Optional[str] = None,
    target_agent_id: Optional[str] = None,
    trigger_event_id: Optional[str] = None,
    reason: Optional[str] = None,
    input_summary: Optional[str] = None,
    payload_summary: Optional[JsonDict] = None,
    status: Optional[str] = None,
) -> dict[str, str]:
    return http.post(
        f"/v1/sessions/{session_id}/handoffs",
        {
            "source_run_id": source_run_id,
            "source_agent_id": source_agent_id,
            "target_run_id": target_run_id,
            "target_agent_id": target_agent_id,
            "trigger_event_id": trigger_event_id,
            "reason": reason,
            "input_summary": input_summary,
            "payload_summary": payload_summary,
            "status": status,
        },
    )


async def async_create_session(
    http: AsyncHttpClient,
    *,
    kind: Optional[SessionKind] = None,
    orchestrator_agent_key: Optional[str] = None,
    orchestrator_agent_id: Optional[str] = None,
    environment: Optional[str] = None,
    input_summary: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
) -> ApieSession:
    body = await http.post(
        "/v1/sessions",
        {
            "kind": kind,
            "orchestrator_agent_key": orchestrator_agent_key,
            "orchestrator_agent_id": orchestrator_agent_id,
            "environment": environment,
            "input_summary": input_summary,
            "metadata": metadata,
        },
    )
    return ApieSession(
        id=str(body.get("id", "")),
        status=str(body.get("status", "")),
        started_at=body.get("started_at"),
    )


async def async_complete_session(
    http: AsyncHttpClient,
    session_id: str,
    *,
    status: SessionStatus,
    output_summary: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
) -> None:
    await http.post(
        f"/v1/sessions/{session_id}/complete",
        {
            "status": status,
            "output_summary": output_summary,
            "metadata": metadata,
        },
    )


async def async_create_child_run(
    http: AsyncHttpClient,
    session_id: str,
    *,
    agent_key: Optional[str] = None,
    agent_id: Optional[str] = None,
    agent_version_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    trigger_event_id: Optional[str] = None,
    step_key: Optional[str] = None,
    step_name: Optional[str] = None,
    step_index: Optional[int] = None,
    role: Optional[str] = None,
    environment: Optional[str] = None,
    input_summary: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
) -> AgentRun:
    body = await http.post(
        f"/v1/sessions/{session_id}/runs",
        {
            "agent_key": agent_key,
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "parent_run_id": parent_run_id,
            "trigger_event_id": trigger_event_id,
            "step_key": step_key,
            "step_name": step_name,
            "step_index": step_index,
            "role": role,
            "environment": environment,
            "input_summary": input_summary,
            "metadata": metadata,
        },
    )
    return AgentRun(
        id=str(body.get("id", "")),
        session_id=str(body.get("session_id", session_id)),
        status=str(body.get("status", "")),
        started_at=body.get("started_at"),
    )


async def async_record_handoff(
    http: AsyncHttpClient,
    session_id: str,
    *,
    source_run_id: Optional[str] = None,
    source_agent_id: Optional[str] = None,
    target_run_id: Optional[str] = None,
    target_agent_id: Optional[str] = None,
    trigger_event_id: Optional[str] = None,
    reason: Optional[str] = None,
    input_summary: Optional[str] = None,
    payload_summary: Optional[JsonDict] = None,
    status: Optional[str] = None,
) -> dict[str, str]:
    return await http.post(
        f"/v1/sessions/{session_id}/handoffs",
        {
            "source_run_id": source_run_id,
            "source_agent_id": source_agent_id,
            "target_run_id": target_run_id,
            "target_agent_id": target_agent_id,
            "trigger_event_id": trigger_event_id,
            "reason": reason,
            "input_summary": input_summary,
            "payload_summary": payload_summary,
            "status": status,
        },
    )
