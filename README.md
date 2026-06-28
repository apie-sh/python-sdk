# apie-sdk

Official Python SDK for [Apie](https://apie.sh) — runtime visibility and guardrails for AI agents.

**[Full documentation →](https://apie.mintlify.site/)**

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
apie doctor --mcp
apie mcp proxy --config apie.mcp.json
apie mcp proxy --transport sse --port 3100 --config apie.mcp.json
apie send-test-event --mode pipeline
apie send-test-event --mode single
apie capabilities declare
apie guardrails enable prod-secrets
apie report create --last 7d --environment production
```

## MCP Proxy

Observe and control MCP tool calls without rewriting agent code:

```bash
pip install apie-sdk[mcp-proxy]

# apie.mcp.json — see examples/apie.mcp.json
apie mcp proxy --config apie.mcp.json

# SSE transport for remote agents
apie mcp proxy --transport sse --port 3100 --config apie.mcp.json

# Validate MCP proxy setup
apie doctor --mcp
```

Point your MCP host config at `apie mcp proxy` instead of the upstream server command.

## Integration Helpers

Integration helpers are available from both `apie` and `apie.integrations`, including:

- `with_openai_tool_call` / `with_anthropic_tool_call`
- `with_openai_agent_step` / `with_openai_agent_tool_call`
- `with_langgraph_node` / `with_langchain_tool_step`
- `with_crewai_task`, `with_autogen_step`, `with_llamaindex_step`
- `with_mcp_tool_call`
- `create_instrumented_mcp_client` / `create_instrumented_mcp_client_async` (recommended embedded MCP path)
- `ApieCallbackHandler` (LangChain/LangGraph)
- `create_apie_run_hooks` (OpenAI Agents SDK)
- `with_workflow_step` / `with_canonical_tool_action`
- `with_github_action`, `with_gitlab_action`, `with_issue_tracker_action`
- `with_incident_response_action`, `with_observability_correlation`
- `create_http_guard`

Async variants are available with the `_async` suffix.

### Minimal wrapper vs full boundary metadata

**Recommended:** wrap your MCP client once with `create_instrumented_mcp_client` — calls inside `with_run` need no explicit `runId`:

```python
from apie import create_instrumented_mcp_client

mcp = create_instrumented_mcp_client(apie, raw_mcp_client, server="github-mcp")

apie.with_run({"inputSummary": "Search repo"}, lambda run: mcp.call_tool(
    "search_code",
    {"query": "rollback"},
))
```

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

## Documentation

| Topic | Link |
| --- | --- |
| Connect your first agent | [apie.mintlify.site/getting-started/connect-your-first-agent](https://apie.mintlify.site/getting-started/connect-your-first-agent) |
| Configuration reference | [apie.mintlify.site/reference/configuration](https://apie.mintlify.site/reference/configuration) |
| How Apie works | [apie.mintlify.site/concepts/how-apie-works](https://apie.mintlify.site/concepts/how-apie-works) |
| Trace runs and sessions | [apie.mintlify.site/observe/trace-runs-and-sessions](https://apie.mintlify.site/observe/trace-runs-and-sessions) |
| Guardrails | [apie.mintlify.site/guardrails/enforce-guardrails](https://apie.mintlify.site/guardrails/enforce-guardrails) |
| Choose how to instrument | [apie.mintlify.site/getting-started/choose-how-to-instrument](https://apie.mintlify.site/getting-started/choose-how-to-instrument) |
| Multi-agent pipelines | [apie.mintlify.site/observe/multi-agent-pipelines](https://apie.mintlify.site/observe/multi-agent-pipelines) |
| Integrations | [apie.mintlify.site/integrations/index](https://apie.mintlify.site/integrations/index) |
| Recipes | [apie.mintlify.site/recipes/incident-remediation](https://apie.mintlify.site/recipes/incident-remediation) |
| CLI | [apie.mintlify.site/reference/cli](https://apie.mintlify.site/reference/cli) |

## Examples

- `examples/incident_remediation_agent.py` - baseline monitor-mode instrumentation
- `examples/production_release_gate_loop.py` - production-bound workflow with MCP and risky action coverage
- `examples/guardrail_packs_smoke.py` - simulate starter guardrail packs in monitor mode
- `examples/multi_agent_pipeline.py` - multi-agent session and handoff telemetry
- `examples/langchain_instrumented_agent.py` - LangChain callback handler
- `examples/openai_agents_instrumented.py` - OpenAI Agents run hooks
- `examples/apie.mcp.json` + `examples/mcp_proxy_stdio.sh` - MCP proxy host config