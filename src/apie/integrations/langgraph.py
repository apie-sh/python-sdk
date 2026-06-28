from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def with_langgraph_node(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": input["nodeKey"],
            "stepName": input["nodeName"],
            "stepIndex": input.get("nodeIndex"),
            "payloadSummary": input.get("payloadSummary"),
        },
        fn,
    )


def with_langchain_tool_step(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_tool(
        {
            "runId": input.get("runId"),
            "tool": {
                "name": input["toolName"],
                "provider": "langchain",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": "execute",
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": "langchain_tool",
                "provider": "langchain",
                "environment": input.get("environment"),
            },
            "metadata": {"args": input.get("args")} if input.get("args") is not None else None,
        },
        fn,
    )


async def with_langgraph_node_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": input["nodeKey"],
            "stepName": input["nodeName"],
            "stepIndex": input.get("nodeIndex"),
            "payloadSummary": input.get("payloadSummary"),
        },
        fn,
    )


async def with_langchain_tool_step_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_tool(
        {
            "runId": input.get("runId"),
            "tool": {
                "name": input["toolName"],
                "provider": "langchain",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": "execute",
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": "langchain_tool",
                "provider": "langchain",
                "environment": input.get("environment"),
            },
            "metadata": {"args": input.get("args")} if input.get("args") is not None else None,
        },
        fn,
    )
