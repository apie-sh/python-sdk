from __future__ import annotations

import asyncio
import time
from typing import Literal, Optional

from .events import redact_event
from .http import AsyncHttpClient, HttpClient
from .types import GuardDecision, JsonDict, QueuedEvent

ApprovalWaitStatus = Literal["approved", "rejected", "expired", "cancelled", "timeout"]


def _redact_guard_payload(
    payload: dict[str, object],
    *,
    redact=None,
    redact_keys: Optional[list[str]] = None,
) -> dict[str, object]:
    if redact is None and not redact_keys:
        return payload
    event: QueuedEvent = {
        "type": "guard.evaluate",
        "agentKey": str(payload.get("agent_key", "")),
        "action": payload.get("action"),
        "resource": payload.get("resource"),
        "tool": payload.get("tool"),
        "metadata": payload.get("metadata"),
    }
    redacted = redact_event(event, redact=redact, redact_keys=redact_keys or [])
    payload["action"] = redacted.get("action", payload.get("action"))
    payload["resource"] = redacted.get("resource", payload.get("resource"))
    payload["tool"] = redacted.get("tool", payload.get("tool"))
    payload["metadata"] = redacted.get("metadata", payload.get("metadata"))
    return payload


def evaluate_guard(
    http: HttpClient,
    *,
    agent_key: str,
    run_id: Optional[str],
    mode: Literal["monitor", "enforce"],
    action: dict[str, str],
    resource: dict[str, object],
    tool: Optional[dict[str, object]] = None,
    risk_level: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
    redact=None,
    redact_keys: Optional[list[str]] = None,
) -> GuardDecision:
    body = _redact_guard_payload(
        {
            "agent_key": agent_key,
            "run_id": run_id,
            "mode": mode,
            "risk_level": risk_level,
            "action": action,
            "resource": {
                "type": resource.get("type"),
                "provider": resource.get("provider"),
                "environment": resource.get("environment"),
                "external_id": resource.get("external_id"),
            },
            "tool": tool,
            "metadata": metadata,
        },
        redact=redact,
        redact_keys=redact_keys,
    )
    response = http.post("/v1/guardrails/evaluate", body)
    approval_request = response.get("approval_request") if isinstance(response, dict) else None
    approval_id = (
        approval_request.get("id")
        if isinstance(approval_request, dict)
        else response.get("approval_id")
        if isinstance(response, dict)
        else None
    )
    return GuardDecision(
        type=response.get("decision", "allow"),
        reason=response.get("reason"),
        decision_id=response.get("decision_id"),
        receipt_id=response.get("receipt_id"),
        approval_id=approval_id,
        matched_guardrails=response.get("matched_guardrails", []) or [],
        monitor_decision=response.get("decision", "allow"),
    )


def get_approval_status(http: HttpClient, approval_id: str) -> dict[str, str]:
    body = http.get(f"/v1/approvals/{approval_id}")
    approval = body.get("approval", {})
    return {"status": str(approval.get("status", "pending"))}


def wait_for_approval(
    http: HttpClient,
    approval_id: str,
    *,
    timeout_ms: int = 300_000,
    poll_interval_ms: int = 2_000,
) -> ApprovalWaitStatus:
    try:
        response = http.get(f"/v1/approvals/{approval_id}/wait", query={"timeout": timeout_ms})
        return response.get("status", "timeout")
    except Exception:
        pass

    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        status = get_approval_status(http, approval_id).get("status", "pending")
        if status in {"approved", "rejected", "expired", "cancelled"}:
            return status  # type: ignore[return-value]
        time.sleep(poll_interval_ms / 1000)
    return "timeout"


async def async_evaluate_guard(
    http: AsyncHttpClient,
    *,
    agent_key: str,
    run_id: Optional[str],
    mode: Literal["monitor", "enforce"],
    action: dict[str, str],
    resource: dict[str, object],
    tool: Optional[dict[str, object]] = None,
    risk_level: Optional[str] = None,
    metadata: Optional[JsonDict] = None,
    redact=None,
    redact_keys: Optional[list[str]] = None,
) -> GuardDecision:
    body = _redact_guard_payload(
        {
            "agent_key": agent_key,
            "run_id": run_id,
            "mode": mode,
            "risk_level": risk_level,
            "action": action,
            "resource": {
                "type": resource.get("type"),
                "provider": resource.get("provider"),
                "environment": resource.get("environment"),
                "external_id": resource.get("external_id"),
            },
            "tool": tool,
            "metadata": metadata,
        },
        redact=redact,
        redact_keys=redact_keys,
    )
    response = await http.post("/v1/guardrails/evaluate", body)
    approval_request = response.get("approval_request") if isinstance(response, dict) else None
    approval_id = (
        approval_request.get("id")
        if isinstance(approval_request, dict)
        else response.get("approval_id")
        if isinstance(response, dict)
        else None
    )
    return GuardDecision(
        type=response.get("decision", "allow"),
        reason=response.get("reason"),
        decision_id=response.get("decision_id"),
        receipt_id=response.get("receipt_id"),
        approval_id=approval_id,
        matched_guardrails=response.get("matched_guardrails", []) or [],
        monitor_decision=response.get("decision", "allow"),
    )


async def async_get_approval_status(http: AsyncHttpClient, approval_id: str) -> dict[str, str]:
    body = await http.get(f"/v1/approvals/{approval_id}")
    approval = body.get("approval", {})
    return {"status": str(approval.get("status", "pending"))}


async def async_wait_for_approval(
    http: AsyncHttpClient,
    approval_id: str,
    *,
    timeout_ms: int = 300_000,
    poll_interval_ms: int = 2_000,
) -> ApprovalWaitStatus:
    try:
        response = await http.get(
            f"/v1/approvals/{approval_id}/wait",
            query={"timeout": timeout_ms},
        )
        return response.get("status", "timeout")
    except Exception:
        pass

    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        status = (await async_get_approval_status(http, approval_id)).get("status", "pending")
        if status in {"approved", "rejected", "expired", "cancelled"}:
            return status  # type: ignore[return-value]
        await asyncio.sleep(poll_interval_ms / 1000)
    return "timeout"
