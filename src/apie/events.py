from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .http import AsyncHttpClient, HttpClient
from .wire import to_wire_event

DEFAULT_REDACT_KEYS = [
    "apiKey",
    "api_key",
    "password",
    "token",
    "secret",
    "authorization",
    "access_token",
    "refresh_token",
    "private_key",
    "client_secret",
]


def send_events(http: HttpClient, events: list[dict[str, Any]]) -> dict[str, list[str]]:
    wire_events = [to_wire_event(event) for event in events]
    response = http.post("/v1/events", {"events": wire_events})
    return {"warnings": response.get("warnings", []) or []}


async def async_send_events(
    http: AsyncHttpClient, events: list[dict[str, Any]]
) -> dict[str, list[str]]:
    wire_events = [to_wire_event(event) for event in events]
    response = await http.post("/v1/events", {"events": wire_events})
    return {"warnings": response.get("warnings", []) or []}


def validate_events(http: HttpClient, events: list[dict[str, Any]]) -> dict[str, Any]:
    wire_events = [to_wire_event(event) for event in events]
    return http.post("/v1/events/validate", {"events": wire_events})


async def async_validate_events(
    http: AsyncHttpClient, events: list[dict[str, Any]]
) -> dict[str, Any]:
    wire_events = [to_wire_event(event) for event in events]
    return await http.post("/v1/events/validate", {"events": wire_events})


