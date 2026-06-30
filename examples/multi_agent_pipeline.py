from __future__ import annotations

from apie import Apie


def main() -> None:
    apie = Apie.create(
        {
            "agent": {"key": "pipeline-orchestrator", "name": "Pipeline Orchestrator"},
        }
    )
    apie.ready()

    def run_pipeline(session):
        def orchestrator(orchestrator_run):
            apie.with_llm_call(
                {
                    "runId": orchestrator_run.id,
                    "sessionId": session.id,
                    "stepName": "Plan",
                    "payloadSummary": {"model": "gpt-4.1-mini"},
                },
                lambda: None,
            )

            def worker(worker_run):
                apie.with_mcp_call(
                    {
                        "runId": worker_run.id,
                        "sessionId": session.id,
                        "stepName": "Lookup",
                        "payloadSummary": {"server": "inventory", "tool": "get_inventory"},
                    },
                    lambda: None,
                )

            apie.with_child_run(
                {
                    "sessionId": session.id,
                    "parentRunId": orchestrator_run.id,
                    "stepName": "Worker",
                    "role": "worker",
                },
                worker,
            )

        apie.with_run({"sessionId": session.id, "stepName": "Orchestrator"}, orchestrator)

    apie.with_session({"kind": "pipeline", "inputSummary": "Deploy release"}, run_pipeline)
    apie.flush()
    apie.shutdown()


if __name__ == "__main__":
    main()
