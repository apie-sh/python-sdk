"""LangChain-compatible callback handler for Apie (duck-typed)."""

from __future__ import annotations

import json
from typing import Any, Optional


class ApieCallbackHandler:
    def __init__(self, apie: Any, *, default_environment: Optional[str] = None) -> None:
        self.apie = apie
        self.default_environment = default_environment
        self._tool_runs: dict[str, dict[str, str]] = {}

    @property
    def name(self) -> str:
        return "ApieCallbackHandler"

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, *, run_id: str, **_: Any) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        self._tool_runs[run_id] = {"tool_name": str(tool_name), "input": input_str}
        run_id_ctx = self.apie.ready() and self.apie._active_session_id  # noqa: SLF001
        _ = run_id_ctx

    def on_tool_end(self, output: str, *, run_id: str, **_: Any) -> None:
        ctx = self._tool_runs.pop(run_id, {})
        tool_name = ctx.get("tool_name", "unknown_tool")
        self.apie.track(
            {
                "type": "agent.action.completed",
                "payload": {
                    "tool": {"name": tool_name, "provider": "langchain"},
                    "metadata": {"output_preview": str(output)[:500]},
                },
            }
        )

    def on_tool_error(self, error: BaseException, *, run_id: str, **_: Any) -> None:
        ctx = self._tool_runs.pop(run_id, {})
        tool_name = ctx.get("tool_name", "unknown_tool")
        self.apie.capture_error(error, metadata={"tool": tool_name})

    def on_chain_start(self, serialized: dict[str, Any], inputs: dict[str, Any], *, run_id: str, **_: Any) -> None:
        self.apie.track(
            {
                "type": "agent.workflow.step.started",
                "payload": {
                    "step_name": serialized.get("name", "chain"),
                    "payload_summary": {"inputs": list(inputs.keys())},
                },
            }
        )

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: str, **_: Any) -> None:
        self.apie.track(
            {
                "type": "agent.workflow.step.completed",
                "payload": {
                    "payload_summary": {
                        "outputs": list(outputs.keys()),
                        "preview": json.dumps(outputs, default=str)[:500],
                    }
                },
            }
        )
