from __future__ import annotations

from typing import Optional

from .http import AsyncHttpClient, HttpClient
from .types import AgentRun, JsonDict


def create_run(
    http: HttpClient,
    *,
    agent_key: str,
    agent_id: Optional[str] = None,
    agent_version_id: Optional[str] = None,
    environment: Optional[str] = None,
    input_summary: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
) -> AgentRun:
    body = http.post(
        "/v1/runs",
        {
            "agent_key": agent_key,
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "environment": environment,
            "input_summary": input_summary,
            "metadata": metadata,
        },
    )
    return AgentRun(
        id=str(body.get("id", "")),
        session_id=body.get("session_id"),
        status=str(body.get("status", "")),
        started_at=body.get("started_at"),
    )


def complete_run(
    http: HttpClient,
    run_id: str,
    *,
    status: str = "completed",
    metadata: Optional[JsonDict] = None,
) -> None:
    http.post(
        f"/v1/runs/{run_id}/complete",
        {
            "status": status,
            "metadata": metadata,
        },
    )


async def async_create_run(
    http: AsyncHttpClient,
    *,
    agent_key: str,
    agent_id: Optional[str] = None,
    agent_version_id: Optional[str] = None,
    environment: Optional[str] = None,
    input_summary: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
) -> AgentRun:
    body = await http.post(
        "/v1/runs",
        {
            "agent_key": agent_key,
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "environment": environment,
            "input_summary": input_summary,
            "metadata": metadata,
        },
    )
    return AgentRun(
        id=str(body.get("id", "")),
        session_id=body.get("session_id"),
        status=str(body.get("status", "")),
        started_at=body.get("started_at"),
    )


async def async_complete_run(
    http: AsyncHttpClient,
    run_id: str,
    *,
    status: str = "completed",
    metadata: Optional[JsonDict] = None,
) -> None:
    await http.post(
        f"/v1/runs/{run_id}/complete",
        {
            "status": status,
            "metadata": metadata,
        },
    )
