from __future__ import annotations

import apie as sdk


def test_root_exports_cover_public_surface() -> None:
    required_exports = [
        "Apie",
        "AsyncApie",
        "ApieClient",
        "AsyncApieClient",
        "ApieError",
        "ApieConfig",
        "ApieAgentConfig",
        "ApieRuntimeConfig",
        "ApieModelConfig",
        "ApieToolConfig",
        "ApieClientOptions",
        "AsyncApieClientOptions",
        "with_openai_tool_call",
        "with_mcp_tool_call",
        "with_workflow_step",
        "create_http_guard",
        "with_issue_tracker_action",
        "send_events",
        "EventQueueDiagnostics",
    ]
    for name in required_exports:
        assert hasattr(sdk, name), f"missing export: {name}"


def test_exported_types_can_be_constructed() -> None:
    config = sdk.ApieConfig(agent=sdk.ApieAgentConfig(key="agent", name="Agent"))
    assert config.agent.key == "agent"
    assert config.release_mode == "monitor"
