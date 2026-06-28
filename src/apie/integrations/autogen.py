from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def with_autogen_step(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": input.get("stepKey", "autogen-step"),
            "stepName": input.get("stepName", "AutoGen step"),
            "stepIndex": input.get("stepIndex"),
            "payloadSummary": {
                "framework": "autogen",
                "agent": input.get("agentName"),
                "conversation": input.get("conversationId"),
                **(input.get("metadata") or {}),
            },
        },
        fn,
    )


def with_autogen_tool_step(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_tool(
        {
            "runId": input.get("runId"),
            "tool": {
                "name": input["toolName"],
                "provider": "autogen",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": input.get("actionType", "execute"),
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input.get("resourceType", "internal_api"),
                "provider": input.get("resourceProvider", "autogen"),
                "environment": input.get("environment"),
            },
            "metadata": {"args": input.get("args"), **(input.get("metadata") or {})},
        },
        fn,
    )


async def with_autogen_step_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": input.get("stepKey", "autogen-step"),
            "stepName": input.get("stepName", "AutoGen step"),
            "stepIndex": input.get("stepIndex"),
            "payloadSummary": {
                "framework": "autogen",
                "agent": input.get("agentName"),
                "conversation": input.get("conversationId"),
                **(input.get("metadata") or {}),
            },
        },
        fn,
    )


async def with_autogen_tool_step_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_tool(
        {
            "runId": input.get("runId"),
            "tool": {
                "name": input["toolName"],
                "provider": "autogen",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": input.get("actionType", "execute"),
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input.get("resourceType", "internal_api"),
                "provider": input.get("resourceProvider", "autogen"),
                "environment": input.get("environment"),
            },
            "metadata": {"args": input.get("args"), **(input.get("metadata") or {})},
        },
        fn,
    )
