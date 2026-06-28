from __future__ import annotations

from unittest.mock import MagicMock

from apie.mcp_core.config import McpServerConfig, McpUpstreamConfig
from apie.mcp_proxy.interceptor import APIE_APPROVAL_CODE, APIE_BLOCKED_CODE, McpInterceptor
from apie.types import GuardDecision


def _config(release_mode: str = "monitor") -> McpServerConfig:
    return McpServerConfig(
        server_name="test-server",
        agent_key="agent",
        release_mode=release_mode,  # type: ignore[arg-type]
        upstream=McpUpstreamConfig(command="echo"),
    )


def _mock_apie_client(**overrides: object) -> MagicMock:
    client = MagicMock()
    client.evaluate.return_value = GuardDecision(type="allow")
    client.build_guardrail_evaluated_event.return_value = {"type": "agent.guardrail.evaluated"}
    client.build_tool_call_events.return_value = [{"type": "agent.tool.called"}]
    client.build_mcp_called_event.return_value = {"type": "agent.mcp.called"}
    client.build_mcp_completed_event.return_value = {"type": "agent.mcp.completed"}
    client.build_action_completed_event.return_value = {"type": "agent.action.completed"}
    client.build_mcp_failed_event.return_value = {"type": "agent.mcp.failed"}
    client.build_action_failed_event.return_value = {"type": "agent.action.failed"}
    client.build_approval_requested_event.return_value = {"type": "agent.approval.requested"}
    client.build_approval_resolved_event.return_value = {"type": "agent.approval.resolved"}
    client.build_tools_listed_event.return_value = {"type": "agent.mcp.tools_listed"}
    client.wait_for_approval.return_value = "approved"
    for key, value in overrides.items():
        setattr(client, key, value)
    return client


def test_interceptor_allows_tool_calls_in_monitor_mode() -> None:
    apie_client = _mock_apie_client()
    interceptor = McpInterceptor(
        config=_config("monitor"),
        apie_client=apie_client,
        run_id="run_test",
    )

    result = interceptor.before_tool_call("search", {"q": "hello"})
    assert result.allowed is True
    apie_client.send.assert_called()


def test_interceptor_blocks_when_guard_decision_is_block() -> None:
    apie_client = _mock_apie_client()
    apie_client.evaluate.return_value = GuardDecision(
        type="block",
        reason="blocked",
        decision_id="dec_1",
    )
    interceptor = McpInterceptor(
        config=_config("guard"),
        apie_client=apie_client,
    )

    result = interceptor.before_tool_call("delete_everything")
    assert result.allowed is False
    assert result.error is not None
    assert result.error["code"] == APIE_BLOCKED_CODE


def test_interceptor_waits_for_approval_when_required() -> None:
    apie_client = _mock_apie_client()
    apie_client.evaluate.return_value = GuardDecision(
        type="require_approval",
        approval_id="appr_1",
        reason="needs review",
    )
    interceptor = McpInterceptor(
        config=_config("guard"),
        apie_client=apie_client,
    )

    result = interceptor.before_tool_call("deploy")
    assert result.allowed is True
    apie_client.wait_for_approval.assert_called_with("appr_1", None)


def test_interceptor_rejects_when_approval_not_granted() -> None:
    apie_client = _mock_apie_client()
    apie_client.evaluate.return_value = GuardDecision(
        type="require_approval",
        approval_id="appr_1",
        reason="needs review",
    )
    apie_client.wait_for_approval.return_value = "timeout"
    interceptor = McpInterceptor(
        config=_config("guard"),
        apie_client=apie_client,
    )

    result = interceptor.before_tool_call("deploy")
    assert result.allowed is False
    assert result.error is not None
    assert result.error["code"] == APIE_APPROVAL_CODE
