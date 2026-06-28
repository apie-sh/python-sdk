from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .types import (
    ApieAgentConfig,
    ApieConfig,
    ApieModelConfig,
    ApieRuntimeConfig,
    ApieSourceConfig,
    ApieToolConfig,
    ApieVersionConfig,
    BoundaryConfig,
    DeclaredCapabilityInput,
    DeclaredCapabilityTool,
    ToolDefinitionInput,
)


def is_apie_client(value: Any) -> bool:
    return (
        value is not None
        and hasattr(value, "ready")
        and hasattr(value, "flush")
        and callable(value.ready)
    )


def _load_python_config(path: Path) -> Any:
    module_name = "_apie_runtime_config"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "default"):
        return module.default
    if hasattr(module, "apie"):
        return module.apie
    if hasattr(module, "config"):
        return module.config
    if hasattr(module, "get_config") and callable(module.get_config):
        return module.get_config()
    return None


def load_apie_module(cwd: Optional[str] = None) -> Any:
    root = Path(cwd or os.getcwd())
    candidates = [
        root / "apie.config.py",
        root / "apie.config.json",
    ]
    for candidate in candidates:
        try:
            if not candidate.exists():
                continue
            if candidate.suffix == ".json":
                return json.loads(candidate.read_text(encoding="utf-8"))
            return _load_python_config(candidate)
        except Exception:
            continue
    return None


def load_apie_config(cwd: Optional[str] = None) -> Optional[ApieConfig]:
    loaded = load_apie_module(cwd=cwd)
    if loaded is None or is_apie_client(loaded):
        return None
    return coerce_config(loaded)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return {}


