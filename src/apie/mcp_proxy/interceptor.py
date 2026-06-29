from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

from ..mcp_core.client import ApieMcpClient
from ..mcp_core.config import McpServerConfig
from ..mcp_core.payload import (
    McpToolCallInput,
    build_mcp_tool_call_payload,
    build_mcp_workflow_payload,
)
from ..types import GuardDecision

APIE_BLOCKED_CODE = -32001
APIE_APPROVAL_CODE = -32002


@dataclass(slots=True)
class ToolCallInterceptResult:
    allowed: bool
    error: dict[str, Any] | None = None


class McpInterceptor:
    def __init__(
        self,
        *,
        config: McpServerConfig,
        apie_client: ApieMcpClient,
        run_id: str | None = None,
    ) -> None:
        self._config = config
        self._apie_client = apie_client
        self._run_id = run_id or os.environ.get("APIE_RUN_ID") or f"run_mcp_{uuid.uuid4().hex[:12]}"
        self._tools_listed = False

    @property
    def run_id(self) -> str:
        return self._run_id

    def handle_tools_list(
        self,
        tools: list[dict[str, Any]],
    ) -> None:
        events = [
            self._apie_client.build_tools_listed_event(self._run_id, self._config.server_name, tools)
        ]
        self._apie_client.send(events)

        for tool in tools:
            try:
                from ..types import ToolDefinitionInput

                self._apie_client.define_tool(
                    ToolDefinitionInput(
                        name=f"{self._config.server_name}.{tool['name']}",
                        provider="mcp",
                        description=tool.get("description"),
                        input_schema=tool.get("inputSchema") or tool.get("input_schema"),
                        risk_level="medium",
                    )
                )
            except Exception as exc:
                print(f"[apie] Failed to define tool {tool.get('name')}: {exc}")
        self._tools_listed = True

    def before_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> ToolCallInterceptResult:
        payload = build_mcp_tool_call_payload(
            McpToolCallInput(
                server_name=self._config.server_name,
                tool_name=tool_name,
                arguments=args,
                environment=self._config.environment,
                redact_keys=self._config.redact_keys,
            )
        )
        workflow_summary = build_mcp_workflow_payload(
            McpToolCallInput(
                server_name=self._config.server_name,
                tool_name=tool_name,
                arguments=args,
                environment=self._config.environment,
                redact_keys=self._config.redact_keys,
            ),
            payload,
        )

        decision = self._apie_client.evaluate(self._run_id, payload)
        events = [
            self._apie_client.build_guardrail_evaluated_event(self._run_id, payload, decision),
            *self._apie_client.build_tool_call_events(self._run_id, payload),
            self._apie_client.build_mcp_called_event(
                self._run_id,
                payload.tool["name"],
                workflow_summary,
            ),
        ]
        self._apie_client.send(events)
        return self._enforce_decision(decision, payload)

    def _enforce_decision(
        self,
        decision: GuardDecision,
        payload: Any,
    ) -> ToolCallInterceptResult:
        if decision.effective_decision == "block":
            return ToolCallInterceptResult(
                allowed=False,
                error={
                    "code": APIE_BLOCKED_CODE,
                    "message": "Action blocked by Apie guardrail",
                    "data": {
                        "reason": decision.reason,
                        "decision_id": decision.decision_id,
                        "policy_decision": decision.policy_decision,
                        "effective_decision": decision.effective_decision,
                        "enforcement_action": decision.enforcement_action,
                        "mode": decision.mode,
                        "matched_guardrail": (
                            decision.matched_guardrails[0].get("key")
                            if decision.matched_guardrails
                            else None
                        ),
                    },
                },
            )

        if decision.effective_decision == "require_approval" and decision.approval_id:
            self._apie_client.send(
                [
                    self._apie_client.build_approval_requested_event(
                        self._run_id,
                        payload,
                        decision.approval_id,
                        decision.reason,
                    )
                ]
            )
            status = self._apie_client.wait_for_approval(
                decision.approval_id,
                self._config.approval_timeout_ms,
            )
            self._apie_client.send(
                [
                    self._apie_client.build_approval_resolved_event(
                        self._run_id,
                        decision.approval_id,
                        status,
                    )
                ]
            )
            if status != "approved":
                return ToolCallInterceptResult(
                    allowed=False,
                    error={
                        "code": APIE_APPROVAL_CODE,
                        "message": f"Action not approved: {status}",
                        "data": {
                            "approval_id": decision.approval_id,
                            "status": status,
                            "reason": decision.reason,
                        },
                    },
                )

        return ToolCallInterceptResult(allowed=True)

    def after_tool_call_success(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> None:
        payload = build_mcp_tool_call_payload(
            McpToolCallInput(
                server_name=self._config.server_name,
                tool_name=tool_name,
                arguments=args,
                environment=self._config.environment,
                redact_keys=self._config.redact_keys,
            )
        )
        self._apie_client.send(
            [
                self._apie_client.build_mcp_completed_event(self._run_id, payload.tool["name"]),
                self._apie_client.build_action_completed_event(self._run_id, payload),
            ]
        )

    def after_tool_call_failure(
        self,
        tool_name: str,
        args: dict[str, Any] | None,
        error: Exception,
    ) -> None:
        payload = build_mcp_tool_call_payload(
            McpToolCallInput(
                server_name=self._config.server_name,
                tool_name=tool_name,
                arguments=args,
                environment=self._config.environment,
                redact_keys=self._config.redact_keys,
            )
        )
        self._apie_client.send(
            [
                self._apie_client.build_mcp_failed_event(
                    self._run_id,
                    payload.tool["name"],
                    {"message": str(error)},
                ),
                self._apie_client.build_action_failed_event(
                    self._run_id,
                    payload,
                    {"message": str(error)},
                ),
            ]
        )

    def has_listed_tools(self) -> bool:
        return self._tools_listed

    @staticmethod
    def format_blocked_result(error: dict[str, Any]) -> str:
        return json.dumps(error)
