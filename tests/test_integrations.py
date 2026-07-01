from __future__ import annotations

import pytest

from apie.integrations import (
    create_http_guard,
    create_http_guard_async,
    with_crewai_task,
    with_openai_agent_step,
    with_openai_agent_tool_call,
    with_github_action,
    with_gitlab_action,
    with_incident_response_action,
    with_issue_tracker_action,
    with_langgraph_node,
    with_mcp_tool_call,
    with_observability_correlation,
    with_openai_tool_call,
    with_openai_tool_call_async,
    with_vercel_ai_generation,
)


def test_with_openai_tool_call_routes_to_with_tool() -> None:
    calls: list[dict] = []

    class FakeApie:
        def with_tool(self, payload, fn):
            calls.append(payload)
            return fn()

    result = with_openai_tool_call(
        FakeApie(),
        {"runId": "run_1", "toolName": "search_docs"},
        lambda: "ok",
    )

    assert result == "ok"
    assert len(calls) == 1
    assert calls[0]["tool"]["provider"] == "openai"


def test_workflow_wrappers_route_to_apie_primitives() -> None:
    calls: list[str] = []

    class FakeApie:
        def with_tool(self, _payload, fn):
            calls.append("tool")
            return fn()

        def with_workflow_step(self, _payload, fn):
            calls.append("workflow")
            return fn()

        def with_mcp_call(self, _payload, fn):
            calls.append("mcp")
            return fn()

        def with_llm_call(self, _payload, fn):
            calls.append("llm")
            return fn()

    apie = FakeApie()
    with_langgraph_node(
        apie,
        {"runId": "run_1", "nodeKey": "plan", "nodeName": "Plan"},
        lambda: "step",
    )
    with_mcp_tool_call(
        apie,
        {"runId": "run_1", "server": "fs", "tool": "read"},
        lambda: "mcp",
    )
    with_vercel_ai_generation(
        apie,
        {"runId": "run_1", "model": "gpt-5.4-mini"},
        lambda: "llm",
    )

    assert calls == ["workflow", "tool", "mcp", "llm"]


def test_openai_agents_and_crewai_helpers_route_to_primitives() -> None:
    calls: list[str] = []

    class FakeApie:
        def with_workflow_step(self, _payload, fn):
            calls.append("workflow")
            return fn()

        def with_tool(self, _payload, fn):
            calls.append("tool")
            return fn()

    apie = FakeApie()
    with_openai_agent_step(
        apie,
        {
            "runId": "run_1",
            "agentName": "triage-agent",
            "stepName": "plan",
        },
        lambda: "step",
    )
    with_openai_agent_tool_call(
        apie,
        {
            "runId": "run_1",
            "agentName": "triage-agent",
            "toolName": "search_docs",
        },
        lambda: "tool",
    )
    with_crewai_task(
        apie,
        {
            "runId": "run_1",
            "taskName": "Assess release risk",
        },
        lambda: "task",
    )

    assert calls == ["workflow", "tool", "workflow"]


def test_create_http_guard_returns_reusable_wrapper() -> None:
    calls: list[dict] = []

    class FakeApie:
        def with_guard(self, payload, fn):
            calls.append(payload)
            return fn()

    with_http_guard = create_http_guard(FakeApie())
    value = with_http_guard(
        {
            "actionName": "POST /deploy",
            "resourceType": "deployment_pipeline",
            "riskLevel": "high",
        },
        lambda: "ok",
    )

    assert value == "ok"
    assert len(calls) == 1
    assert calls[0]["action"]["name"] == "POST /deploy"


def test_platform_connector_wrappers_set_provider() -> None:
    calls: list[dict] = []

    class FakeApie:
        def with_tool(self, payload, fn):
            calls.append(payload)
            return fn()

    apie = FakeApie()
    with_github_action(apie, {"runId": "run_1", "toolName": "merge_pr"}, lambda: "gh")
    with_gitlab_action(apie, {"runId": "run_1", "toolName": "deploy_release"}, lambda: "gl")
    with_issue_tracker_action(
        apie,
        {"runId": "run_1", "toolName": "update_issue", "provider": "jira"},
        lambda: "issue",
    )
    with_incident_response_action(
        apie, {"runId": "run_1", "toolName": "page_oncall"}, lambda: "incident"
    )
    with_observability_correlation(
        apie, {"runId": "run_1", "toolName": "fetch_sentry_issue"}, lambda: "obs"
    )

    assert len(calls) == 5
    assert calls[0]["tool"]["provider"] == "github"
    assert calls[1]["tool"]["provider"] == "gitlab"
    assert calls[2]["tool"]["provider"] == "jira"


@pytest.mark.asyncio
async def test_async_helpers_route_to_async_primitives() -> None:
    calls: list[dict] = []

    class FakeApie:
        async def with_tool(self, payload, fn):
            calls.append(payload)
            return await fn()

        async def with_guard(self, payload, fn):
            calls.append(payload)
            return await fn()

    apie = FakeApie()

    async def _ok() -> str:
        return "ok"

    result = await with_openai_tool_call_async(
        apie, {"runId": "run_1", "toolName": "search_docs"}, _ok
    )
    assert result == "ok"

    with_http_guard = create_http_guard_async(apie)
    result_guard = await with_http_guard(
        {"actionName": "GET /status", "resourceType": "internal_api"},
        _ok,
    )
    assert result_guard == "ok"
    assert len(calls) == 2
