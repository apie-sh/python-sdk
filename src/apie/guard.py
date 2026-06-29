from __future__ import annotations

import asyncio
import time
from typing import Literal, Optional

from .events import redact_event
from .http import AsyncHttpClient, HttpClient
from .types import GuardDecision, JsonDict, QueuedEvent

ApprovalWaitStatus = Literal["approved", "rejected", "expired", "cancelled", "timeout"]
DecisionType = Literal["allow", "block", "warn", "require_approval"]


def _coerce_decision(value: object, default: DecisionType = "allow") -> DecisionType:
    return value if value in {"allow", "block", "warn", "require_approval"} else default  # type: ignore[return-value]


def _effective_decision(policy_decision: DecisionType, mode: str) -> DecisionType:
    if mode == "monitor" and policy_decision in {"block", "require_approval"}:
        return "allow"
    return policy_decision


def _enforcement_action(decision: DecisionType) -> Literal[
    "proceed", "warn", "block", "wait_for_approval"
]:
    if decision == "block":
        return "block"
    if decision == "require_approval":
        return "wait_for_approval"
    if decision == "warn":
        return "warn"
    return "proceed"


def _parse_guard_decision(response: dict[str, object], fallback_mode: str) -> GuardDecision:
    policy_decision = _coerce_decision(
        response.get("policy_decision") or response.get("decision")
    )
    mode = response.get("mode") if response.get("mode") in {"monitor", "enforce"} else fallback_mode
    effective_decision = _coerce_decision(
        response.get("effective_decision"),
        _effective_decision(policy_decision, str(mode)),
    )
    enforcement_action = response.get("enforcement_action")
    if enforcement_action not in {"proceed", "warn", "block", "wait_for_approval"}:
        enforcement_action = _enforcement_action(effective_decision)
    approval_request = response.get("approval_request")
    approval_id = (
        approval_request.get("id")
        if isinstance(approval_request, dict)
        else response.get("approval_id")
    )
    return GuardDecision(
        policy_decision=policy_decision,
        effective_decision=effective_decision,
        mode=mode,  # type: ignore[arg-type]
        enforcement_action=enforcement_action,  # type: ignore[arg-type]
        reason=response.get("reason") if isinstance(response.get("reason"), str) else None,
        decision_id=(
            response.get("decision_id") if isinstance(response.get("decision_id"), str) else None
        ),
        receipt_id=response.get("receipt_id") if isinstance(response.get("receipt_id"), str) else None,
        approval_id=approval_id if isinstance(approval_id, str) else None,
        matched_guardrails=response.get("matched_guardrails", [])  # type: ignore[arg-type]
        or [],
    )


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
    return _parse_guard_decision(response, mode)


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
    return _parse_guard_decision(response, mode)


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
