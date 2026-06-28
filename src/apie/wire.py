from __future__ import annotations

import os
import re
from dataclasses import asdict, is_dataclass
from typing import Any

from ._version import SDK_VERSION
from .types import ApieConfig, ApieToolConfig, RegisterResponse

_CAMEL_RE_1 = re.compile("(.)([A-Z][a-z]+)")
_CAMEL_RE_2 = re.compile("([a-z0-9])([A-Z])")


def to_snake_case_key(key: str) -> str:
    return _CAMEL_RE_2.sub(r"\1_\2", _CAMEL_RE_1.sub(r"\1_\2", key)).lower()


def _to_plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value


def to_wire_tool(tool: ApieToolConfig) -> dict[str, Any]:
    return {
        "name": tool.name,
        "action_types": tool.action_types or None,
        "resource_types": tool.resource_types or None,
        "risk_level": tool.risk_level,
        "provider": tool.provider,
    }


def build_register_payload(config: ApieConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "agent": {
            "key": config.agent.key,
            "name": config.agent.name,
            "purpose": config.agent.purpose,
            "owner_email": config.agent.owner,
            "team": config.agent.team,
            "description": config.agent.description,
        },
        "runtime": {
            "environment": config.runtime.environment,
            "framework": config.runtime.framework,
            "language": config.runtime.language or "python",
            "sdk_version": config.runtime.sdk_version or SDK_VERSION,
        },
        "model": _to_plain(config.model),
        "release_mode": config.release_mode,
        "tools": [to_wire_tool(tool) for tool in config.tools] or None,
        "prompt_hash": config.prompt_hash,
        "hostname": os.getenv("HOSTNAME", "local"),
    }

    if config.version.version or config.version.framework or config.version.model_name:
        payload["version"] = {
            "version": config.version.version,
            "framework": config.version.framework or config.runtime.framework,
            "model_provider": config.version.model_provider or config.model.provider,
            "model_name": config.version.model_name or config.model.name,
        }
    if config.source.git_sha or config.source.deployment_id:
        payload["source"] = {
            "git_sha": config.source.git_sha,
            "deployment_id": config.source.deployment_id,
        }
    return payload


def parse_register_response(body: dict[str, Any]) -> RegisterResponse:
    return RegisterResponse(
        agent_id=str(body.get("agent_id", "")),
        agent_version_id=str(body.get("agent_version_id", "")),
        workspace_id=str(body.get("workspace_id", "")),
        config_hash=str(body.get("config_hash", "")),
        status="registered",
        created=bool(body.get("created")),
        version_created=bool(body.get("version_created")),
        ingest_url=str(body.get("ingest_url", "")),
        recommended_next_step=str(body.get("recommended_next_step", "")),
        dashboard_url=str(body.get("dashboard_url", "")),
    )


def to_wire_event(event: dict[str, Any]) -> dict[str, Any]:
    wire: dict[str, Any] = {}
    for key, value in event.items():
        if value is None:
            continue
        wire[to_snake_case_key(key)] = value
    return wire
