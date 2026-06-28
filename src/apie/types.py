from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Literal, Optional, TypedDict

JsonDict = Dict[str, Any]
QueuedEvent = Dict[str, Any]

ReleaseMode = Literal["monitor", "guard"]
GuardMode = Literal["monitor", "enforce"]
GuardFailureMode = Literal["fail_open", "fail_closed", "throw"]
OnErrorMode = Literal["silent", "warn", "throw"]
QueueDropPolicy = Literal["drop_oldest", "drop_newest"]
SendTestEventMode = Literal["pipeline", "single"]


class ApieInfoResponse(TypedDict):
    name: str
    status: str


class HealthCheckResponse(TypedDict):
    status: Literal["ok", "error"]
    database: Literal["connected", "disconnected"]


@dataclass(slots=True)
class ApieAgentConfig:
    key: str
    name: str
    purpose: Optional[str] = None
    owner: Optional[str] = None
    team: Optional[str] = None
    description: Optional[str] = None


@dataclass(slots=True)
class ApieRuntimeConfig:
    environment: Optional[str] = None
    framework: Optional[str] = None
    language: Optional[str] = None
    sdk_version: Optional[str] = None


@dataclass(slots=True)
class ApieModelConfig:
    provider: Optional[str] = None
    name: Optional[str] = None


@dataclass(slots=True)
class ApieVersionConfig:
    version: Optional[str] = None
    framework: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None


@dataclass(slots=True)
class ApieToolConfig:
    name: str
    action_types: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    risk_level: Optional[str] = None
    provider: Optional[str] = None
    environments: list[str] = field(default_factory=list)
    description: Optional[str] = None
    input_schema: Optional[JsonDict] = None


@dataclass(slots=True)
class DeclaredCapabilityTool:
    name: str
    provider: Optional[str] = None


@dataclass(slots=True)
class DeclaredCapabilityInput:
    tool: DeclaredCapabilityTool
    actions: list[str]
    resources: list[str]
    environments: list[str] = field(default_factory=list)
    risk_level: Optional[str] = None


@dataclass(slots=True)
class ToolDefinitionInput:
    name: str
    provider: Optional[str] = None
    description: Optional[str] = None
    input_schema: Optional[JsonDict] = None
    action_types: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    risk_level: Optional[str] = None


@dataclass(slots=True)
class BoundaryConfig:
    warn_on_undeclared_tools: bool = False
    warn_on_unknown_resource_types: bool = False
    auto_infer_from_tool_names: bool = False


@dataclass(slots=True)
class ApieSourceConfig:
    git_sha: Optional[str] = None
    deployment_id: Optional[str] = None


@dataclass(slots=True)
class ApieConfig:
    agent: ApieAgentConfig
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    enabled: bool = True
    runtime: ApieRuntimeConfig = field(default_factory=ApieRuntimeConfig)
    model: ApieModelConfig = field(default_factory=ApieModelConfig)
    version: ApieVersionConfig = field(default_factory=ApieVersionConfig)
    release_mode: ReleaseMode = "monitor"
    mode: Optional[GuardMode] = None
    tools: list[ApieToolConfig] = field(default_factory=list)
    capabilities: list[DeclaredCapabilityInput] = field(default_factory=list)
    boundary: BoundaryConfig = field(default_factory=BoundaryConfig)
    source: ApieSourceConfig = field(default_factory=ApieSourceConfig)
    prompt_hash: Optional[str] = None
    guard_failure_mode: GuardFailureMode = "fail_open"
    approval_timeout_ms: int = 300_000
    flush_interval_ms: int = 2_000
    max_batch_size: int = 25
    max_queue_size: int = 5_000
    retry_attempts: int = 3
    retry_base_delay_ms: int = 250
    queue_storage_path: Optional[str] = None
    queue_drop_policy: QueueDropPolicy = "drop_oldest"
    queue_idempotency_key: Optional[Callable[[QueuedEvent], Optional[str]]] = None
    on_error: OnErrorMode = "warn"
    redact: Optional[Callable[[QueuedEvent], QueuedEvent]] = None
    redact_keys: list[str] = field(default_factory=list)
    redact_allow_paths: list[str] = field(default_factory=list)
    redact_deny_patterns: list[str] = field(default_factory=list)
    max_event_payload_bytes: Optional[int] = None
    timeout: Optional[int] = None
    headers: JsonDict = field(default_factory=dict)


@dataclass(slots=True)
class RegisterResponse:
    agent_id: str
    agent_version_id: str
    workspace_id: str
    config_hash: str
    status: Literal["registered"]
    created: bool
    version_created: bool
    ingest_url: str
    recommended_next_step: str
    dashboard_url: str


@dataclass(slots=True)
class AgentRun:
    id: str
    session_id: Optional[str] = None
    status: str = "completed"
    started_at: Optional[str] = None


@dataclass(slots=True)
class ApieSession:
    id: str
    status: str = "completed"
    started_at: Optional[str] = None


@dataclass(slots=True)
class SendTestEventOptions:
    mode: SendTestEventMode = "pipeline"


@dataclass(slots=True)
class SendTestEventResult:
    session_id: str
    run_ids: list[str]
    mode: SendTestEventMode


@dataclass(slots=True)
class GuardDecision:
    type: Literal["allow", "block", "warn", "require_approval"]
    reason: Optional[str] = None
    decision_id: Optional[str] = None
    approval_id: Optional[str] = None
    receipt_id: Optional[str] = None
    monitor_decision: Optional[Literal["allow", "block", "warn", "require_approval"]] = None
    matched_guardrails: list[JsonDict] = field(default_factory=list)


@dataclass(slots=True)
class ActionRef:
    type: str
    name: str
    risk_level: Optional[str] = None


@dataclass(slots=True)
class ResourceRef:
    type: str
    external_id: Optional[str] = None
    provider: Optional[str] = None
    environment: Optional[str] = None


@dataclass(slots=True)
class ToolRef:
    name: str
    provider: Optional[str] = None
    risk_level: Optional[str] = None


@dataclass(slots=True)
class TrackActionInput:
    action: ActionRef
    run_id: Optional[str] = None
    resource: Optional[ResourceRef] = None
    tool: Optional[ToolRef] = None
    metadata: Optional[JsonDict] = None
    risk_level: Optional[str] = None


@dataclass(slots=True)
class TrackToolCallInput:
    tool: ToolRef
    run_id: Optional[str] = None
    action: Optional[ActionRef] = None
    resource: Optional[ResourceRef] = None
    metadata: Optional[JsonDict] = None


@dataclass(slots=True)
class BoundaryReportCreateInput:
    title: Optional[str] = None
    report_type: Optional[
        Literal[
            "agent_boundary_report",
            "release_readiness_report",
            "incident_report",
            "customer_evidence_pack",
        ]
    ] = None
    window: Optional[Literal["24h", "7d", "30d"]] = None
    time_window: Optional[dict[str, str]] = None
    environments: list[str] = field(default_factory=list)
    agent_version_id: Optional[str] = None
    sections: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BoundaryReportResponse:
    report_id: str
    status: str
    web_url: str