def _pick(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _coerce_tools(values: list[Any]) -> list[ApieToolConfig]:
    tools: list[ApieToolConfig] = []
    for raw in values:
        if isinstance(raw, ApieToolConfig):
            tools.append(raw)
            continue
        if not isinstance(raw, Mapping):
            continue
        tools.append(
            ApieToolConfig(
                name=str(_pick(raw, "name", default="")),
                action_types=list(_pick(raw, "action_types", "actionTypes", default=[]) or []),
                resource_types=list(
                    _pick(raw, "resource_types", "resourceTypes", default=[]) or []
                ),
                risk_level=_pick(raw, "risk_level", "riskLevel"),
                provider=_pick(raw, "provider"),
                environments=list(_pick(raw, "environments", default=[]) or []),
                description=_pick(raw, "description"),
                input_schema=_pick(raw, "input_schema", "inputSchema"),
            )
        )
    return [tool for tool in tools if tool.name]


def _coerce_capabilities(values: list[Any]) -> list[DeclaredCapabilityInput]:
    capabilities: list[DeclaredCapabilityInput] = []
    for raw in values:
        if isinstance(raw, DeclaredCapabilityInput):
            capabilities.append(raw)
            continue
        if not isinstance(raw, Mapping):
            continue
        tool_raw = _pick(raw, "tool", default={})
        if not isinstance(tool_raw, Mapping):
            continue
        tool_name = _pick(tool_raw, "name", default=None)
        if not tool_name:
            continue
        capabilities.append(
            DeclaredCapabilityInput(
                tool=DeclaredCapabilityTool(
                    name=str(tool_name),
                    provider=_pick(tool_raw, "provider"),
                ),
                actions=list(_pick(raw, "actions", default=[]) or []),
                resources=list(_pick(raw, "resources", default=[]) or []),
                environments=list(_pick(raw, "environments", default=[]) or []),
                risk_level=_pick(raw, "risk_level", "riskLevel"),
            )
        )
    return capabilities


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
            and result.get(key) is not None
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def coerce_config(value: Any) -> ApieConfig:
    if isinstance(value, ApieConfig):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if not isinstance(value, Mapping):
        raise TypeError("Apie config must be a mapping or ApieConfig instance")

    agent_raw = _pick(value, "agent", default={}) or {}
    if not isinstance(agent_raw, Mapping):
        agent_raw = {}

    runtime_raw = _pick(value, "runtime", default={}) or {}
    model_raw = _pick(value, "model", default={}) or {}
    version_raw = _pick(value, "version", default={}) or {}
    boundary_raw = _pick(value, "boundary", default={}) or {}
    source_raw = _pick(value, "source", default={}) or {}

    config = ApieConfig(
        api_key=_pick(value, "api_key", "apiKey"),
        base_url=_pick(value, "base_url", "baseUrl"),
        enabled=bool(_pick(value, "enabled", default=True)),
        agent=ApieAgentConfig(
            key=str(_pick(agent_raw, "key", default="")),
            name=str(_pick(agent_raw, "name", default="")),
            purpose=_pick(agent_raw, "purpose"),
            owner=_pick(agent_raw, "owner"),
            team=_pick(agent_raw, "team"),
            description=_pick(agent_raw, "description"),
        ),
        runtime=ApieRuntimeConfig(
            environment=_pick(runtime_raw, "environment"),
            framework=_pick(runtime_raw, "framework"),
            language=_pick(runtime_raw, "language"),
            sdk_version=_pick(runtime_raw, "sdk_version", "sdkVersion"),
        ),
        model=ApieModelConfig(
            provider=_pick(model_raw, "provider"),
            name=_pick(model_raw, "name"),
        ),
        version=ApieVersionConfig(
            version=_pick(version_raw, "version"),
            framework=_pick(version_raw, "framework"),
            model_provider=_pick(version_raw, "model_provider", "modelProvider"),
            model_name=_pick(version_raw, "model_name", "modelName"),
        ),
        release_mode=_pick(value, "release_mode", "releaseMode", default="monitor"),
        mode=_pick(value, "mode"),
        tools=_coerce_tools(list(_pick(value, "tools", default=[]) or [])),
        capabilities=_coerce_capabilities(list(_pick(value, "capabilities", default=[]) or [])),
        boundary=BoundaryConfig(
            warn_on_undeclared_tools=bool(
                _pick(
                    boundary_raw, "warn_on_undeclared_tools", "warnOnUndeclaredTools", default=False
                )
            ),
            warn_on_unknown_resource_types=bool(
                _pick(
                    boundary_raw,
                    "warn_on_unknown_resource_types",
                    "warnOnUnknownResourceTypes",
                    default=False,
                )
            ),
            auto_infer_from_tool_names=bool(
                _pick(
                    boundary_raw,
                    "auto_infer_from_tool_names",
                    "autoInferFromToolNames",
                    default=False,
                )
            ),
        ),
        source=ApieSourceConfig(
            git_sha=_pick(source_raw, "git_sha", "gitSha"),
            deployment_id=_pick(source_raw, "deployment_id", "deploymentId"),
        ),
        prompt_hash=_pick(value, "prompt_hash", "promptHash"),
        guard_failure_mode=_pick(
            value, "guard_failure_mode", "guardFailureMode", default="fail_open"
        ),
        approval_timeout_ms=int(
            _pick(value, "approval_timeout_ms", "approvalTimeoutMs", default=300_000)
        ),
        flush_interval_ms=int(_pick(value, "flush_interval_ms", "flushIntervalMs", default=2_000)),
        max_batch_size=int(_pick(value, "max_batch_size", "maxBatchSize", default=25)),
        max_queue_size=int(_pick(value, "max_queue_size", "maxQueueSize", default=5_000)),
        retry_attempts=int(_pick(value, "retry_attempts", "retryAttempts", default=3)),
        retry_base_delay_ms=int(
            _pick(value, "retry_base_delay_ms", "retryBaseDelayMs", default=250)
        ),
        queue_storage_path=_pick(value, "queue_storage_path", "queueStoragePath"),
        queue_drop_policy=_pick(
            value, "queue_drop_policy", "queueDropPolicy", default="drop_oldest"
        ),
        queue_idempotency_key=_pick(value, "queue_idempotency_key", "queueIdempotencyKey"),
        on_error=_pick(value, "on_error", "onError", default="warn"),
        redact=_pick(value, "redact"),
        redact_keys=list(_pick(value, "redact_keys", "redactKeys", default=[]) or []),
        redact_allow_paths=list(
            _pick(value, "redact_allow_paths", "redactAllowPaths", default=[]) or []
        ),
        redact_deny_patterns=list(
            _pick(value, "redact_deny_patterns", "redactDenyPatterns", default=[]) or []
        ),
        max_event_payload_bytes=_pick(value, "max_event_payload_bytes", "maxEventPayloadBytes"),
        timeout=_pick(value, "timeout"),
        headers=dict(_pick(value, "headers", default={}) or {}),
    )
    return config


def resolve_config(
    input_config: Optional[Any] = None,
    file_config: Optional[Any] = None,
) -> ApieConfig:
    merged = _deep_merge(_as_dict(file_config), _as_dict(input_config))
    config = coerce_config(merged)

    api_key = config.api_key or os.getenv("APIE_API_KEY")
    base_url = config.base_url or os.getenv("APIE_BASE_URL") or "http://localhost:3000"

    release_mode = (
        "guard"
        if config.mode == "enforce"
        else "monitor"
        if config.mode == "monitor"
        else config.release_mode
    )

    config.api_key = api_key
    config.base_url = base_url
    config.release_mode = release_mode
    if not config.guard_failure_mode:
        config.guard_failure_mode = "fail_open"
    return config


def tool_definition_from_capability(capability: DeclaredCapabilityInput) -> ToolDefinitionInput:
    return ToolDefinitionInput(
        name=capability.tool.name,
        provider=capability.tool.provider,
        action_types=capability.actions,
        resource_types=capability.resources,
        risk_level=capability.risk_level,
    )
