from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def with_openai_agent_step(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": f"openai-agent:{input['agentName']}:{input['stepName']}",
            "stepName": input["stepName"],
            "stepIndex": input.get("stepIndex"),
            "payloadSummary": {
                "provider": "openai-agents",
                "agent": input["agentName"],
                "model": input.get("model"),
                **(input.get("metadata") or {}),
            },
        },
        fn,
    )


def with_openai_agent_tool_call(
    apie: Apie,
    input: dict[str, Any],
    fn: Callable[[], T],
) -> T:
    return apie.with_tool(
        {
            "runId": input["runId"],
            "tool": {
                "name": input["toolName"],
                "provider": "openai",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": input.get("actionType", "execute"),
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input.get("resourceType", "llm_tool"),
                "provider": "openai",
                "external_id": input.get("resourceId"),
                "environment": input.get("environment"),
            },
            "metadata": {
                "agent": input.get("agentName"),
                "model": input.get("model"),
                "arguments": input.get("arguments"),
                **(input.get("metadata") or {}),
            },
        },
        fn,
    )


async def with_openai_agent_step_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": f"openai-agent:{input['agentName']}:{input['stepName']}",
            "stepName": input["stepName"],
            "stepIndex": input.get("stepIndex"),
            "payloadSummary": {
                "provider": "openai-agents",
                "agent": input["agentName"],
                "model": input.get("model"),
                **(input.get("metadata") or {}),
            },
        },
        fn,
    )


async def with_openai_agent_tool_call_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_tool(
        {
            "runId": input["runId"],
            "tool": {
                "name": input["toolName"],
                "provider": "openai",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": input.get("actionType", "execute"),
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input.get("resourceType", "llm_tool"),
                "provider": "openai",
                "external_id": input.get("resourceId"),
                "environment": input.get("environment"),
            },
            "metadata": {
                "agent": input.get("agentName"),
                "model": input.get("model"),
                "arguments": input.get("arguments"),
                **(input.get("metadata") or {}),
            },
        },
        fn,
    )
