from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def with_llamaindex_step(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": input.get("stepKey", "llamaindex-step"),
            "stepName": input.get("stepName", "LlamaIndex step"),
            "stepIndex": input.get("stepIndex"),
            "payloadSummary": {
                "framework": "llamaindex",
                "index": input.get("indexName"),
                "query_type": input.get("queryType"),
                **(input.get("metadata") or {}),
            },
        },
        fn,
    )


def with_llamaindex_tool_step(
    apie: Apie,
    input: dict[str, Any],
    fn: Callable[[], T],
) -> T:
    return apie.with_tool(
        {
            "runId": input.get("runId"),
            "tool": {
                "name": input["toolName"],
                "provider": "llamaindex",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": input.get("actionType", "execute"),
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input.get("resourceType", "knowledge_base"),
                "provider": input.get("resourceProvider", "llamaindex"),
                "environment": input.get("environment"),
            },
            "metadata": {"args": input.get("args"), **(input.get("metadata") or {})},
        },
        fn,
    )


async def with_llamaindex_step_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_workflow_step(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepKey": input.get("stepKey", "llamaindex-step"),
            "stepName": input.get("stepName", "LlamaIndex step"),
            "stepIndex": input.get("stepIndex"),
            "payloadSummary": {
                "framework": "llamaindex",
                "index": input.get("indexName"),
                "query_type": input.get("queryType"),
                **(input.get("metadata") or {}),
            },
        },
        fn,
    )


async def with_llamaindex_tool_step_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_tool(
        {
            "runId": input.get("runId"),
            "tool": {
                "name": input["toolName"],
                "provider": "llamaindex",
                "riskLevel": input.get("riskLevel", "medium"),
            },
            "action": {
                "type": input.get("actionType", "execute"),
                "name": input["toolName"],
                "riskLevel": input.get("riskLevel"),
            },
            "resource": {
                "type": input.get("resourceType", "knowledge_base"),
                "provider": input.get("resourceProvider", "llamaindex"),
                "environment": input.get("environment"),
            },
            "metadata": {"args": input.get("args"), **(input.get("metadata") or {})},
        },
        fn,
    )
