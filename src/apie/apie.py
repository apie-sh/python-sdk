from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional, TypeVar

from .capabilities import (
    async_declare_capabilities,
    async_define_tool,
    declare_capabilities,
    define_tool,
)
from .config import (
    is_apie_client,
    load_apie_module,
    resolve_config,
)
from .events import (
    async_validate_events,
    build_action_completed_event,
    build_action_failed_event,
    build_action_requested_event,
    build_approval_requested_event,
    build_approval_resolved_event,
    build_error_event,
    build_guardrail_evaluated_event,
    build_resource_touched_event,
    build_tool_call_event,
    build_workflow_event,
    redact_event,
    validate_events,
)
from .guard import (
    async_evaluate_guard,
    async_get_approval_status,
    async_wait_for_approval,
    evaluate_guard,
    get_approval_status,
    wait_for_approval,
)
from .http import (
    ApieClientOptions,
    AsyncApieClientOptions,
    AsyncHttpClient,
    HttpClient,
)
from .queue import AsyncEventQueue, EventQueue, EventQueueDiagnostics
from .registration import (
    async_identify_agent,
    identify_agent,
)
from .reports import (
    async_create_report,
    async_get_report,
    async_wait_until_report_ready,
    create_report,
    get_report,
    wait_until_report_ready,
)
from .runs import async_complete_run, async_create_run, complete_run, create_run
from .sessions import (
    async_complete_session,
    async_create_child_run,
    async_create_session,
    async_record_handoff,
    complete_session,
    create_child_run,
    create_session,
    record_handoff,
)
from .types import (
    AgentRun,
    ApieConfig,
    ApieSession,
    BoundaryReportCreateInput,
    DeclaredCapabilityInput,
    GuardDecision,
    RegisterResponse,
    SendTestEventResult,
    ToolDefinitionInput,
)

