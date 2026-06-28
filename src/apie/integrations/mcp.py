from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def with_mcp_tool_call(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    tool_name = f"{input['server']}.{input['tool']}"
    payload_summary = input.get("payloadSummary") or {
        "server": input["server"],
        "tool": input["tool"],
        "action_type": input.get("actionType", "execute"),
        "resource_type": input.get("resourceType", "internal_api"),
        "environment": input.get("environment"),
    }
    return apie.with_tool(
        {
            "runId": input["runId"],
            "tool": {
                "name": tool_name,
                "provider": "mcp",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": input.get("actionType", "execute"),
                "name": input.get("actionName", tool_name),
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input.get("resourceType", "internal_api"),
                "provider": input.get("resourceProvider", input["server"]),
                "external_id": input.get("resourceId", input.get("resourceTarget")),
                "environment": input.get("environment"),
            },
            "metadata": {
                **(input.get("metadata") or {}),
                "mcp": {
                    "server": input["server"],
                    "tool": input["tool"],
                    "input_schema": input.get("inputSchema"),
                    "resource_target": input.get("resourceTarget"),
                },
            },
        },
        lambda: apie.with_mcp_call(
            {
                "runId": input["runId"],
                "sessionId": input.get("sessionId"),
                "stepName": tool_name,
                "payloadSummary": payload_summary,
            },
            fn,
        ),
    )


async def with_mcp_tool_call_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    tool_name = f"{input['server']}.{input['tool']}"
    payload_summary = input.get("payloadSummary") or {
        "server": input["server"],
        "tool": input["tool"],
        "action_type": input.get("actionType", "execute"),
        "resource_type": input.get("resourceType", "internal_api"),
        "environment": input.get("environment"),
    }
    return await apie.with_tool(
        {
            "runId": input["runId"],
            "tool": {
                "name": tool_name,
                "provider": "mcp",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": input.get("actionType", "execute"),
                "name": input.get("actionName", tool_name),
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input.get("resourceType", "internal_api"),
                "provider": input.get("resourceProvider", input["server"]),
                "external_id": input.get("resourceId", input.get("resourceTarget")),
                "environment": input.get("environment"),
            },
            "metadata": {
                **(input.get("metadata") or {}),
                "mcp": {
                    "server": input["server"],
                    "tool": input["tool"],
                    "input_schema": input.get("inputSchema"),
                    "resource_target": input.get("resourceTarget"),
                },
            },
        },
        lambda: apie.with_mcp_call(
            {
                "runId": input["runId"],
                "sessionId": input.get("sessionId"),
                "stepName": tool_name,
                "payloadSummary": payload_summary,
            },
            fn,
        ),
    )
