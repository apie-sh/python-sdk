from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(slots=True)
class InferenceResult:
    action_type: str
    resource_type: str
    confidence: Literal["low", "medium", "high"]
    reason: str
    risk_level: Optional[str] = None


@dataclass(slots=True)
class _InferenceRule:
    pattern: re.Pattern[str]
    action_type: str
    resource_type: str
    confidence: Literal["low", "medium", "high"]
    reason: str
    risk_level: Optional[str] = None


_INFERENCE_RULES: list[_InferenceRule] = [
    _InferenceRule(
        re.compile(r"deploy", re.I),
        "execute",
        "deployment_event",
        "high",
        "Tool name contains deploy",
        "critical",
    ),
    _InferenceRule(
        re.compile(r"pipeline", re.I),
        "execute",
        "pipeline_run",
        "high",
        "Tool name contains pipeline",
        "high",
    ),
    _InferenceRule(
        re.compile(r"secret", re.I),
        "read",
        "secret",
        "high",
        "Tool name contains secret",
        "critical",
    ),
    _InferenceRule(
        re.compile(r"delete", re.I),
        "delete",
        "unknown",
        "medium",
        "Tool name contains delete",
        "high",
    ),
    _InferenceRule(
        re.compile(r"send|message|email|slack|notify", re.I),
        "communicate",
        "communication_event",
        "medium",
        "Tool name suggests communication",
    ),
    _InferenceRule(
        re.compile(r"ticket|issue", re.I),
        "read",
        "work_item",
        "medium",
        "Tool name suggests work item",
    ),
    _InferenceRule(
        re.compile(r"change_request|pull_request|\bpr\b", re.I),
        "create",
        "change_request",
        "medium",
        "Tool name suggests change request",
    ),
    _InferenceRule(
        re.compile(r"incident", re.I),
        "read",
        "incident_signal",
        "medium",
        "Tool name suggests incident signal",
    ),
    _InferenceRule(
        re.compile(r"execute|run|trigger", re.I),
        "execute",
        "internal_api",
        "medium",
        "Tool name suggests execution",
        "high",
    ),
    _InferenceRule(
        re.compile(r"admin", re.I),
        "execute",
        "internal_api",
        "medium",
        "Tool name contains admin",
        "critical",
    ),
]


def infer_from_tool_name(tool_name: str) -> InferenceResult | None:
    for rule in _INFERENCE_RULES:
        if rule.pattern.search(tool_name):
            return InferenceResult(
                action_type=rule.action_type,
                resource_type=rule.resource_type,
                risk_level=rule.risk_level,
                confidence=rule.confidence,
                reason=rule.reason,
            )
    return None
