from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .inference import infer_from_tool_name
from .redact import summarize_args


@dataclass(slots=True)
class McpToolCallInput:
    server_name: str
    tool_name: str
    arguments: dict[str, Any] | None = None
    environment: str | None = None
    redact_keys: list[str] | None = None


@dataclass(slots=True)
class McpGuardPayload:
    tool: dict[str, str]
    action: dict[str, str]
    resource: dict[str, str | None]
    metadata: dict[str, Any]
    risk_level: str


def build_mcp_tool_call_payload(input: McpToolCallInput) -> McpGuardPayload:
    qualified_name = f"{input.server_name}.{input.tool_name}"
    inferred = infer_from_tool_name(qualified_name)
    action_type = inferred.action_type if inferred else "execute"
    resource_type = inferred.resource_type if inferred else "internal_api"
    risk_level = inferred.risk_level if inferred and inferred.risk_level else "medium"

    return McpGuardPayload(
        tool={
            "name": qualified_name,
            "provider": "mcp",
            "riskLevel": risk_level,
        },
        action={
            "type": action_type,
            "name": qualified_name,
            "riskLevel": risk_level,
        },
        resource={
            "type": resource_type,
            "provider": input.server_name,
            "environment": input.environment,
        },
        risk_level=risk_level,
        metadata={
            "capture_source": "mcp_proxy",
            "mcp": {
                "server": input.server_name,
                "tool": input.tool_name,
                "arguments": summarize_args(input.arguments, input.redact_keys),
            },
        },
    )


def build_mcp_workflow_payload(
    input: McpToolCallInput,
    payload: McpGuardPayload,
) -> dict[str, Any]:
    return {
        "server": input.server_name,
        "tool": input.tool_name,
        "action_type": payload.action["type"],
        "resource_type": payload.resource["type"],
        "environment": input.environment,
    }
