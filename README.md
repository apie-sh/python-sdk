# apie-sdk

Official Python SDK for [Apie](https://apie.sh) — runtime visibility and guardrails for AI agents.

**[Full documentation →](https://apie.mintlify.site/)**

> **Pre-release.** This package is not yet stable — do not use in production.

---

## Install

```bash
pip install apie-sdk
```

The CLI ships with the package — no separate install needed.

## Environment

```env
APIE_API_KEY=apie_sk_test_...
APIE_BASE_URL=https://api.apie.sh
```

## Quick start

Scaffold config and verify connectivity in one pass:

```bash
apie init
apie send-test-event          # pipeline smoke test — prints session replay URL
apie send-test-event --mode single
apie doctor                   # config, queue, and ingestion diagnostics
apie doctor --send-test
```

### 1. Initialize

One client per process:

```python
from apie import Apie

apie = Apie.create(
    {
        "agent": {
            "key": "incident-remediation",
            "name": "Incident Remediation Agent",
        }
    }
)
apie.ready()
```

For async applications, use `AsyncApie` and `await apie.ready()` — see [Async](#async) below.

### 2. Choose your integration path

Start simple; add metadata later when you tune guardrails for production.

| Path | When to use | Effort |
| --- | --- | --- |
| [MCP proxy](#mcp-proxy) | MCP hosts (Cursor, Claude Desktop) | Config only |
| Framework plugin | LangChain, OpenAI Agents | ~5 lines |
| `with_run` + instrumented client | Custom agents with MCP tools | ~10 lines |
| `with_tool` with full metadata | Production guard mode tuning | Per call site |

### 3. Instrument

**Tier 1 — Framework plugin.** Tools auto-instrument inside a run:

```python
from apie import Apie
from apie.integrations import ApieCallbackHandler

apie = Apie.create({"agent": {"key": "my-agent", "name": "My Agent"}})
apie.ready()

handler = ApieCallbackHandler(apie, default_environment="production")

def run_agent() -> None:
    # Pass handler to your LangChain agent callbacks — no per-tool wrappers
    ...

apie.with_run({"inputSummary": "Process request"}, lambda _run: run_agent())
apie.flush()
apie.shutdown()
```

**Tier 2 — Instrumented MCP client.** Wrap once; calls inside a run need no explicit `runId`:

```python
from apie import Apie, create_instrumented_mcp_client

apie = Apie.create({"agent": {"key": "my-agent", "name": "My Agent"}})
apie.ready()

mcp = create_instrumented_mcp_client(apie, raw_mcp_client, server="github-mcp")

apie.with_run(
    {"inputSummary": "Search repo"},
    lambda _run: mcp.call_tool("search_code", {"query": "rollback"}),
)
apie.flush()
apie.shutdown()
```

**Tier 3 — Explicit metadata.** Optional — tune guardrails and boundary maps:

```python
apie.with_run({"inputSummary": "Process request"}, lambda _run: apie.with_tool(
    {
        "tool": {"name": "search", "riskLevel": "low"},
        "action": {"type": "read", "name": "search"},
        "resource": {"type": "knowledge_base"},
    },
    lambda: {"ok": True},
))
```

Action and resource types are inferred from tool names when omitted. Add explicit `action`, `resource`, and `environment` when enabling guard mode in production.

## Async

`AsyncApie` cannot await in `__init__`; it starts a background registration task when constructed inside an active event loop. Call `await apie.ready()` to wait for registration and surface failures.

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

Async variants of integration helpers use the `_async` suffix (for example, `with_mcp_tool_call_async`).

## Requirements

- Python 3.10+

## MCP proxy

Observe and control MCP tool calls without rewriting every call site:

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

## Integration helpers

### Framework wrappers

| Helper | Use with |
| --- | --- |
| `ApieCallbackHandler` | LangChain / LangGraph |
| `create_apie_run_hooks` | OpenAI Agents |
| `with_openai_tool_call`, `with_anthropic_tool_call`, `with_tool_call_guard` | LLM tool calls |
| `with_openai_agent_step`, `with_openai_agent_tool_call` | OpenAI Agents SDK |
| `with_langgraph_node`, `with_langchain_tool_step` | LangChain / LangGraph |
| `with_crewai_task`, `with_crewai_tool_step` | CrewAI |
| `with_autogen_step`, `with_autogen_tool_step` | AutoGen |
| `with_llamaindex_step`, `with_llamaindex_tool_step` | LlamaIndex |
| `with_mcp_tool_call`, `create_instrumented_mcp_client` | MCP |
| `with_vercel_ai_generation` | Vercel AI SDK |
| `with_workflow_step`, `with_canonical_tool_action` | Custom workflows |
| `create_http_guard` | HTTP handlers |

### Platform connectors

Provider-neutral canonical mapping for common integrations:

- `with_github_action`, `with_gitlab_action`
- `with_issue_tracker_action` (Linear / Jira)
- `with_incident_response_action` (PagerDuty / Opsgenie)
- `with_observability_correlation` (Datadog / Sentry)

See `examples/` for runnable patterns.

### MCP metadata progression

Start minimal for activation:

```python
with_mcp_tool_call(
    apie,
    {"server": "internal-cicd", "tool": "trigger_pipeline"},
    lambda: mcp_client.call_tool("trigger_pipeline", {"service": "api"}),
)
```

Then switch to full metadata once you tune controls:

```python
with_mcp_tool_call(
    apie,
    {
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

| Example | What it demonstrates |
| --- | --- |
| `examples/incident_remediation_agent.py` | Baseline monitor-mode instrumentation |
| `examples/production_release_gate_loop.py` | Production-bound workflow with MCP and risky action coverage |
| `examples/guardrail_packs_smoke.py` | Simulate starter guardrail packs in monitor mode |
| `examples/multi_agent_pipeline.py` | Multi-agent session and handoff telemetry |
| `examples/langchain_instrumented_agent.py` | LangChain callback handler |
| `examples/openai_agents_instrumented.py` | OpenAI Agents run hooks |
| `examples/apie.mcp.json` + `examples/mcp_proxy_stdio.sh` | MCP proxy host config |

## CLI

| Command | Description |
| --- | --- |
| `apie init` | Scaffold `apie.config.py` |
| `apie doctor [--send-test] [--mcp]` | Validate config, queue, and ingestion health |
| `apie mcp proxy` | MCP proxy (stdio or SSE) with monitor/guard modes |
| `apie send-test-event` | Verify connectivity (pipeline or single mode) |
| `apie capabilities declare` | Declare capabilities from config |
| `apie guardrails enable <key>` | Enable a guardrail template |
| `apie report create` | Generate a boundary report |

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

## License

MIT
