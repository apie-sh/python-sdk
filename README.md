# apie-sdk

Official Python SDK for [Apie](https://apie.sh) — runtime visibility and guardrails for AI agents.

## Install

```bash
pip install apie-sdk
```

## Environment

```env
APIE_API_KEY=apie_sk_test_...
APIE_BASE_URL=https://api.apie.sh
```

## Quick Start (Sync)

```python
from apie import Apie, with_openai_tool_call

apie = Apie.create(
    {
        "agent": {
            "key": "incident-remediation",
            "name": "Incident Remediation Agent",
        }
    }
)

apie.ready()

apie.with_run({"inputSummary": "Process request"}, lambda run: apie.with_tool(
    {
        "runId": run.id,
        "tool": {"name": "search", "riskLevel": "low"},
        "action": {"type": "read", "name": "search"},
        "resource": {"type": "knowledge_base"},
    },
    lambda: {"ok": True},
))

# Integration helpers are also exported from the package root.
with_openai_tool_call(
    apie,
    {"runId": "run_123", "toolName": "search"},
    lambda: {"ok": True},
)

apie.flush()
apie.shutdown()
```

## Quick Start (Async)

```python
import asyncio
from apie import AsyncApie


async def main() -> None:
    apie = await AsyncApie.create(
        {
            "agent": {
                "key": "incident-remediation",
                "name": "Incident Remediation Agent",
            }
        }
    )
    await apie.ready()
    await apie.send_test_event({"mode": "pipeline"})
    await apie.flush()
    await apie.shutdown()


asyncio.run(main())
```

## Lifecycle Notes

- `Apie` (sync) starts registration during construction for enabled clients and `ready()` returns the resolved registration (or raises any startup registration error).
- `AsyncApie` cannot await in `__init__`; it starts a background registration task when constructed inside an active event loop. Call `await apie.ready()` to deterministically wait for registration and surface failures.

## CLI

```bash
apie init
apie doctor
apie doctor --send-test
apie send-test-event --mode pipeline
apie send-test-event --mode single
apie capabilities declare
apie guardrails enable prod-secrets
apie report create --last 7d --environment production
```

## Integration Helpers

Integration helpers are available from both `apie` and `apie.integrations`, including:

- `with_openai_tool_call` / `with_anthropic_tool_call`
- `with_openai_agent_step` / `with_openai_agent_tool_call`
- `with_langgraph_node` / `with_langchain_tool_step`
- `with_crewai_task`, `with_autogen_step`, `with_llamaindex_step`
- `with_mcp_tool_call`
- `with_workflow_step` / `with_canonical_tool_action`
- `with_github_action`, `with_gitlab_action`, `with_issue_tracker_action`
- `with_incident_response_action`, `with_observability_correlation`
- `create_http_guard`

Async variants are available with the `_async` suffix.

### Minimal wrapper vs full boundary metadata

Start minimal for activation:

```python
with_mcp_tool_call(
    apie,
    {"runId": run.id, "server": "internal-cicd", "tool": "trigger_pipeline"},
    lambda: mcp_client.call_tool("trigger_pipeline", {"service": "api"}),
)
```

Then switch to full metadata once you tune controls:

```python
with_mcp_tool_call(
    apie,
    {
        "runId": run.id,
        "server": "internal-cicd",
        "tool": "trigger_pipeline",
        "actionType": "execute",
        "resourceType": "pipeline_run",
        "environment": "production",
        "riskLevel": "high",
        "resourceTarget": "payments-service",
        "inputSchema": {"service": "string", "ref": "string", "dryRun": "boolean"},
    },
    lambda: mcp_client.call_tool("trigger_pipeline", {"service": "payments-service"}),
)
```

## Examples

- `examples/incident_remediation_agent.py` - baseline monitor-mode instrumentation
- `examples/production_release_gate_loop.py` - production-bound workflow with MCP and risky action coverage
- `examples/guardrail_packs_smoke.py` - simulate starter guardrail packs in monitor mode
- `examples/multi_agent_pipeline.py` - multi-agent session and handoff telemetry