T = TypeVar("T")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_tool_dict(tool: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if tool is None:
        return None
    return {
        "name": tool.get("name"),
        "provider": tool.get("provider"),
        "riskLevel": tool.get("riskLevel") or tool.get("risk_level"),
    }


@dataclass(slots=True)
class _RunsProxy:
    apie: "Apie"

    def start(
        self,
        *,
        input_summary: Optional[str] = None,
        environment: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentRun:
        return self.apie.start_run(
            input_summary=input_summary,
            environment=environment,
            metadata=metadata,
        )

    def complete(
        self,
        run_id: str,
        *,
        status: str = "completed",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.apie.complete_run(run_id, status=status, metadata=metadata)


@dataclass(slots=True)
class _CapabilitiesProxy:
    apie: "Apie"

    def declare(
        self, capabilities: list[DeclaredCapabilityInput]
    ) -> dict[str, list[dict[str, str]]]:
        return self.apie.declare_capabilities(capabilities)


@dataclass(slots=True)
class _ToolsProxy:
    apie: "Apie"

    def define(self, tool: ToolDefinitionInput) -> dict[str, Any]:
        return self.apie.define_tool(tool)


@dataclass(slots=True)
class _ApprovalsProxy:
    apie: "Apie"

    def wait(
        self,
        approval_id: str,
        *,
        timeout_ms: Optional[int] = None,
        poll_interval_ms: Optional[int] = None,
    ) -> str:
        return wait_for_approval(
            self.apie._http,
            approval_id,
            timeout_ms=timeout_ms or self.apie._config.approval_timeout_ms,
            poll_interval_ms=poll_interval_ms or 2000,
        )

    def get_status(self, approval_id: str) -> dict[str, str]:
        return get_approval_status(self.apie._http, approval_id)


@dataclass(slots=True)
class _ReportsProxy:
    apie: "Apie"

    def create(self, input: Optional[BoundaryReportCreateInput] = None) -> Any:
        return self.apie.create_boundary_report(input)

    def get(self, report_id: str) -> dict[str, Any]:
        return get_report(self.apie._http, report_id)

    def wait_until_ready(
        self,
        report_id: str,
        *,
        timeout_ms: int = 30000,
        poll_interval_ms: int = 1000,
    ) -> dict[str, Any]:
        return wait_until_report_ready(
            self.apie._http,
            report_id,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )


class Apie:
    def __init__(self, config: Optional[ApieConfig | dict[str, Any]] = None) -> None:
        if config is None:
            raise ValueError("Apie requires config. Pass options or create apie.config.py/json.")
        self._config = resolve_config(config)
        self._validate_config()
        self._http = HttpClient(
            ApieClientOptions(
                base_url=self._config.base_url or "",
                api_key=self._config.api_key,
                timeout=self._config.timeout,
                headers={str(k): str(v) for k, v in self._config.headers.items()},
            )
        )

        self._queue = EventQueue(
            self._http,
            flush_interval_ms=self._config.flush_interval_ms,
            max_batch_size=self._config.max_batch_size,
            max_queue_size=self._config.max_queue_size,
            retry_attempts=self._config.retry_attempts,
            retry_base_delay_ms=self._config.retry_base_delay_ms,
            drop_policy=self._config.queue_drop_policy,
            durable_storage_path=self._config.queue_storage_path,
            idempotency_key=self._config.queue_idempotency_key,
            on_error=self._handle_queue_error,
            transform=self._prepare_event,
        )
        self._registration: Optional[RegisterResponse] = None
        self._registration_error: Optional[Exception] = None
        self._run_sequences: dict[str, int] = {}
        self._session_sequences: dict[str, int] = {}
        self._active_session_id: Optional[str] = None
        self._disabled_session_counter = 0
        self._disabled_run_counter = 0

        self.runs = _RunsProxy(self)
        self.capabilities = _CapabilitiesProxy(self)
        self.tools = _ToolsProxy(self)
        self.approvals = _ApprovalsProxy(self)
        self.reports = _ReportsProxy(self)

        if self._is_enabled():
            self._queue.start()
            self._start_registration()

    @classmethod
    def create(cls, config: Optional[ApieConfig | dict[str, Any]] = None) -> "Apie":
        loaded = load_apie_module()
        if loaded is not None and is_apie_client(loaded):
            return loaded
        resolved = resolve_config(config, loaded)
        return cls(resolved)

    @classmethod
    def from_config(cls, config: Optional[ApieConfig | dict[str, Any]] = None) -> "Apie":
        return cls.create(config)

    def _validate_config(self) -> None:
        if not self._config.api_key:
            raise ValueError("APIE_API_KEY is required")
        if not self._config.agent.key:
            raise ValueError("agent.key is required")
        if not self._config.agent.name:
            raise ValueError("agent.name is required")

    def _is_enabled(self) -> bool:
        return self._config.enabled is not False

    def _disabled_registration(self) -> RegisterResponse:
        return RegisterResponse(
            agent_id=f"disabled_agent_{self._config.agent.key}",
            agent_version_id="disabled_version",
            workspace_id="disabled_workspace",
            config_hash="disabled",
            status="registered",
            created=False,
            version_created=False,
            ingest_url=self._config.base_url or "",
            recommended_next_step="Enable Apie to send telemetry.",
            dashboard_url=self._config.base_url or "",
        )

    def _create_disabled_run(self, session_id: Optional[str] = None) -> AgentRun:
        self._disabled_run_counter += 1
        return AgentRun(
            id=f"disabled_run_{self._disabled_run_counter}",
            session_id=session_id,
            status="completed",
            started_at=_now_iso(),
        )

    def _create_disabled_session(self) -> ApieSession:
        self._disabled_session_counter += 1
        return ApieSession(
            id=f"disabled_session_{self._disabled_session_counter}",
            status="completed",
            started_at=_now_iso(),
        )

    def _handle_queue_error(self, error: Exception) -> None:
        mode = self._config.on_error
        if mode == "silent":
            return
        if mode == "throw":
            raise error
        print(f"[apie] Event flush failed: {error}")

    def _next_sequence(self, run_id: Optional[str]) -> Optional[int]:
        if not run_id:
            return None
        next_value = self._run_sequences.get(run_id, 0) + 1
        self._run_sequences[run_id] = next_value
        return next_value

    def _next_session_sequence(self, session_id: Optional[str]) -> Optional[int]:
        current = session_id or self._active_session_id
        if not current:
            return None
        next_value = self._session_sequences.get(current, 0) + 1
        self._session_sequences[current] = next_value
        return next_value

    def _event_context(
        self, run_id: Optional[str] = None, session_id: Optional[str] = None
    ) -> dict[str, Any]:
        resolved_session_id = session_id or self._active_session_id
        if not self._is_enabled():
            return {
                "agentId": None,
                "agentVersionId": None,
                "sessionId": resolved_session_id,
                "runId": run_id,
                "sequenceNumber": self._next_sequence(run_id),
                "sessionSequenceNumber": self._next_session_sequence(resolved_session_id),
                "environment": self._config.runtime.environment,
            }
        registration = self.ready()
        return {
            "agentId": registration.agent_id,
            "agentVersionId": registration.agent_version_id,
            "sessionId": resolved_session_id,
            "runId": run_id,
            "sequenceNumber": self._next_sequence(run_id),
            "sessionSequenceNumber": self._next_session_sequence(resolved_session_id),
            "environment": self._config.runtime.environment,
        }

    def _prepare_event(self, event: dict[str, Any]) -> dict[str, Any]:
        return redact_event(
            event,
            redact=self._config.redact,
            redact_keys=self._config.redact_keys,
            redact_allow_paths=self._config.redact_allow_paths,
            redact_deny_patterns=self._config.redact_deny_patterns,
            max_payload_bytes=self._config.max_event_payload_bytes,
        )

    def _enqueue(self, event: dict[str, Any]) -> None:
        if not self._is_enabled():
            return
        self._queue.enqueue(event)

    def _start_registration(self) -> None:
        try:
            if self._registration is None:
                self._registration = identify_agent(self._http, self._config)
                self._registration_error = None
                self._auto_declare_capabilities(self._registration.agent_id)
        except Exception as error:
            self._registration_error = error
            self._handle_queue_error(error)

    def _with_session_scope(self, session_id: Optional[str], fn: Callable[[], T]) -> T:
        previous = self._active_session_id
        self._active_session_id = session_id
        try:
            return fn()
        finally:
            self._active_session_id = previous

    def identify(self) -> RegisterResponse:
        if not self._is_enabled():
            self._registration = self._disabled_registration()
            self._registration_error = None
            return self._registration
        try:
            result = identify_agent(self._http, self._config)
            self._registration = result
            self._registration_error = None
            self._auto_declare_capabilities(result.agent_id)
            return result
        except Exception as error:
            self._registration_error = error
            raise

    def _auto_declare_capabilities(self, agent_id: str) -> None:
        if not self._config.capabilities:
            return
        try:
            declare_capabilities(self._http, agent_id, self._config.capabilities)
        except Exception as error:
            self._handle_queue_error(error)

    def ready(self) -> RegisterResponse:
        if not self._is_enabled():
            if self._registration is None:
                self._registration = self._disabled_registration()
            return self._registration
        if self._registration is not None:
            return self._registration
        if self._registration_error is not None:
            raise self._registration_error
        return self.identify()

    @property
    def agent_id(self) -> Optional[str]:
        return self._registration.agent_id if self._registration else None

    @property
    def agent_version_id(self) -> Optional[str]:
        return self._registration.agent_version_id if self._registration else None

    def declare_capabilities(self, capabilities: list[DeclaredCapabilityInput]) -> dict[str, Any]:
        registration = self.ready()
        return declare_capabilities(self._http, registration.agent_id, capabilities)

    def define_tool(self, tool: ToolDefinitionInput) -> dict[str, Any]:
        registration = self.ready()
        return define_tool(self._http, registration.agent_id, tool)

    def start_run(
        self,
        *,
        input_summary: Optional[str] = None,
        input: Optional[dict[str, Any]] = None,
        environment: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentRun:
        if not self._is_enabled():
            return self._create_disabled_run()
        registration = self.ready()
        merged_metadata = {**(metadata or {})}
        if input is not None:
            merged_metadata["input"] = input
        return create_run(
            self._http,
            agent_key=self._config.agent.key,
            agent_id=registration.agent_id,
            agent_version_id=registration.agent_version_id,
            environment=environment or self._config.runtime.environment,
            input_summary=input_summary,
            metadata=merged_metadata or None,
        )

    def complete_run(
        self,
        run_id: str,
        *,
        status: str = "completed",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if not self._is_enabled():
            return
        self.flush()
        complete_run(self._http, run_id, status=status, metadata=metadata)
        self._run_sequences.pop(run_id, None)

    @contextmanager
    def run_context(
        self,
        *,
        session_id: Optional[str] = None,
        input_summary: Optional[str] = None,
        environment: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        step_name: Optional[str] = None,
        step_key: Optional[str] = None,
        step_index: Optional[int] = None,
    ):
        if session_id:
            run = create_child_run(
                self._http,
                session_id,
                agent_key=self._config.agent.key,
                agent_id=self.ready().agent_id,
                agent_version_id=self.ready().agent_version_id,
                environment=environment or self._config.runtime.environment,
                input_summary=input_summary,
                metadata=metadata,
                step_name=step_name,
                step_key=step_key,
                step_index=step_index,
            )
        else:
            run = self.start_run(
                input_summary=input_summary,
                environment=environment,
                metadata=metadata,
            )

        previous = self._active_session_id
        self._active_session_id = session_id or run.session_id
        try:
            yield run
            self.complete_run(run.id, status="completed")
        except Exception as error:
            self.capture_error(error, run_id=run.id, session_id=session_id or run.session_id)
            self.complete_run(run.id, status="failed")
            raise
        finally:
            self._active_session_id = previous
            self.flush()

    def with_run(
        self,
        input: dict[str, Any],
        fn: Callable[[AgentRun], T],
    ) -> T:
        if not self._is_enabled():
            return fn(self._create_disabled_run(input.get("sessionId")))
        with self.run_context(
            session_id=input.get("sessionId"),
            input_summary=input.get("inputSummary"),
            environment=input.get("environment"),
            metadata=input.get("metadata"),
            step_name=input.get("stepName"),
            step_key=input.get("stepKey"),
            step_index=input.get("stepIndex"),
        ) as run:
            return fn(run)

    @contextmanager
    def session_context(
        self,
        *,
        kind: str = "single_agent",
        input_summary: Optional[str] = None,
        environment: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        if not self._is_enabled():
            session = self._create_disabled_session()
            yield session
            return

        registration = self.ready()
        session = create_session(
            self._http,
            kind=kind,  # type: ignore[arg-type]
            orchestrator_agent_key=self._config.agent.key,
            orchestrator_agent_id=registration.agent_id,
            environment=environment or self._config.runtime.environment,
            input_summary=input_summary,
            metadata=metadata,
        )
        previous = self._active_session_id
        self._active_session_id = session.id
        try:
            yield session
            complete_session(self._http, session.id, status="completed")
        except Exception as error:
            self.capture_error(error, session_id=session.id)
            complete_session(self._http, session.id, status="failed")
            raise
        finally:
            self._active_session_id = previous
            self._session_sequences.pop(session.id, None)
            self.flush()

    def with_session(self, input: dict[str, Any], fn: Callable[[ApieSession], T]) -> T:
        with self.session_context(
            kind=input.get("kind", "single_agent"),
            input_summary=input.get("inputSummary"),
            environment=input.get("environment"),
            metadata=input.get("metadata"),
        ) as session:
            return fn(session)

    def with_child_run(self, input: dict[str, Any], fn: Callable[[AgentRun], T]) -> T:
        if not self._is_enabled():
            return fn(self._create_disabled_run(input.get("sessionId")))
        session_id = input["sessionId"]

        def _run_child() -> T:
            run = create_child_run(
                self._http,
                session_id,
                agent_key=input.get("agentKey") or self._config.agent.key,
                agent_id=None if input.get("agentKey") else self.ready().agent_id,
                agent_version_id=(None if input.get("agentKey") else self.ready().agent_version_id),
                parent_run_id=input.get("parentRunId"),
                step_name=input.get("stepName"),
                step_key=input.get("stepKey"),
                step_index=input.get("stepIndex"),
                role=input.get("role"),
                input_summary=input.get("inputSummary"),
                metadata={
                    **(input.get("metadata") or {}),
                    "payload_summary": input.get("payloadSummary"),
                },
            )
            try:
                result = fn(run)
                self.complete_run(run.id, status="completed")
                return result
            except Exception as error:
                self.capture_error(error, run_id=run.id, session_id=session_id)
                self.complete_run(run.id, status="failed")
                raise
            finally:
                self.flush()

        return self._with_session_scope(session_id, _run_child)

    def track_handoff_requested(self, input: dict[str, Any]) -> None:
        registration = self.ready()
        record_handoff(
            self._http,
            input["sessionId"],
            source_run_id=input.get("sourceRunId"),
            source_agent_id=registration.agent_id,
            target_run_id=input.get("targetRunId"),
            target_agent_id=input.get("targetAgentId"),
            reason=input.get("reason"),
            input_summary=input.get("inputSummary"),
            payload_summary=input.get("payloadSummary"),
            status="requested",
        )
        ctx = self._event_context(input.get("sourceRunId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.handoff.requested",
                self._config.agent.key,
                {
                    **ctx,
                    "payloadSummary": input.get("payloadSummary"),
                    "metadata": {
                        "reason": input.get("reason"),
                        "target_run_id": input.get("targetRunId"),
                        "target_agent_id": input.get("targetAgentId"),
                    },
                },
            )
        )

    def track_handoff_completed(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.handoff.completed",
                self._config.agent.key,
                {**ctx, "payloadSummary": input.get("payloadSummary")},
            )
        )

    def track_handoff_failed(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.handoff.failed",
                self._config.agent.key,
                {
                    **ctx,
                    "payloadSummary": input.get("payloadSummary"),
                    "error": input.get("error"),
                },
            )
        )

    def with_workflow_step(self, input: dict[str, Any], fn: Callable[[], T]) -> T:
        ctx = self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.workflow.step.started",
                self._config.agent.key,
                {
                    **ctx,
                    "stepKey": input.get("stepKey"),
                    "stepName": input.get("stepName"),
                    "stepIndex": input.get("stepIndex"),
                    "payloadSummary": input.get("payloadSummary"),
                },
            )
        )
        try:
            result = fn()
            done = self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.workflow.step.completed",
                    self._config.agent.key,
                    {
                        **done,
                        "stepKey": input.get("stepKey"),
                        "stepName": input.get("stepName"),
                        "stepIndex": input.get("stepIndex"),
                    },
                )
            )
            return result
        except Exception as error:
            fail = self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.workflow.step.failed",
                    self._config.agent.key,
                    {
                        **fail,
                        "stepKey": input.get("stepKey"),
                        "stepName": input.get("stepName"),
                        "stepIndex": input.get("stepIndex"),
                        "error": {"message": str(error)},
                    },
                )
            )
            raise

    def with_llm_call(self, input: dict[str, Any], fn: Callable[[], T]) -> T:
        ctx = self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.llm.called",
                self._config.agent.key,
                {
                    **ctx,
                    "stepName": input.get("stepName"),
                    "eventCategory": "llm",
                    "payloadSummary": input.get("payloadSummary"),
                },
            )
        )
        try:
            result = fn()
            done = self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.llm.completed",
                    self._config.agent.key,
                    {**done, "stepName": input.get("stepName")},
                )
            )
            return result
        except Exception as error:
            fail = self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.llm.failed",
                    self._config.agent.key,
                    {
                        **fail,
                        "stepName": input.get("stepName"),
                        "error": {"message": str(error)},
                    },
                )
            )
            raise

    def with_mcp_call(self, input: dict[str, Any], fn: Callable[[], T]) -> T:
        ctx = self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.mcp.called",
                self._config.agent.key,
                {
                    **ctx,
                    "stepName": input.get("stepName"),
                    "eventCategory": "mcp",
                    "payloadSummary": input.get("payloadSummary"),
                },
            )
        )
        try:
            result = fn()
            done = self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.mcp.completed",
                    self._config.agent.key,
                    {**done, "stepName": input.get("stepName")},
                )
            )
            return result
        except Exception as error:
            fail = self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.mcp.failed",
                    self._config.agent.key,
                    {
                        **fail,
                        "stepName": input.get("stepName"),
                        "error": {"message": str(error)},
                    },
                )
            )
            raise

    def track_tool_call(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"))
        self._enqueue(build_tool_call_event(self._config.agent.key, {**ctx, **input}))

    def track_action_requested(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"))
        self._enqueue(build_action_requested_event(self._config.agent.key, {**ctx, **input}))

    def track_action_completed(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"))
        self._enqueue(build_action_completed_event(self._config.agent.key, {**ctx, **input}))

    def track_action_failed(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"))
        self._enqueue(build_action_failed_event(self._config.agent.key, {**ctx, **input}))

    def track_resource_touched(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"))
        self._enqueue(build_resource_touched_event(self._config.agent.key, {**ctx, **input}))

    def track_approval_requested(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"))
        self._enqueue(build_approval_requested_event(self._config.agent.key, {**ctx, **input}))

    def track_approval_resolved(self, input: dict[str, Any]) -> None:
        ctx = self._event_context(input.get("runId"))
        self._enqueue(build_approval_resolved_event(self._config.agent.key, {**ctx, **input}))

    def track(self, event: dict[str, Any]) -> None:
        registration = self.ready()
        self._enqueue(
            {
                "type": event.get("type"),
                "agentKey": self._config.agent.key,
                "agentId": registration.agent_id,
                "agentVersionId": registration.agent_version_id,
                "runId": event.get("runId"),
                "sequenceNumber": self._next_sequence(event.get("runId")),
                "timestamp": _now_iso(),
                "metadata": event.get("payload"),
            }
        )

    def capture_error(
        self,
        error: Any,
        *,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        ctx = self._event_context(run_id, session_id)
        self._enqueue(
            build_error_event(self._config.agent.key, error, {**ctx, "metadata": metadata})
        )

    def _is_enforce_mode(self) -> bool:
        return self._config.release_mode == "guard"

    def _guard_mode(self) -> str:
        return "enforce" if self._is_enforce_mode() else "monitor"

    def _evaluate_guard_decision(self, input: dict[str, Any]) -> GuardDecision:
        if not self._is_enabled():
            return GuardDecision(type="allow")
        try:
            raw = evaluate_guard(
                self._http,
                agent_key=self._config.agent.key,
                run_id=input.get("runId"),
                mode=self._guard_mode(),  # type: ignore[arg-type]
                risk_level=input.get("riskLevel"),
                action=input["action"],
                resource=input["resource"],
                tool=_to_tool_dict(input.get("tool")),
                metadata=input.get("metadata"),
                redact=self._config.redact,
                redact_keys=self._config.redact_keys,
            )
            if not self._is_enforce_mode():
                if raw.type in {"block", "require_approval"} and raw.reason:
                    print(
                        "[apie] Would "
                        + ("block" if raw.type == "block" else "require approval")
                        + f" in enforcement mode: {raw.reason}"
                    )
                if raw.type == "warn" and raw.reason:
                    print(f"[apie] Guardrail warning: {raw.reason}")
                monitor_type = raw.type
                effective = "warn" if raw.type == "warn" else "allow"
                return GuardDecision(
                    type=effective,  # type: ignore[arg-type]
                    reason=raw.reason,
                    decision_id=raw.decision_id,
                    approval_id=raw.approval_id,
                    receipt_id=raw.receipt_id,
                    monitor_decision=monitor_type,
                    matched_guardrails=raw.matched_guardrails,
                )
            return raw
        except Exception as error:
            if self._config.guard_failure_mode == "fail_closed":
                return GuardDecision(type="block", reason=str(error))
            if self._config.guard_failure_mode == "throw":
                raise
            self._handle_queue_error(error)
            return GuardDecision(type="allow")

    def _enforce_guard_decision(self, input: dict[str, Any], decision: GuardDecision) -> None:
        ctx = self._event_context(input.get("runId"))
        self._enqueue(
            build_guardrail_evaluated_event(
                self._config.agent.key,
                {
                    **ctx,
                    "decision": decision.monitor_decision or decision.type,
                    "reason": decision.reason,
                    "action": input.get("action"),
                    "resource": input.get("resource"),
                },
            )
        )

        if decision.type == "block":
            raise RuntimeError(decision.reason or "Action blocked by guardrail")

        if decision.type == "warn" and decision.reason:
            print(f"[apie] Guardrail warning: {decision.reason}")

        if decision.type == "require_approval" and decision.approval_id:
            self.track_approval_requested(
                {
                    "runId": input.get("runId"),
                    "approvalId": decision.approval_id,
                    "action": input.get("action"),
                    "resource": input.get("resource"),
                    "reason": decision.reason,
                }
            )
            self.flush()
            status = self.approvals.wait(
                decision.approval_id,
                timeout_ms=self._config.approval_timeout_ms,
            )
            self.track_approval_resolved(
                {
                    "runId": input.get("runId"),
                    "approvalId": decision.approval_id,
                    "status": status,
                }
            )
            if status != "approved":
                raise RuntimeError(f"Action not approved: {status}")

    @contextmanager
    def guard_context(self, input: dict[str, Any]):
        decision = self._evaluate_guard_decision(input)
        self._enforce_guard_decision(input, decision)
        self.track_action_requested(
            {
                "runId": input.get("runId"),
                "action": input.get("action"),
                "resource": input.get("resource"),
                "tool": input.get("tool"),
                "metadata": input.get("metadata"),
                "riskLevel": input.get("riskLevel"),
            }
        )
        try:
            yield
            self.track_action_completed(
                {
                    "runId": input.get("runId"),
                    "action": input.get("action"),
                    "resource": input.get("resource"),
                    "tool": input.get("tool"),
                    "metadata": input.get("metadata"),
                    "result": {"status": "executed"},
                }
            )
        except Exception as error:
            self.track_action_failed(
                {
                    "runId": input.get("runId"),
                    "action": input.get("action"),
                    "resource": input.get("resource"),
                    "tool": input.get("tool"),
                    "error": {"message": str(error)},
                    "metadata": input.get("metadata"),
                }
            )
            self.capture_error(error, run_id=input.get("runId"))
            self.flush()
            raise

    def with_guard(self, input: dict[str, Any], fn: Callable[[], T]) -> T:
        with self.guard_context(input):
            return fn()

    @contextmanager
    def tool_context(self, input: dict[str, Any]):
        should_evaluate = input.get("guard", True) is not False
        action = input.get("action") or {"type": "execute", "name": input["tool"]["name"]}
        resource = input.get("resource") or {"type": "unknown"}
        if should_evaluate:
            decision = self._evaluate_guard_decision(
                {
                    "runId": input.get("runId"),
                    "action": action,
                    "resource": resource,
                    "tool": input.get("tool"),
                    "metadata": input.get("metadata"),
                    "riskLevel": (input.get("tool") or {}).get("riskLevel"),
                }
            )
            self._enforce_guard_decision(
                {
                    "runId": input.get("runId"),
                    "action": action,
                    "resource": resource,
                    "tool": input.get("tool"),
                },
                decision,
            )

        self.track_tool_call(input)
        self.track_action_requested(
            {
                "runId": input.get("runId"),
                "action": action,
                "resource": resource,
                "tool": input.get("tool"),
                "metadata": input.get("metadata"),
            }
        )
        try:
            yield
            self.track_action_completed(
                {
                    "runId": input.get("runId"),
                    "action": action,
                    "resource": resource,
                    "tool": input.get("tool"),
                    "metadata": input.get("metadata"),
                }
            )
        except Exception as error:
            self.track_action_failed(
                {
                    "runId": input.get("runId"),
                    "action": action,
                    "resource": resource,
                    "tool": input.get("tool"),
                    "error": {"message": str(error)},
                    "metadata": input.get("metadata"),
                }
            )
            self.capture_error(error, run_id=input.get("runId"))
            self.flush()
            raise

    def with_tool(self, input: dict[str, Any], fn: Callable[[], T]) -> T:
        with self.tool_context(input):
            return fn()

    def send_test_event(self, options: Optional[dict[str, Any]] = None) -> SendTestEventResult:
        mode = (options or {}).get("mode", "pipeline")
        if mode == "single":
            return self._send_single_test_event()
        return self._send_pipeline_test_event()

    def _send_single_test_event(self) -> SendTestEventResult:
        session_id = ""
        run_ids: list[str] = []

        def _session_fn(session: ApieSession) -> None:
            nonlocal session_id
            session_id = session.id

            def _run_fn(run: AgentRun) -> None:
                run_ids.append(run.id)
                self.with_tool(
                    {
                        "runId": run.id,
                        "tool": {"name": "test_tool", "provider": "apie", "riskLevel": "low"},
                        "action": {"type": "read", "name": "test_tool"},
                        "resource": {"type": "test_resource", "provider": "apie"},
                        "guard": False,
                    },
                    lambda: {"ok": True},
                )

            self.with_run(
                {"sessionId": session.id, "inputSummary": "Apie SDK test run"},
                _run_fn,
            )

        self.with_session(
            {
                "kind": "single_agent",
                "inputSummary": "Apie SDK test run",
                "metadata": {"test": True},
            },
            _session_fn,
        )

        return SendTestEventResult(session_id=session_id, run_ids=run_ids, mode="single")

    def _send_pipeline_test_event(self) -> SendTestEventResult:
        session_id = ""
        run_ids: list[str] = []

        def _session_fn(session: ApieSession) -> None:
            nonlocal session_id
            session_id = session.id

            def _orchestrator_fn(orchestrator_run: AgentRun) -> None:
                run_ids.append(orchestrator_run.id)
                self.with_llm_call(
                    {
                        "runId": orchestrator_run.id,
                        "sessionId": session.id,
                        "stepName": "Plan",
                        "payloadSummary": {"model": "test-model", "purpose": "plan"},
                    },
                    lambda: None,
                )
                self.with_workflow_step(
                    {
                        "runId": orchestrator_run.id,
                        "sessionId": session.id,
                        "stepName": "Validate inputs",
                        "stepIndex": 0,
                    },
                    lambda: None,
                )
                self.with_tool(
                    {
                        "runId": orchestrator_run.id,
                        "tool": {"name": "test_tool", "provider": "apie", "riskLevel": "low"},
                        "action": {"type": "read", "name": "test_tool"},
                        "resource": {"type": "test_resource", "provider": "apie"},
                        "guard": False,
                    },
                    lambda: {"ok": True},
                )
                self.with_guard(
                    {
                        "runId": orchestrator_run.id,
                        "action": {"type": "execute", "name": "deploy_pipeline"},
                        "resource": {
                            "type": "deployment_event",
                            "provider": "internal_ops",
                            "environment": "production",
                        },
                        "tool": {
                            "name": "deploy_pipeline_tool",
                            "provider": "internal_ops",
                            "riskLevel": "high",
                        },
                        "riskLevel": "high",
                        "metadata": {"test": True, "scenario": "guardrail_evaluation"},
                    },
                    lambda: None,
                )
                self.track_handoff_requested(
                    {
                        "sessionId": session.id,
                        "sourceRunId": orchestrator_run.id,
                        "reason": "Delegate worker step",
                        "payloadSummary": {"releaseId": "rel_test", "filesChanged": 3},
                    }
                )

                def _worker_fn(worker_run: AgentRun) -> None:
                    run_ids.append(worker_run.id)
                    self.track_handoff_completed(
                        {
                            "sessionId": session.id,
                            "runId": worker_run.id,
                            "payloadSummary": {
                                "releaseId": "rel_test",
                                "status": "accepted",
                            },
                        }
                    )
                    self.with_mcp_call(
                        {
                            "runId": worker_run.id,
                            "sessionId": session.id,
                            "stepName": "Lookup",
                            "payloadSummary": {"server": "test-mcp", "tool": "lookup"},
                        },
                        lambda: None,
                    )
                    self.with_tool(
                        {
                            "runId": worker_run.id,
                            "tool": {
                                "name": "test_tool_worker",
                                "provider": "apie",
                                "riskLevel": "low",
                            },
                            "action": {"type": "read", "name": "test_tool_worker"},
                            "resource": {"type": "test_resource", "provider": "apie"},
                            "guard": False,
                        },
                        lambda: {"ok": True},
                    )

                self.with_child_run(
                    {
                        "sessionId": session.id,
                        "parentRunId": orchestrator_run.id,
                        "stepName": "Worker",
                        "stepIndex": 1,
                        "role": "worker",
                        "inputSummary": "Worker step",
                    },
                    _worker_fn,
                )

            self.with_run(
                {
                    "sessionId": session.id,
                    "stepName": "Orchestrator",
                    "stepIndex": 0,
                    "inputSummary": "Orchestrator step",
                },
                _orchestrator_fn,
            )

        self.with_session(
            {
                "kind": "pipeline",
                "inputSummary": "Apie SDK pipeline test",
                "metadata": {"test": True},
            },
            _session_fn,
        )
        return SendTestEventResult(session_id=session_id, run_ids=run_ids, mode="pipeline")

    def flush(self) -> None:
        if not self._is_enabled():
            return
        self._queue.flush()

    def guard(self, input: Optional[dict[str, Any]] = None) -> GuardDecision:
        input = input or {}
        if not input.get("action") or not input.get("resource"):
            return GuardDecision(type="allow")
        return self._evaluate_guard_decision(input)

    def create_boundary_report(self, input: Optional[BoundaryReportCreateInput] = None) -> Any:
        if not self._is_enabled():
            return {"report_id": "disabled_report", "status": "disabled", "web_url": ""}
        registration = self.ready()
        return create_report(self._http, registration.agent_id, input)

    def enable_guardrail_template(self, key: str) -> dict[str, str]:
        if not self._is_enabled():
            return {"id": "disabled", "key": key, "status": "disabled"}
        self.ready()
        return self._http.post(f"/v1/guardrails/templates/{key}/enable", {})

    def shutdown(self) -> None:
        self._queue.stop()
        if self._is_enabled():
            self.flush()
        self._http.close()

    def queue_diagnostics(self) -> EventQueueDiagnostics:
        return self._queue.get_diagnostics()

    def validate_events(self, events: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        if not self._is_enabled():
            return {"accepted": 0, "previews": []}
        self.ready()
        batch = events if isinstance(events, list) else [events]
        return validate_events(self._http, batch)

    def doctor(self) -> dict[str, Any]:
        enabled = self._is_enabled()
        registration = self.ready() if enabled else None
        return {
            "registration": registration,
            "enabled": enabled,
            "releaseMode": self._config.release_mode,
            "guardFailureMode": self._config.guard_failure_mode,
            "baseUrl": self._config.base_url,
            "apiKeyConfigured": bool(self._config.api_key),
            "runtimeEnvironment": self._config.runtime.environment,
            "runtimeFramework": self._config.runtime.framework,
            "queueStoragePath": self._config.queue_storage_path,
            "redactionEnabled": bool(
                self._config.redact or self._config.redact_keys or self._config.redact_deny_patterns
            ),
            "queue": self._queue.get_diagnostics(),
        }


@dataclass(slots=True)
class _AsyncRunsProxy:
    apie: "AsyncApie"

    async def start(
        self,
        *,
        input_summary: Optional[str] = None,
        environment: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentRun:
        return await self.apie.start_run(
            input_summary=input_summary,
            environment=environment,
            metadata=metadata,
        )

    async def complete(
        self,
        run_id: str,
        *,
        status: str = "completed",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        await self.apie.complete_run(run_id, status=status, metadata=metadata)


@dataclass(slots=True)
class _AsyncCapabilitiesProxy:
    apie: "AsyncApie"

    async def declare(self, capabilities: list[DeclaredCapabilityInput]) -> dict[str, Any]:
        return await self.apie.declare_capabilities(capabilities)


@dataclass(slots=True)
class _AsyncToolsProxy:
    apie: "AsyncApie"

    async def define(self, tool: ToolDefinitionInput) -> dict[str, Any]:
        return await self.apie.define_tool(tool)


@dataclass(slots=True)
class _AsyncApprovalsProxy:
    apie: "AsyncApie"

    async def wait(
        self,
        approval_id: str,
        *,
        timeout_ms: Optional[int] = None,
        poll_interval_ms: Optional[int] = None,
    ) -> str:
        return await async_wait_for_approval(
            self.apie._http,
            approval_id,
            timeout_ms=timeout_ms or self.apie._config.approval_timeout_ms,
            poll_interval_ms=poll_interval_ms or 2000,
        )

    async def get_status(self, approval_id: str) -> dict[str, str]:
        return await async_get_approval_status(self.apie._http, approval_id)


@dataclass(slots=True)
class _AsyncReportsProxy:
    apie: "AsyncApie"

    async def create(self, input: Optional[BoundaryReportCreateInput] = None) -> Any:
        return await self.apie.create_boundary_report(input)

    async def get(self, report_id: str) -> dict[str, Any]:
        return await async_get_report(self.apie._http, report_id)

    async def wait_until_ready(
        self,
        report_id: str,
        *,
        timeout_ms: int = 30000,
        poll_interval_ms: int = 1000,
    ) -> dict[str, Any]:
        return await async_wait_until_report_ready(
            self.apie._http,
            report_id,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )


class AsyncApie:
    def __init__(self, config: Optional[ApieConfig | dict[str, Any]] = None) -> None:
        if config is None:
            raise ValueError(
                "AsyncApie requires config. Pass options or create apie.config.py/json."
            )
        self._config = resolve_config(config)
        if not self._config.agent.key or not self._config.agent.name:
            raise ValueError("agent.key and agent.name are required")
        if not self._config.api_key:
            raise ValueError("APIE_API_KEY is required")

        self._http = AsyncHttpClient(
            AsyncApieClientOptions(
                base_url=self._config.base_url or "",
                api_key=self._config.api_key,
                timeout=self._config.timeout,
                headers={str(k): str(v) for k, v in self._config.headers.items()},
            )
        )
        self._queue = AsyncEventQueue(
            self._http,
            flush_interval_ms=self._config.flush_interval_ms,
            max_batch_size=self._config.max_batch_size,
            max_queue_size=self._config.max_queue_size,
            retry_attempts=self._config.retry_attempts,
            retry_base_delay_ms=self._config.retry_base_delay_ms,
            drop_policy=self._config.queue_drop_policy,
            durable_storage_path=self._config.queue_storage_path,
            idempotency_key=self._config.queue_idempotency_key,
            on_error=self._handle_queue_error,
            transform=self._prepare_event,
        )
        self._registration: Optional[RegisterResponse] = None
        self._registration_error: Optional[Exception] = None
        self._registration_task: Optional[asyncio.Task[RegisterResponse]] = None
        self._run_sequences: dict[str, int] = {}
        self._session_sequences: dict[str, int] = {}
        self._active_session_id: Optional[str] = None
        self._disabled_session_counter = 0
        self._disabled_run_counter = 0

        self.runs = _AsyncRunsProxy(self)
        self.capabilities = _AsyncCapabilitiesProxy(self)
        self.tools = _AsyncToolsProxy(self)
        self.approvals = _AsyncApprovalsProxy(self)
        self.reports = _AsyncReportsProxy(self)
        if self._is_enabled():
            self._queue.start()
            self._start_registration_task()

    @classmethod
    async def create(cls, config: Optional[ApieConfig | dict[str, Any]] = None) -> "AsyncApie":
        loaded = load_apie_module()
        if loaded is not None and is_apie_client(loaded):
            return loaded
        resolved = resolve_config(config, loaded)
        return cls(resolved)

    @classmethod
    async def from_config(cls, config: Optional[ApieConfig | dict[str, Any]] = None) -> "AsyncApie":
        return await cls.create(config)

    def _is_enabled(self) -> bool:
        return self._config.enabled is not False

    def _disabled_registration(self) -> RegisterResponse:
        return RegisterResponse(
            agent_id=f"disabled_agent_{self._config.agent.key}",
            agent_version_id="disabled_version",
            workspace_id="disabled_workspace",
            config_hash="disabled",
            status="registered",
            created=False,
            version_created=False,
            ingest_url=self._config.base_url or "",
            recommended_next_step="Enable Apie to send telemetry.",
            dashboard_url=self._config.base_url or "",
        )

    def _create_disabled_run(self, session_id: Optional[str] = None) -> AgentRun:
        self._disabled_run_counter += 1
        return AgentRun(
            id=f"disabled_run_{self._disabled_run_counter}",
            session_id=session_id,
            status="completed",
            started_at=_now_iso(),
        )

    def _create_disabled_session(self) -> ApieSession:
        self._disabled_session_counter += 1
        return ApieSession(
            id=f"disabled_session_{self._disabled_session_counter}",
            status="completed",
            started_at=_now_iso(),
        )

    def _handle_queue_error(self, error: Exception) -> None:
        if self._config.on_error == "silent":
            return
        if self._config.on_error == "throw":
            raise error
        print(f"[apie] Event flush failed: {error}")

    def _next_sequence(self, run_id: Optional[str]) -> Optional[int]:
        if not run_id:
            return None
        next_value = self._run_sequences.get(run_id, 0) + 1
        self._run_sequences[run_id] = next_value
        return next_value

    def _next_session_sequence(self, session_id: Optional[str]) -> Optional[int]:
        current = session_id or self._active_session_id
        if not current:
            return None
        next_value = self._session_sequences.get(current, 0) + 1
        self._session_sequences[current] = next_value
        return next_value

    async def _event_context(
        self, run_id: Optional[str] = None, session_id: Optional[str] = None
    ) -> dict[str, Any]:
        resolved_session_id = session_id or self._active_session_id
        if not self._is_enabled():
            return {
                "agentId": None,
                "agentVersionId": None,
                "sessionId": resolved_session_id,
                "runId": run_id,
                "sequenceNumber": self._next_sequence(run_id),
                "sessionSequenceNumber": self._next_session_sequence(resolved_session_id),
                "environment": self._config.runtime.environment,
            }
        registration = await self.ready()
        return {
            "agentId": registration.agent_id,
            "agentVersionId": registration.agent_version_id,
            "sessionId": resolved_session_id,
            "runId": run_id,
            "sequenceNumber": self._next_sequence(run_id),
            "sessionSequenceNumber": self._next_session_sequence(resolved_session_id),
            "environment": self._config.runtime.environment,
        }

    def _prepare_event(self, event: dict[str, Any]) -> dict[str, Any]:
        return redact_event(
            event,
            redact=self._config.redact,
            redact_keys=self._config.redact_keys,
            redact_allow_paths=self._config.redact_allow_paths,
            redact_deny_patterns=self._config.redact_deny_patterns,
            max_payload_bytes=self._config.max_event_payload_bytes,
        )

    def _enqueue(self, event: dict[str, Any]) -> None:
        if self._is_enabled():
            self._queue.enqueue(event)

    def _start_registration_task(self) -> None:
        if self._registration is not None or self._registration_task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._registration_task = loop.create_task(self.identify())

    async def identify(self) -> RegisterResponse:
        if not self._is_enabled():
            self._registration = self._disabled_registration()
            self._registration_error = None
            return self._registration
        try:
            result = await async_identify_agent(self._http, self._config)
            self._registration = result
            self._registration_error = None
            if self._config.capabilities:
                try:
                    await async_declare_capabilities(
                        self._http, result.agent_id, self._config.capabilities
                    )
                except Exception as error:
                    self._handle_queue_error(error)
            return result
        except Exception as error:
            self._registration_error = error
            raise

    async def ready(self) -> RegisterResponse:
        if not self._is_enabled():
            if self._registration is None:
                self._registration = self._disabled_registration()
            return self._registration
        if self._registration is not None:
            return self._registration
        if self._registration_task is not None:
            try:
                result = await self._registration_task
                self._registration = result
                return result
            finally:
                self._registration_task = None
        if self._registration_error is not None:
            raise self._registration_error
        return await self.identify()

    async def declare_capabilities(
        self, capabilities: list[DeclaredCapabilityInput]
    ) -> dict[str, Any]:
        registration = await self.ready()
        return await async_declare_capabilities(self._http, registration.agent_id, capabilities)

    async def define_tool(self, tool: ToolDefinitionInput) -> dict[str, Any]:
        registration = await self.ready()
        return await async_define_tool(self._http, registration.agent_id, tool)

    async def start_run(
        self,
        *,
        input_summary: Optional[str] = None,
        input: Optional[dict[str, Any]] = None,
        environment: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentRun:
        if not self._is_enabled():
            return self._create_disabled_run()
        registration = await self.ready()
        merged_metadata = {**(metadata or {})}
        if input is not None:
            merged_metadata["input"] = input
        return await async_create_run(
            self._http,
            agent_key=self._config.agent.key,
            agent_id=registration.agent_id,
            agent_version_id=registration.agent_version_id,
            environment=environment or self._config.runtime.environment,
            input_summary=input_summary,
            metadata=merged_metadata or None,
        )

    async def complete_run(
        self,
        run_id: str,
        *,
        status: str = "completed",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if not self._is_enabled():
            return
        await self.flush()
        await async_complete_run(self._http, run_id, status=status, metadata=metadata)
        self._run_sequences.pop(run_id, None)

    @asynccontextmanager
    async def run_context(
        self,
        *,
        session_id: Optional[str] = None,
        input_summary: Optional[str] = None,
        environment: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        step_name: Optional[str] = None,
        step_key: Optional[str] = None,
        step_index: Optional[int] = None,
    ):
        if session_id:
            registration = await self.ready()
            run = await async_create_child_run(
                self._http,
                session_id,
                agent_key=self._config.agent.key,
                agent_id=registration.agent_id,
                agent_version_id=registration.agent_version_id,
                environment=environment or self._config.runtime.environment,
                input_summary=input_summary,
                metadata=metadata,
                step_name=step_name,
                step_key=step_key,
                step_index=step_index,
            )
        else:
            run = await self.start_run(
                input_summary=input_summary,
                environment=environment,
                metadata=metadata,
            )

        previous = self._active_session_id
        self._active_session_id = session_id or run.session_id
        try:
            yield run
            await self.complete_run(run.id, status="completed")
        except Exception as error:
            await self.capture_error(error, run_id=run.id, session_id=session_id or run.session_id)
            await self.complete_run(run.id, status="failed")
            raise
        finally:
            self._active_session_id = previous
            await self.flush()

    async def with_run(self, input: dict[str, Any], fn: Callable[[AgentRun], Awaitable[T]]) -> T:
        if not self._is_enabled():
            return await fn(self._create_disabled_run(input.get("sessionId")))
        async with self.run_context(
            session_id=input.get("sessionId"),
            input_summary=input.get("inputSummary"),
            environment=input.get("environment"),
            metadata=input.get("metadata"),
            step_name=input.get("stepName"),
            step_key=input.get("stepKey"),
            step_index=input.get("stepIndex"),
        ) as run:
            return await fn(run)

    @asynccontextmanager
    async def session_context(
        self,
        *,
        kind: str = "single_agent",
        input_summary: Optional[str] = None,
        environment: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        if not self._is_enabled():
            session = self._create_disabled_session()
            yield session
            return

        registration = await self.ready()
        session = await async_create_session(
            self._http,
            kind=kind,  # type: ignore[arg-type]
            orchestrator_agent_key=self._config.agent.key,
            orchestrator_agent_id=registration.agent_id,
            environment=environment or self._config.runtime.environment,
            input_summary=input_summary,
            metadata=metadata,
        )
        previous = self._active_session_id
        self._active_session_id = session.id
        try:
            yield session
            await async_complete_session(self._http, session.id, status="completed")
        except Exception as error:
            await self.capture_error(error, session_id=session.id)
            await async_complete_session(self._http, session.id, status="failed")
            raise
        finally:
            self._active_session_id = previous
            self._session_sequences.pop(session.id, None)
            await self.flush()

    async def with_session(
        self,
        input: dict[str, Any],
        fn: Callable[[ApieSession], Awaitable[T]],
    ) -> T:
        async with self.session_context(
            kind=input.get("kind", "single_agent"),
            input_summary=input.get("inputSummary"),
            environment=input.get("environment"),
            metadata=input.get("metadata"),
        ) as session:
            return await fn(session)

    async def with_child_run(
        self,
        input: dict[str, Any],
        fn: Callable[[AgentRun], Awaitable[T]],
    ) -> T:
        if not self._is_enabled():
            return await fn(self._create_disabled_run(input.get("sessionId")))
        session_id = input["sessionId"]
        previous = self._active_session_id
        self._active_session_id = session_id
        try:
            registration = await self.ready()
            run = await async_create_child_run(
                self._http,
                session_id,
                agent_key=input.get("agentKey") or self._config.agent.key,
                agent_id=None if input.get("agentKey") else registration.agent_id,
                agent_version_id=(None if input.get("agentKey") else registration.agent_version_id),
                parent_run_id=input.get("parentRunId"),
                step_name=input.get("stepName"),
                step_key=input.get("stepKey"),
                step_index=input.get("stepIndex"),
                role=input.get("role"),
                input_summary=input.get("inputSummary"),
                metadata={
                    **(input.get("metadata") or {}),
                    "payload_summary": input.get("payloadSummary"),
                },
            )
            try:
                result = await fn(run)
                await self.complete_run(run.id, status="completed")
                return result
            except Exception as error:
                await self.capture_error(error, run_id=run.id, session_id=session_id)
                await self.complete_run(run.id, status="failed")
                raise
            finally:
                await self.flush()
        finally:
            self._active_session_id = previous

    async def track_handoff_requested(self, input: dict[str, Any]) -> None:
        registration = await self.ready()
        await async_record_handoff(
            self._http,
            input["sessionId"],
            source_run_id=input.get("sourceRunId"),
            source_agent_id=registration.agent_id,
            target_run_id=input.get("targetRunId"),
            target_agent_id=input.get("targetAgentId"),
            reason=input.get("reason"),
            input_summary=input.get("inputSummary"),
            payload_summary=input.get("payloadSummary"),
            status="requested",
        )
        ctx = await self._event_context(input.get("sourceRunId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.handoff.requested",
                self._config.agent.key,
                {
                    **ctx,
                    "payloadSummary": input.get("payloadSummary"),
                    "metadata": {
                        "reason": input.get("reason"),
                        "target_run_id": input.get("targetRunId"),
                        "target_agent_id": input.get("targetAgentId"),
                    },
                },
            )
        )

    async def track_handoff_completed(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.handoff.completed",
                self._config.agent.key,
                {**ctx, "payloadSummary": input.get("payloadSummary")},
            )
        )

    async def track_handoff_failed(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.handoff.failed",
                self._config.agent.key,
                {
                    **ctx,
                    "payloadSummary": input.get("payloadSummary"),
                    "error": input.get("error"),
                },
            )
        )

    async def with_workflow_step(self, input: dict[str, Any], fn: Callable[[], Awaitable[T]]) -> T:
        ctx = await self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.workflow.step.started",
                self._config.agent.key,
                {
                    **ctx,
                    "stepKey": input.get("stepKey"),
                    "stepName": input.get("stepName"),
                    "stepIndex": input.get("stepIndex"),
                    "payloadSummary": input.get("payloadSummary"),
                },
            )
        )
        try:
            result = await fn()
            done = await self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.workflow.step.completed",
                    self._config.agent.key,
                    {
                        **done,
                        "stepKey": input.get("stepKey"),
                        "stepName": input.get("stepName"),
                        "stepIndex": input.get("stepIndex"),
                    },
                )
            )
            return result
        except Exception as error:
            fail = await self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.workflow.step.failed",
                    self._config.agent.key,
                    {
                        **fail,
                        "stepKey": input.get("stepKey"),
                        "stepName": input.get("stepName"),
                        "stepIndex": input.get("stepIndex"),
                        "error": {"message": str(error)},
                    },
                )
            )
            raise

    async def with_llm_call(self, input: dict[str, Any], fn: Callable[[], Awaitable[T]]) -> T:
        ctx = await self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.llm.called",
                self._config.agent.key,
                {
                    **ctx,
                    "stepName": input.get("stepName"),
                    "eventCategory": "llm",
                    "payloadSummary": input.get("payloadSummary"),
                },
            )
        )
        try:
            result = await fn()
            done = await self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.llm.completed",
                    self._config.agent.key,
                    {**done, "stepName": input.get("stepName")},
                )
            )
            return result
        except Exception as error:
            fail = await self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.llm.failed",
                    self._config.agent.key,
                    {
                        **fail,
                        "stepName": input.get("stepName"),
                        "error": {"message": str(error)},
                    },
                )
            )
            raise

    async def with_mcp_call(self, input: dict[str, Any], fn: Callable[[], Awaitable[T]]) -> T:
        ctx = await self._event_context(input.get("runId"), input.get("sessionId"))
        self._enqueue(
            build_workflow_event(
                "agent.mcp.called",
                self._config.agent.key,
                {
                    **ctx,
                    "stepName": input.get("stepName"),
                    "eventCategory": "mcp",
                    "payloadSummary": input.get("payloadSummary"),
                },
            )
        )
        try:
            result = await fn()
            done = await self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.mcp.completed",
                    self._config.agent.key,
                    {**done, "stepName": input.get("stepName")},
                )
            )
            return result
        except Exception as error:
            fail = await self._event_context(input.get("runId"), input.get("sessionId"))
            self._enqueue(
                build_workflow_event(
                    "agent.mcp.failed",
                    self._config.agent.key,
                    {
                        **fail,
                        "stepName": input.get("stepName"),
                        "error": {"message": str(error)},
                    },
                )
            )
            raise

    async def track_tool_call(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"))
        self._enqueue(build_tool_call_event(self._config.agent.key, {**ctx, **input}))

    async def track_action_requested(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"))
        self._enqueue(build_action_requested_event(self._config.agent.key, {**ctx, **input}))

    async def track_action_completed(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"))
        self._enqueue(build_action_completed_event(self._config.agent.key, {**ctx, **input}))

    async def track_action_failed(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"))
        self._enqueue(build_action_failed_event(self._config.agent.key, {**ctx, **input}))

    async def track_resource_touched(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"))
        self._enqueue(build_resource_touched_event(self._config.agent.key, {**ctx, **input}))

    async def track_approval_requested(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"))
        self._enqueue(build_approval_requested_event(self._config.agent.key, {**ctx, **input}))

    async def track_approval_resolved(self, input: dict[str, Any]) -> None:
        ctx = await self._event_context(input.get("runId"))
        self._enqueue(build_approval_resolved_event(self._config.agent.key, {**ctx, **input}))

    async def track(self, event: dict[str, Any]) -> None:
        registration = await self.ready()
        self._enqueue(
            {
                "type": event.get("type"),
                "agentKey": self._config.agent.key,
                "agentId": registration.agent_id,
                "agentVersionId": registration.agent_version_id,
                "runId": event.get("runId"),
                "sequenceNumber": self._next_sequence(event.get("runId")),
                "timestamp": _now_iso(),
                "metadata": event.get("payload"),
            }
        )

    async def capture_error(
        self,
        error: Any,
        *,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        ctx = await self._event_context(run_id, session_id)
        self._enqueue(
            build_error_event(self._config.agent.key, error, {**ctx, "metadata": metadata})
        )

    def _is_enforce_mode(self) -> bool:
        return self._config.release_mode == "guard"

    def _guard_mode(self) -> str:
        return "enforce" if self._is_enforce_mode() else "monitor"

    async def _evaluate_guard_decision(self, input: dict[str, Any]) -> GuardDecision:
        if not self._is_enabled():
            return GuardDecision(type="allow")
        try:
            raw = await async_evaluate_guard(
                self._http,
                agent_key=self._config.agent.key,
                run_id=input.get("runId"),
                mode=self._guard_mode(),  # type: ignore[arg-type]
                risk_level=input.get("riskLevel"),
                action=input["action"],
                resource=input["resource"],
                tool=_to_tool_dict(input.get("tool")),
                metadata=input.get("metadata"),
                redact=self._config.redact,
                redact_keys=self._config.redact_keys,
            )
            if not self._is_enforce_mode():
                if raw.type in {"block", "require_approval"} and raw.reason:
                    print(
                        "[apie] Would "
                        + ("block" if raw.type == "block" else "require approval")
                        + f" in enforcement mode: {raw.reason}"
                    )
                if raw.type == "warn" and raw.reason:
                    print(f"[apie] Guardrail warning: {raw.reason}")
                monitor_type = raw.type
                effective = "warn" if raw.type == "warn" else "allow"
                return GuardDecision(
                    type=effective,  # type: ignore[arg-type]
                    reason=raw.reason,
                    decision_id=raw.decision_id,
                    approval_id=raw.approval_id,
                    receipt_id=raw.receipt_id,
                    monitor_decision=monitor_type,
                    matched_guardrails=raw.matched_guardrails,
                )
            return raw
        except Exception as error:
            if self._config.guard_failure_mode == "fail_closed":
                return GuardDecision(type="block", reason=str(error))
            if self._config.guard_failure_mode == "throw":
                raise
            self._handle_queue_error(error)
            return GuardDecision(type="allow")

    async def _enforce_guard_decision(self, input: dict[str, Any], decision: GuardDecision) -> None:
        ctx = await self._event_context(input.get("runId"))
        self._enqueue(
            build_guardrail_evaluated_event(
                self._config.agent.key,
                {
                    **ctx,
                    "decision": decision.monitor_decision or decision.type,
                    "reason": decision.reason,
                    "action": input.get("action"),
                    "resource": input.get("resource"),
                },
            )
        )
        if decision.type == "block":
            raise RuntimeError(decision.reason or "Action blocked by guardrail")
        if decision.type == "warn" and decision.reason:
            print(f"[apie] Guardrail warning: {decision.reason}")
        if decision.type == "require_approval" and decision.approval_id:
            await self.track_approval_requested(
                {
                    "runId": input.get("runId"),
                    "approvalId": decision.approval_id,
                    "action": input.get("action"),
                    "resource": input.get("resource"),
                    "reason": decision.reason,
                }
            )
            await self.flush()
            status = await self.approvals.wait(
                decision.approval_id,
                timeout_ms=self._config.approval_timeout_ms,
            )
            await self.track_approval_resolved(
                {
                    "runId": input.get("runId"),
                    "approvalId": decision.approval_id,
                    "status": status,
                }
            )
            if status != "approved":
                raise RuntimeError(f"Action not approved: {status}")

    async def with_guard(self, input: dict[str, Any], fn: Callable[[], Awaitable[T]]) -> T:
        decision = await self._evaluate_guard_decision(input)
        await self._enforce_guard_decision(input, decision)
        await self.track_action_requested(
            {
                "runId": input.get("runId"),
                "action": input.get("action"),
                "resource": input.get("resource"),
                "tool": input.get("tool"),
                "metadata": input.get("metadata"),
                "riskLevel": input.get("riskLevel"),
            }
        )
        try:
            result = await fn()
            await self.track_action_completed(
                {
                    "runId": input.get("runId"),
                    "action": input.get("action"),
                    "resource": input.get("resource"),
                    "tool": input.get("tool"),
                    "metadata": input.get("metadata"),
                    "result": {"status": "executed"},
                }
            )
            return result
        except Exception as error:
            await self.track_action_failed(
                {
                    "runId": input.get("runId"),
                    "action": input.get("action"),
                    "resource": input.get("resource"),
                    "tool": input.get("tool"),
                    "error": {"message": str(error)},
                    "metadata": input.get("metadata"),
                }
            )
            await self.capture_error(error, run_id=input.get("runId"))
            await self.flush()
            raise

    async def with_tool(self, input: dict[str, Any], fn: Callable[[], Awaitable[T]]) -> T:
        should_evaluate = input.get("guard", True) is not False
        action = input.get("action") or {"type": "execute", "name": input["tool"]["name"]}
        resource = input.get("resource") or {"type": "unknown"}
        if should_evaluate:
            decision = await self._evaluate_guard_decision(
                {
                    "runId": input.get("runId"),
                    "action": action,
                    "resource": resource,
                    "tool": input.get("tool"),
                    "metadata": input.get("metadata"),
                    "riskLevel": (input.get("tool") or {}).get("riskLevel"),
                }
            )
            await self._enforce_guard_decision(
                {
                    "runId": input.get("runId"),
                    "action": action,
                    "resource": resource,
                    "tool": input.get("tool"),
                },
                decision,
            )
        await self.track_tool_call(input)
        await self.track_action_requested(
            {
                "runId": input.get("runId"),
                "action": action,
                "resource": resource,
                "tool": input.get("tool"),
                "metadata": input.get("metadata"),
            }
        )
        try:
            result = await fn()
            await self.track_action_completed(
                {
                    "runId": input.get("runId"),
                    "action": action,
                    "resource": resource,
                    "tool": input.get("tool"),
                    "metadata": input.get("metadata"),
                }
            )
            return result
        except Exception as error:
            await self.track_action_failed(
                {
                    "runId": input.get("runId"),
                    "action": action,
                    "resource": resource,
                    "tool": input.get("tool"),
                    "error": {"message": str(error)},
                    "metadata": input.get("metadata"),
                }
            )
            await self.capture_error(error, run_id=input.get("runId"))
            await self.flush()
            raise

    async def send_test_event(
        self, options: Optional[dict[str, Any]] = None
    ) -> SendTestEventResult:
        mode = (options or {}).get("mode", "pipeline")
        if mode == "single":
            return await self._send_single_test_event()
        return await self._send_pipeline_test_event()

    async def _send_single_test_event(self) -> SendTestEventResult:
        session_id = ""
        run_ids: list[str] = []

        async def _session_fn(session: ApieSession) -> None:
            nonlocal session_id
            session_id = session.id

            async def _run_fn(run: AgentRun) -> None:
                run_ids.append(run.id)
                await self.with_tool(
                    {
                        "runId": run.id,
                        "tool": {"name": "test_tool", "provider": "apie", "riskLevel": "low"},
                        "action": {"type": "read", "name": "test_tool"},
                        "resource": {"type": "test_resource", "provider": "apie"},
                        "guard": False,
                    },
                    lambda: asyncio.sleep(0, result={"ok": True}),
                )

            await self.with_run(
                {"sessionId": session.id, "inputSummary": "Apie SDK test run"},
                _run_fn,
            )

        await self.with_session(
            {
                "kind": "single_agent",
                "inputSummary": "Apie SDK test run",
                "metadata": {"test": True},
            },
            _session_fn,
        )
        return SendTestEventResult(session_id=session_id, run_ids=run_ids, mode="single")

    async def _send_pipeline_test_event(self) -> SendTestEventResult:
        session_id = ""
        run_ids: list[str] = []

        async def _session_fn(session: ApieSession) -> None:
            nonlocal session_id
            session_id = session.id

            async def _orchestrator_fn(orchestrator_run: AgentRun) -> None:
                run_ids.append(orchestrator_run.id)
                await self.with_llm_call(
                    {
                        "runId": orchestrator_run.id,
                        "sessionId": session.id,
                        "stepName": "Plan",
                        "payloadSummary": {"model": "test-model", "purpose": "plan"},
                    },
                    lambda: asyncio.sleep(0),
                )
                await self.with_workflow_step(
                    {
                        "runId": orchestrator_run.id,
                        "sessionId": session.id,
                        "stepName": "Validate inputs",
                        "stepIndex": 0,
                    },
                    lambda: asyncio.sleep(0),
                )
                await self.with_tool(
                    {
                        "runId": orchestrator_run.id,
                        "tool": {"name": "test_tool", "provider": "apie", "riskLevel": "low"},
                        "action": {"type": "read", "name": "test_tool"},
                        "resource": {"type": "test_resource", "provider": "apie"},
                        "guard": False,
                    },
                    lambda: asyncio.sleep(0, result={"ok": True}),
                )
                await self.with_guard(
                    {
                        "runId": orchestrator_run.id,
                        "action": {"type": "execute", "name": "deploy_pipeline"},
                        "resource": {
                            "type": "deployment_event",
                            "provider": "internal_ops",
                            "environment": "production",
                        },
                        "tool": {
                            "name": "deploy_pipeline_tool",
                            "provider": "internal_ops",
                            "riskLevel": "high",
                        },
                        "riskLevel": "high",
                        "metadata": {"test": True, "scenario": "guardrail_evaluation"},
                    },
                    lambda: asyncio.sleep(0),
                )
                await self.track_handoff_requested(
                    {
                        "sessionId": session.id,
                        "sourceRunId": orchestrator_run.id,
                        "reason": "Delegate worker step",
                        "payloadSummary": {"releaseId": "rel_test", "filesChanged": 3},
                    }
                )

                async def _worker_fn(worker_run: AgentRun) -> None:
                    run_ids.append(worker_run.id)
                    await self.track_handoff_completed(
                        {
                            "sessionId": session.id,
                            "runId": worker_run.id,
                            "payloadSummary": {
                                "releaseId": "rel_test",
                                "status": "accepted",
                            },
                        }
                    )
                    await self.with_mcp_call(
                        {
                            "runId": worker_run.id,
                            "sessionId": session.id,
                            "stepName": "Lookup",
                            "payloadSummary": {"server": "test-mcp", "tool": "lookup"},
                        },
                        lambda: asyncio.sleep(0),
                    )
                    await self.with_tool(
                        {
                            "runId": worker_run.id,
                            "tool": {
                                "name": "test_tool_worker",
                                "provider": "apie",
                                "riskLevel": "low",
                            },
                            "action": {"type": "read", "name": "test_tool_worker"},
                            "resource": {"type": "test_resource", "provider": "apie"},
                            "guard": False,
                        },
                        lambda: asyncio.sleep(0, result={"ok": True}),
                    )

                await self.with_child_run(
                    {
                        "sessionId": session.id,
                        "parentRunId": orchestrator_run.id,
                        "stepName": "Worker",
                        "stepIndex": 1,
                        "role": "worker",
                        "inputSummary": "Worker step",
                    },
                    _worker_fn,
                )

            await self.with_run(
                {
                    "sessionId": session.id,
                    "stepName": "Orchestrator",
                    "stepIndex": 0,
                    "inputSummary": "Orchestrator step",
                },
                _orchestrator_fn,
            )

        await self.with_session(
            {
                "kind": "pipeline",
                "inputSummary": "Apie SDK pipeline test",
                "metadata": {"test": True},
            },
            _session_fn,
        )
        return SendTestEventResult(session_id=session_id, run_ids=run_ids, mode="pipeline")

    async def flush(self) -> None:
        if self._is_enabled():
            await self._queue.flush()

    async def guard(self, input: Optional[dict[str, Any]] = None) -> GuardDecision:
        input = input or {}
        if not input.get("action") or not input.get("resource"):
            return GuardDecision(type="allow")
        return await self._evaluate_guard_decision(input)

    async def create_boundary_report(
        self, input: Optional[BoundaryReportCreateInput] = None
    ) -> Any:
        if not self._is_enabled():
            return {"report_id": "disabled_report", "status": "disabled", "web_url": ""}
        registration = await self.ready()
        return await async_create_report(self._http, registration.agent_id, input)

    async def enable_guardrail_template(self, key: str) -> dict[str, str]:
        if not self._is_enabled():
            return {"id": "disabled", "key": key, "status": "disabled"}
        await self.ready()
        return await self._http.post(f"/v1/guardrails/templates/{key}/enable", {})

    async def shutdown(self) -> None:
        await self._queue.stop()
        if self._is_enabled():
            await self.flush()
        await self._http.aclose()

    def queue_diagnostics(self) -> EventQueueDiagnostics:
        return self._queue.get_diagnostics()

    async def validate_events(
        self, events: dict[str, Any] | list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not self._is_enabled():
            return {"accepted": 0, "previews": []}
        await self.ready()
        batch = events if isinstance(events, list) else [events]
        return await async_validate_events(self._http, batch)

    async def doctor(self) -> dict[str, Any]:
        enabled = self._is_enabled()
        registration = await self.ready() if enabled else None
        return {
            "registration": registration,
            "enabled": enabled,
            "releaseMode": self._config.release_mode,
            "guardFailureMode": self._config.guard_failure_mode,
            "baseUrl": self._config.base_url,
            "apiKeyConfigured": bool(self._config.api_key),
            "runtimeEnvironment": self._config.runtime.environment,
            "runtimeFramework": self._config.runtime.framework,
            "queueStoragePath": self._config.queue_storage_path,
            "redactionEnabled": bool(
                self._config.redact or self._config.redact_keys or self._config.redact_deny_patterns
            ),
            "queue": self._queue.get_diagnostics(),
        }


def create_apie(config: Optional[ApieConfig | dict[str, Any]] = None) -> Apie:
    return Apie.create(config)


async def create_async_apie(
    config: Optional[ApieConfig | dict[str, Any]] = None,
) -> AsyncApie:
    return await AsyncApie.create(config)
