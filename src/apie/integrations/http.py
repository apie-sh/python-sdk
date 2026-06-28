from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def create_http_guard(apie: Apie) -> Callable[[dict[str, Any], Callable[[], T]], T]:
    def with_http_guard(input: dict[str, Any], fn: Callable[[], T]) -> T:
        return apie.with_guard(
            {
                "runId": input.get("runId"),
                "action": {
                    "type": input.get("actionType", "http.request"),
                    "name": input["actionName"],
                },
                "resource": {
                    "type": input["resourceType"],
                    "external_id": input.get("resourceId"),
                    "environment": input.get("environment"),
                },
                "tool": {
                    "name": input.get("toolName"),
                    "provider": "http",
                    "riskLevel": input.get("riskLevel"),
                }
                if input.get("toolName")
                else None,
                "riskLevel": input.get("riskLevel"),
                "metadata": input.get("metadata"),
            },
            fn,
        )

    return with_http_guard


def create_http_guard_async(
    apie: AsyncApie,
) -> Callable[[dict[str, Any], Callable[[], Awaitable[T]]], Awaitable[T]]:
    async def with_http_guard(input: dict[str, Any], fn: Callable[[], Awaitable[T]]) -> T:
        return await apie.with_guard(
            {
                "runId": input.get("runId"),
                "action": {
                    "type": input.get("actionType", "http.request"),
                    "name": input["actionName"],
                },
                "resource": {
                    "type": input["resourceType"],
                    "external_id": input.get("resourceId"),
                    "environment": input.get("environment"),
                },
                "tool": {
                    "name": input.get("toolName"),
                    "provider": "http",
                    "riskLevel": input.get("riskLevel"),
                }
                if input.get("toolName")
                else None,
                "riskLevel": input.get("riskLevel"),
                "metadata": input.get("metadata"),
            },
            fn,
        )

    return with_http_guard
