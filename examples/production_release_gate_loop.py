from __future__ import annotations

from apie import Apie, with_mcp_tool_call, with_openai_tool_call


def main() -> None:
    apie = Apie.create(
        {
            "agent": {
                "key": "release-gate-orchestrator",
                "name": "Release Gate Orchestrator",
            },
            "runtime": {
                "environment": "production",
                "framework": "langgraph",
            },
            "mode": "monitor",
        }
    )
    apie.ready()

    def run_session(session) -> None:
        def run_orchestrator(run) -> None:
            with_openai_tool_call(
                apie,
                {
                    "runId": run.id,
                    "toolName": "summarize_release_risk",
                    "arguments": {"service": "api", "environment": "production"},
                    "resourceType": "work_item",
                    "riskLevel": "medium",
                },
                lambda: {"summary": "No blocker found in latest incident feed."},
            )

            with_mcp_tool_call(
                apie,
                {
                    "runId": run.id,
                    "sessionId": session.id,
                    "server": "internal-cicd",
                    "tool": "trigger_pipeline",
                    "actionType": "execute",
                    "resourceType": "pipeline_run",
                    "environment": "production",
                    "riskLevel": "high",
                    "resourceTarget": "payments-service",
                    "inputSchema": {
                        "service": "string",
                        "ref": "string",
                        "dryRun": "boolean",
                    },
                },
                lambda: {"accepted": True, "runId": "pipe_123"},
            )

        apie.with_run(
            {
                "sessionId": session.id,
                "stepName": "Release gate orchestrator",
                "inputSummary": "Collect rollout evidence and risky actions",
            },
            run_orchestrator,
        )

    apie.with_session(
        {
            "kind": "pipeline",
            "inputSummary": "Validate production rollout readiness",
            "metadata": {"workflow": "release_gate"},
        },
        run_session,
    )
    apie.flush()
    apie.shutdown()


if __name__ == "__main__":
    main()