def _base_event(
    event_type: str,
    agent_key: str,
    ctx: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ctx = ctx or {}
    return {
        "type": event_type,
        "agentKey": agent_key,
        "agentId": ctx.get("agentId"),
        "agentVersionId": ctx.get("agentVersionId"),
        "runId": ctx.get("runId"),
        "sessionId": ctx.get("sessionId"),
        "eventId": str(uuid4()),
        "sequenceNumber": ctx.get("sequenceNumber"),
        "sessionSequenceNumber": ctx.get("sessionSequenceNumber"),
        "parentEventId": ctx.get("parentEventId"),
        "causedByEventId": ctx.get("causedByEventId"),
        "triggerKind": ctx.get("triggerKind"),
        "eventCategory": ctx.get("eventCategory"),
        "stepKey": ctx.get("stepKey"),
        "stepName": ctx.get("stepName"),
        "stepIndex": ctx.get("stepIndex"),
        "payloadSummary": ctx.get("payloadSummary"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": ctx.get("environment"),
    }


def _wire_resource(resource: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not resource:
        return None
    return {
        "type": resource.get("type"),
        "external_id": resource.get("external_id") or resource.get("externalId"),
        "provider": resource.get("provider"),
        "environment": resource.get("environment"),
    }


def _wire_action(
    action: Optional[dict[str, Any]], risk_level: Optional[str] = None
) -> Optional[dict[str, Any]]:
    if not action:
        return None
    return {
        "type": action.get("type"),
        "name": action.get("name"),
        "risk_level": action.get("risk_level") or action.get("riskLevel") or risk_level,
    }


def _wire_tool(tool: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not tool:
        return None
    return {
        "name": tool.get("name"),
        "provider": tool.get("provider"),
        "risk_level": tool.get("risk_level") or tool.get("riskLevel"),
    }


def build_tool_call_event(agent_key: str, input: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_event("agent.tool.called", agent_key, input),
        "tool": _wire_tool(input.get("tool")),
        "action": _wire_action(input.get("action")),
        "resource": _wire_resource(input.get("resource")),
        "metadata": input.get("metadata"),
    }


def build_action_requested_event(agent_key: str, input: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_event(
            "agent.action.requested",
            agent_key,
            {**input, "environment": (input.get("resource") or {}).get("environment")},
        ),
        "action": _wire_action(input.get("action"), input.get("riskLevel")),
        "resource": _wire_resource(input.get("resource")),
        "tool": _wire_tool(input.get("tool")),
        "metadata": input.get("metadata"),
    }


def build_action_completed_event(agent_key: str, input: dict[str, Any]) -> dict[str, Any]:
    metadata = {**(input.get("metadata") or {})}
    metadata["result"] = input.get("result") or {"status": "completed"}
    return {
        **_base_event(
            "agent.action.completed",
            agent_key,
            {**input, "environment": (input.get("resource") or {}).get("environment")},
        ),
        "action": _wire_action(input.get("action")),
        "resource": _wire_resource(input.get("resource")),
        "tool": _wire_tool(input.get("tool")),
        "metadata": metadata,
    }


def build_action_failed_event(agent_key: str, input: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_event(
            "agent.action.failed",
            agent_key,
            {**input, "environment": (input.get("resource") or {}).get("environment")},
        ),
        "action": _wire_action(input.get("action")),
        "resource": _wire_resource(input.get("resource")),
        "tool": _wire_tool(input.get("tool")),
        "error": input.get("error"),
        "metadata": input.get("metadata"),
    }


def build_resource_touched_event(agent_key: str, input: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_event(
            "agent.resource.touched",
            agent_key,
            {**input, "environment": (input.get("resource") or {}).get("environment")},
        ),
        "resource": _wire_resource(input.get("resource")),
        "action": _wire_action(input.get("action")),
        "metadata": input.get("metadata"),
    }


def build_guardrail_evaluated_event(agent_key: str, input: dict[str, Any]) -> dict[str, Any]:
    decision = {
        "policyDecision": input.get("policyDecision"),
        "effectiveDecision": input.get("effectiveDecision"),
        "enforcementAction": input.get("enforcementAction"),
        "mode": input.get("mode"),
        "reason": input.get("reason"),
    }
    return {
        **_base_event("agent.guardrail.evaluated", agent_key, input),
        "action": _wire_action(input.get("action")),
        "resource": _wire_resource(input.get("resource")),
        "decision": decision,
        "metadata": decision,
    }


def build_approval_requested_event(agent_key: str, input: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_event("agent.approval.requested", agent_key, input),
        "action": _wire_action(input.get("action")),
        "resource": _wire_resource(input.get("resource")),
        "approval": {"approval_id": input.get("approvalId"), "status": "pending"},
        "metadata": {
            "approval_id": input.get("approvalId"),
            "reason": input.get("reason"),
        },
    }


def build_approval_resolved_event(agent_key: str, input: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_event("agent.approval.resolved", agent_key, input),
        "approval": {
            "approval_id": input.get("approvalId"),
            "status": input.get("status"),
            "resolved_by": input.get("resolvedBy"),
        },
        "metadata": {
            "approval_id": input.get("approvalId"),
            "status": input.get("status"),
        },
    }


def build_workflow_event(event_type: str, agent_key: str, ctx: dict[str, Any]) -> dict[str, Any]:
    if "handoff" in event_type:
        category = "handoff"
    elif "llm" in event_type:
        category = "llm"
    elif "mcp" in event_type:
        category = "mcp"
    else:
        category = "workflow"
    return {
        **_base_event(event_type, agent_key, {**ctx, "eventCategory": category}),
        "metadata": ctx.get("metadata"),
        "error": ctx.get("error"),
    }


def build_error_event(
    agent_key: str,
    error: Any,
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    message = str(error)
    stack = getattr(error, "__traceback__", None)
    return {
        **_base_event("agent.error", agent_key, context or {}),
        "error": {"message": message, "stack": str(stack) if stack else None},
        "metadata": (context or {}).get("metadata"),
    }


def redact_event(
    event: dict[str, Any],
    *,
    redact=None,
    redact_keys: Optional[list[str]] = None,
    redact_allow_paths: Optional[list[str]] = None,
    redact_deny_patterns: Optional[list[str]] = None,
    max_payload_bytes: Optional[int] = None,
) -> dict[str, Any]:
    result = copy.deepcopy(event)
    if callable(redact):
        result = redact(result)

    keys = {k.lower() for k in [*DEFAULT_REDACT_KEYS, *(redact_keys or [])]}
    allow_paths = {(path or "").lower() for path in (redact_allow_paths or [])}
    deny_patterns: list[re.Pattern[str]] = []
    for pattern in redact_deny_patterns or []:
        try:
            deny_patterns.append(re.compile(pattern, re.IGNORECASE))
        except re.error:
            continue

    default_value_patterns = [
        re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
        re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{12,}\b", re.IGNORECASE),
        re.compile(r"\b[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{8,}\b"),
    ]

    def path_key(segments: list[str]) -> str:
        return ".".join(segments).lower()

    def sensitive_key(key: str) -> bool:
        normalized = key.lower()
        return any(normalized == candidate or candidate in normalized for candidate in keys)

    def sensitive_value(value: str) -> bool:
        return any(p.search(value) for p in default_value_patterns + deny_patterns)

    def scrub(value: Any, path: list[str]) -> Any:
        if path_key(path) in allow_paths:
            return value
        if isinstance(value, str):
            return "[REDACTED]" if sensitive_value(value) else value
        if isinstance(value, list):
            return [scrub(item, [*path, str(index)]) for index, item in enumerate(value)]
        if not isinstance(value, dict):
            return value

        output: dict[str, Any] = {}
        for key, nested in value.items():
            nested_path = [*path, key]
            if path_key(nested_path) not in allow_paths and sensitive_key(key):
                output[key] = "[REDACTED]"
            else:
                output[key] = scrub(nested, nested_path)
        return output

    for section in ["metadata", "payloadSummary", "tool", "action", "resource", "error"]:
        if section in result and result[section] is not None:
            result[section] = scrub(result[section], [section])

    if max_payload_bytes:
        encoded = json.dumps(result).encode("utf-8")
        if len(encoded) > max_payload_bytes:
            result["metadata"] = {
                "apie_payload_truncated": True,
                "apie_payload_bytes": len(encoded),
                "apie_payload_max_bytes": max_payload_bytes,
            }
            result["payloadSummary"] = {"notice": "[TRUNCATED_FOR_SIZE]"}
            result["tool"] = None
            result["action"] = None
            result["resource"] = None
            result["error"] = None
            result["decision"] = None
            result["approval"] = None
    return result
