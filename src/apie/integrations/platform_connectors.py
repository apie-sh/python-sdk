from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie
from .workflow import with_canonical_tool_action, with_canonical_tool_action_async

T = TypeVar("T")


def _default_action_for_tool(tool_name: str, fallback: str) -> str:
    lowered = tool_name.lower()
    if "merge" in lowered:
        return "merge"
    if "deploy" in lowered:
        return "deploy"
    if "delete" in lowered:
        return "delete"
    if "write" in lowered or "update" in lowered:
        return "write"
    if "read" in lowered or "list" in lowered:
        return "read"
    return fallback


def with_github_action(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return with_canonical_tool_action(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": "github",
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "execute"),
            "resourceType": input.get("resourceType", "code_repository"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


def with_gitlab_action(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return with_canonical_tool_action(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": "gitlab",
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "execute"),
            "resourceType": input.get("resourceType", "code_repository"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


def with_issue_tracker_action(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return with_canonical_tool_action(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": input.get("provider", "linear"),
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "update"),
            "resourceType": input.get("resourceType", "work_item"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


def with_incident_response_action(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return with_canonical_tool_action(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": input.get("provider", "pagerduty"),
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "execute"),
            "resourceType": input.get("resourceType", "incident_signal"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel", "high"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


def with_observability_correlation(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    return with_canonical_tool_action(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": input.get("provider", "sentry"),
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "read"),
            "resourceType": input.get("resourceType", "observability_event"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel", "medium"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


async def with_github_action_async(
    apie: AsyncApie, input: dict[str, Any], fn: Callable[[], Awaitable[T]]
) -> T:
    return await with_canonical_tool_action_async(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": "github",
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "execute"),
            "resourceType": input.get("resourceType", "code_repository"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


async def with_gitlab_action_async(
    apie: AsyncApie, input: dict[str, Any], fn: Callable[[], Awaitable[T]]
) -> T:
    return await with_canonical_tool_action_async(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": "gitlab",
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "execute"),
            "resourceType": input.get("resourceType", "code_repository"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


async def with_issue_tracker_action_async(
    apie: AsyncApie, input: dict[str, Any], fn: Callable[[], Awaitable[T]]
) -> T:
    return await with_canonical_tool_action_async(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": input.get("provider", "linear"),
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "update"),
            "resourceType": input.get("resourceType", "work_item"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


async def with_incident_response_action_async(
    apie: AsyncApie, input: dict[str, Any], fn: Callable[[], Awaitable[T]]
) -> T:
    return await with_canonical_tool_action_async(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": input.get("provider", "pagerduty"),
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "execute"),
            "resourceType": input.get("resourceType", "incident_signal"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel", "high"),
            "metadata": input.get("metadata"),
        },
        fn,
    )


async def with_observability_correlation_async(
    apie: AsyncApie, input: dict[str, Any], fn: Callable[[], Awaitable[T]]
) -> T:
    return await with_canonical_tool_action_async(
        apie,
        {
            "runId": input.get("runId"),
            "toolName": input["toolName"],
            "provider": input.get("provider", "sentry"),
            "actionType": input.get("actionType")
            or _default_action_for_tool(input["toolName"], "read"),
            "resourceType": input.get("resourceType", "observability_event"),
            "environment": input.get("environment"),
            "riskLevel": input.get("riskLevel", "medium"),
            "metadata": input.get("metadata"),
        },
        fn,
    )
