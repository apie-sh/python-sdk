from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

from ..capabilities import define_tool
from ..events import (
    build_action_completed_event,
    build_action_failed_event,
    build_action_requested_event,
    build_approval_requested_event,
    build_approval_resolved_event,
    build_guardrail_evaluated_event,
    build_tool_call_event,
    build_workflow_event,
    send_events,
)
from ..guard import evaluate_guard, wait_for_approval
from ..http import ApieClientOptions, HttpClient
from ..registration import identify_agent
from ..types import ApieAgentConfig, ApieConfig, ApieRuntimeConfig, GuardDecision, QueuedEvent, RegisterResponse, ReleaseMode, ToolDefinitionInput
from .payload import McpGuardPayload


@dataclass(slots=True)
class ApieMcpClientOptions:
    agent_key: str
    api_key: str | None = None
    base_url: str | None = None
    agent_name: str | None = None
    release_mode: ReleaseMode = "monitor"
    runtime: ApieRuntimeConfig | None = None


class ApieMcpClient:
    def __init__(self, options: ApieMcpClientOptions) -> None:
        self._agent_key = options.agent_key
        self._release_mode = options.release_mode
        self._agent_name = options.agent_name
        self._runtime = options.runtime
        self._registration: RegisterResponse | None = None
        self._sequence = 0
        api_key = options.api_key or os.environ.get("APIE_API_KEY")
        base_url = options.base_url or os.environ.get("APIE_BASE_URL") or "https://api.apie.sh"
        self._http = HttpClient(ApieClientOptions(base_url=base_url, api_key=api_key))

    def guard_mode(self) -> Literal["monitor", "enforce"]:
        return "enforce" if self._release_mode == "guard" else "monitor"

    def identify(self) -> RegisterResponse:
        if self._registration:
            return self._registration
        config = ApieConfig(
            agent=ApieAgentConfig(
                key=self._agent_key,
                name=self._agent_name or self._agent_key,
            ),
            runtime=self._runtime or ApieRuntimeConfig(),
            release_mode=self._release_mode,
        )
        self._registration = identify_agent(self._http, config)
        return self._registration

    def evaluate(self, run_id: str | None, payload: McpGuardPayload) -> GuardDecision:
        decision = evaluate_guard(
            self._http,
            agent_key=self._agent_key,
            run_id=run_id,
            mode=self.guard_mode(),
            risk_level=payload.risk_level,
            action={
                "type": payload.action["type"],
                "name": payload.action["name"],
            },
            resource={
                "type": payload.resource["type"],
                "provider": payload.resource.get("provider"),
                "environment": payload.resource.get("environment"),
            },
            tool=payload.tool,
            metadata=payload.metadata,
        )

        if self.guard_mode() == "monitor" and decision.type in {"block", "require_approval"}:
            action = "block" if decision.type == "block" else "require approval"
            print(f"[apie] Would {action} in guard mode: {decision.reason}")
            return GuardDecision(
                type="allow",
                reason=decision.reason,
                decision_id=decision.decision_id,
                approval_id=decision.approval_id,
                receipt_id=decision.receipt_id,
                monitor_decision=decision.type,
                matched_guardrails=decision.matched_guardrails,
            )
        return decision

    def wait_for_approval(self, approval_id: str, timeout_ms: int | None = None) -> str:
        return wait_for_approval(
            self._http,
            approval_id,
            timeout_ms=timeout_ms or 300_000,
        )

    def define_tool(self, tool: ToolDefinitionInput) -> dict[str, Any]:
        registration = self.identify()
        return define_tool(
            self._http,
            registration.agent_id,
            tool,
        )

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _enrich(self, event: QueuedEvent) -> QueuedEvent:
        registration = self.identify()
        metadata = {**(event.get("metadata") or {}), "capture_source": "mcp_proxy"}
        return {
            **event,
            "agentId": registration.agent_id,
            "agentVersionId": registration.agent_version_id,
            "sequenceNumber": event.get("sequenceNumber") or self._next_sequence(),
            "metadata": metadata,
        }

    def send(self, events: list[QueuedEvent]) -> None:
        self.identify()
        send_events(self._http, [self._enrich(event) for event in events])

    def build_tool_call_events(
        self,
        run_id: str | None,
        payload: McpGuardPayload,
    ) -> list[QueuedEvent]:
        input_data = {
            "runId": run_id,
            "tool": payload.tool,
            "action": payload.action,
            "resource": payload.resource,
            "metadata": payload.metadata,
        }
        return [
            build_tool_call_event(self._agent_key, input_data),
            build_action_requested_event(
                self._agent_key,
                {**input_data, "riskLevel": payload.risk_level},
            ),
        ]

    def build_mcp_called_event(
        self,
        run_id: str | None,
        step_name: str,
        payload_summary: dict[str, Any],
    ) -> QueuedEvent:
        return build_workflow_event(
            "agent.mcp.called",
            self._agent_key,
            {
                "runId": run_id,
                "stepName": step_name,
                "eventCategory": "mcp",
                "payloadSummary": payload_summary,
            },
        )

    def build_mcp_completed_event(self, run_id: str | None, step_name: str) -> QueuedEvent:
        return build_workflow_event(
            "agent.mcp.completed",
            self._agent_key,
            {
                "runId": run_id,
                "stepName": step_name,
                "eventCategory": "mcp",
            },
        )

    def build_mcp_failed_event(
        self,
        run_id: str | None,
        step_name: str,
        error: dict[str, str],
    ) -> QueuedEvent:
        return build_workflow_event(
            "agent.mcp.failed",
            self._agent_key,
            {
                "runId": run_id,
                "stepName": step_name,
                "eventCategory": "mcp",
                "error": error,
            },
        )

    def build_action_completed_event(
        self,
        run_id: str | None,
        payload: McpGuardPayload,
    ) -> QueuedEvent:
        return build_action_completed_event(
            self._agent_key,
            {
                "runId": run_id,
                "action": payload.action,
                "resource": payload.resource,
                "tool": payload.tool,
                "metadata": payload.metadata,
                "result": {"status": "executed"},
            },
        )

    def build_action_failed_event(
        self,
        run_id: str | None,
        payload: McpGuardPayload,
        error: dict[str, str],
    ) -> QueuedEvent:
        return build_action_failed_event(
            self._agent_key,
            {
                "runId": run_id,
                "action": payload.action,
                "resource": payload.resource,
                "tool": payload.tool,
                "metadata": payload.metadata,
                "error": error,
            },
        )

    def build_guardrail_evaluated_event(
        self,
        run_id: str | None,
        payload: McpGuardPayload,
        decision: GuardDecision,
    ) -> QueuedEvent:
        return build_guardrail_evaluated_event(
            self._agent_key,
            {
                "runId": run_id,
                "decision": decision.monitor_decision or decision.type,
                "reason": decision.reason,
                "action": payload.action,
                "resource": payload.resource,
            },
        )

    def build_approval_requested_event(
        self,
        run_id: str | None,
        payload: McpGuardPayload,
        approval_id: str,
        reason: str | None = None,
    ) -> QueuedEvent:
        return build_approval_requested_event(
            self._agent_key,
            {
                "runId": run_id,
                "approvalId": approval_id,
                "action": payload.action,
                "resource": payload.resource,
                "reason": reason,
            },
        )

    def build_approval_resolved_event(
        self,
        run_id: str | None,
        approval_id: str,
        status: str,
    ) -> QueuedEvent:
        return build_approval_resolved_event(
            self._agent_key,
            {
                "runId": run_id,
                "approvalId": approval_id,
                "status": status,
            },
        )

    def build_tools_listed_event(
        self,
        run_id: str | None,
        server_name: str,
        tools: list[dict[str, str]],
    ) -> QueuedEvent:
        return build_workflow_event(
            "agent.mcp.tools_listed",
            self._agent_key,
            {
                "runId": run_id,
                "stepName": f"{server_name}.tools_list",
                "eventCategory": "mcp",
                "payloadSummary": {
                    "server": server_name,
                    "tool_count": len(tools),
                    "tools": [tool["name"] for tool in tools],
                },
                "metadata": {
                    "capture_source": "mcp_proxy",
                    "mcp": {"server": server_name, "tools": tools},
                },
            },
        )
