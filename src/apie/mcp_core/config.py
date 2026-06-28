from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import ReleaseMode


@dataclass(slots=True)
class McpUpstreamConfig:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


@dataclass(slots=True)
class McpServerConfig:
    server_name: str
    agent_key: str
    upstream: McpUpstreamConfig
    agent_name: str | None = None
    release_mode: ReleaseMode = "monitor"
    redact_keys: list[str] | None = None
    environment: str | None = None
    approval_timeout_ms: int | None = None


@dataclass(slots=True)
class McpProxyConfigFile:
    agent_key: str | None = None
    agent_name: str | None = None
    server_name: str | None = None
    release_mode: ReleaseMode | None = None
    upstream: McpUpstreamConfig | None = None
    redact_keys: list[str] | None = None
    environment: str | None = None
    approval_timeout_ms: int | None = None
    servers: dict[str, dict[str, Any]] | None = None


def _parse_upstream(raw: dict[str, Any]) -> McpUpstreamConfig:
    return McpUpstreamConfig(
        command=str(raw["command"]),
        args=[str(arg) for arg in raw.get("args", [])],
        env={str(k): str(v) for k, v in (raw.get("env") or {}).items()} or None,
    )


def load_mcp_proxy_config(config_path: str, server_name: str | None = None) -> McpServerConfig:
    full_path = Path(config_path).resolve()
    if not full_path.exists():
        raise FileNotFoundError(f"MCP proxy config not found: {full_path}")

    raw = json.loads(full_path.read_text(encoding="utf-8"))

    if raw.get("servers"):
        name = server_name or raw.get("serverName")
        if not name:
            raise ValueError("Specify --server when using multi-server apie.mcp.json")
        server = raw["servers"].get(name)
        if not server:
            raise ValueError(f'Unknown MCP server "{name}" in config')
        return McpServerConfig(
            server_name=name,
            agent_key=server["agentKey"],
            agent_name=server.get("agentName") or raw.get("agentName"),
            release_mode=server.get("releaseMode") or raw.get("releaseMode") or "monitor",
            upstream=_parse_upstream(server["upstream"]),
            redact_keys=server.get("redactKeys") or raw.get("redactKeys"),
            environment=server.get("environment") or raw.get("environment"),
            approval_timeout_ms=server.get("approvalTimeoutMs") or raw.get("approvalTimeoutMs"),
        )

    if not raw.get("agentKey") or not raw.get("serverName") or not raw.get("upstream"):
        raise ValueError("apie.mcp.json requires agentKey, serverName, and upstream")

    return McpServerConfig(
        server_name=raw["serverName"],
        agent_key=raw["agentKey"],
        agent_name=raw.get("agentName"),
        release_mode=raw.get("releaseMode") or "monitor",
        upstream=_parse_upstream(raw["upstream"]),
        redact_keys=raw.get("redactKeys"),
        environment=raw.get("environment"),
        approval_timeout_ms=raw.get("approvalTimeoutMs"),
    )
