from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def with_workflow_step(
    apie: Apie,
    input: dict[str, Any],
    fn: Callable[[], T],
) -> T:
    return apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": input.get("stepKey"),
            "stepName": input.get("stepName") or input.get("stepKey"),
            "stepIndex": input.get("stepIndex"),
            "payloadSummary": input.get("payloadSummary"),
        },
        fn,
    )


async def with_workflow_step_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": input.get("stepKey"),
            "stepName": input.get("stepName") or input.get("stepKey"),
            "stepIndex": input.get("stepIndex"),
            "payloadSummary": input.get("payloadSummary"),
        },
        fn,
    )


def with_canonical_tool_action(
    apie: Apie,
    input: dict[str, Any],
    fn: Callable[[], T],
) -> T:
    return apie.with_tool(
        {
            "runId": input.get("runId"),
            "tool": {
                "name": input["toolName"],
                "provider": input.get("provider"),
                "riskLevel": input.get("riskLevel"),
            },
            "action": {
                "type": input["actionType"],
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input["resourceType"],
                "provider": input.get("provider"),
                "environment": input.get("environment"),
            },
            "metadata": input.get("metadata"),
        },
        fn,
    )


async def with_canonical_tool_action_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_tool(
        {
            "runId": input.get("runId"),
            "tool": {
                "name": input["toolName"],
                "provider": input.get("provider"),
                "riskLevel": input.get("riskLevel"),
            },
            "action": {
                "type": input["actionType"],
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input["resourceType"],
                "provider": input.get("provider"),
                "environment": input.get("environment"),
            },
            "metadata": input.get("metadata"),
        },
        fn,
    )
