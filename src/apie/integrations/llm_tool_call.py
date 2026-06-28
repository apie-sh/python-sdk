from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def _to_tool_input(input: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": input.get("runId"),
        "tool": {
            "name": input["toolName"],
            "provider": input["provider"],
            "riskLevel": input.get("riskLevel", "medium"),
        },
        "action": {
            "type": "execute",
            "name": input["toolName"],
            "riskLevel": input.get("riskLevel"),
        },
        "resource": {
            "type": input.get("resourceType", "llm_tool"),
            "provider": input["provider"],
            "external_id": input.get("resourceId"),
            "environment": input.get("environment"),
        },
        "metadata": {"arguments": input.get("arguments")}
        if input.get("arguments") is not None
        else None,
    }


def with_openai_tool_call(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_tool(_to_tool_input({**input, "provider": "openai"}), fn)


def with_anthropic_tool_call(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_tool(_to_tool_input({**input, "provider": "anthropic"}), fn)


def with_tool_call_guard(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return apie.with_tool(_to_tool_input(input), fn)


async def with_openai_tool_call_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_tool(_to_tool_input({**input, "provider": "openai"}), fn)


async def with_anthropic_tool_call_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_tool(_to_tool_input({**input, "provider": "anthropic"}), fn)


async def with_tool_call_guard_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    return await apie.with_tool(_to_tool_input(input), fn)
