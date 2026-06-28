"""OpenAI Agents SDK hooks for Apie (duck-typed)."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional


def create_apie_run_hooks(
    apie: Any,
    *,
    agent_name: str = "openai-agent",
    default_environment: Optional[str] = None,
) -> dict[str, Callable[..., Any]]:
    def on_agent_start(context: dict[str, Any]) -> None:
        _ = context
        apie.track(
            {
                "type": "agent.workflow.step.started",
                "payload": {
                    "step_name": f"{agent_name} start",
                    "payload_summary": {"provider": "openai-agents", "agent": agent_name},
                },
            }
        )

    def on_tool_start(context: dict[str, Any]) -> None:
        tool_name = context.get("toolName", "unknown_tool")
        apie.with_tool(
            {
                "tool": {"name": tool_name, "provider": "openai", "riskLevel": "medium"},
                "action": {"type": "execute", "name": tool_name},
                "resource": {
                    "type": "llm_tool",
                    "provider": "openai",
                    "environment": default_environment,
                },
                "metadata": {"agent": agent_name, "arguments": context.get("arguments")},
                "guard": False,
            },
            lambda: None,
        )

    def on_tool_end(context: dict[str, Any]) -> None:
        tool_name = context.get("toolName", "unknown_tool")
        apie.track_action_completed(
            {
                "action": {"type": "execute", "name": tool_name},
                "resource": {"type": "llm_tool", "environment": default_environment},
                "tool": {"name": tool_name, "provider": "openai"},
                "metadata": {
                    "result_preview": json.dumps(context.get("result"), default=str)[:500]
                },
            }
        )

    return {
        "onAgentStart": on_agent_start,
        "onToolStart": on_tool_start,
        "onToolEnd": on_tool_end,
    }
