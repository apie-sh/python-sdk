from __future__ import annotations

import json
from pathlib import Path

import pytest

from apie.mcp_core.config import load_mcp_proxy_config
from apie.mcp_core.inference import infer_from_tool_name
from apie.mcp_core.payload import McpToolCallInput, build_mcp_tool_call_payload
from apie.mcp_core.redact import summarize_args


def test_infer_from_tool_name_deploy() -> None:
    result = infer_from_tool_name("github-mcp.deploy_service")
    assert result is not None
    assert result.action_type == "execute"
    assert result.resource_type == "deployment_event"
    assert result.risk_level == "critical"


def test_build_mcp_tool_call_payload_sets_capture_source(tmp_path: Path) -> None:
    payload = build_mcp_tool_call_payload(
        McpToolCallInput(
            server_name="filesystem",
            tool_name="read_file",
            arguments={"path": "/tmp/test", "token": "secret"},
            redact_keys=["token"],
        )
    )
    assert payload.tool["name"] == "filesystem.read_file"
    assert payload.metadata["capture_source"] == "mcp_proxy"
    assert payload.metadata["mcp"]["arguments"]["token"] == "[REDACTED]"


def test_summarize_args_redacts_nested_keys() -> None:
    result = summarize_args({"apiKey": "abc", "query": "hello"})
    assert result["apiKey"] == "[REDACTED]"
    assert result["query"] == "hello"


def test_load_mcp_proxy_config_single_server(tmp_path: Path) -> None:
    config_path = tmp_path / "apie.mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "agentKey": "agent-1",
                "serverName": "filesystem",
                "releaseMode": "monitor",
                "upstream": {"command": "npx", "args": ["-y", "server"]},
            }
        ),
        encoding="utf-8",
    )
    loaded = load_mcp_proxy_config(str(config_path))
    assert loaded.server_name == "filesystem"
    assert loaded.agent_key == "agent-1"
    assert loaded.upstream.command == "npx"


def test_load_mcp_proxy_config_multi_server(tmp_path: Path) -> None:
    config_path = tmp_path / "apie.mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "servers": {
                    "github": {
                        "agentKey": "agent-1",
                        "upstream": {"command": "gh", "args": []},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    loaded = load_mcp_proxy_config(str(config_path), server_name="github")
    assert loaded.server_name == "github"
    assert loaded.agent_key == "agent-1"
