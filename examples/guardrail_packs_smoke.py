from __future__ import annotations

from apie import Apie


def main() -> None:
    apie = Apie.create(
        {
            "agent": {
                "key": "guardrail-pack-smoke-agent",
                "name": "Guardrail Pack Smoke Agent",
            },
            "runtime": {"environment": "production"},
            "mode": "monitor",
        }
    )
    apie.ready()

    def run_smoke(run) -> None:
        scenarios = [
            {
                "tool": {"name": "deploy.release", "provider": "cicd", "riskLevel": "high"},
                "action": {"type": "execute", "name": "deploy.release"},
                "resource": {"type": "deployment_event", "environment": "production"},
            },
            {
                "tool": {"name": "vault.read", "provider": "vault", "riskLevel": "high"},
                "action": {"type": "read", "name": "vault.read"},
                "resource": {"type": "secret", "environment": "production"},
            },
            {
                "tool": {"name": "db.update", "provider": "postgres", "riskLevel": "high"},
                "action": {"type": "update", "name": "db.update"},
                "resource": {"type": "database_record", "environment": "production"},
            },
            {
                "tool": {
                    "name": "github.merge_pr",
                    "provider": "github",
                    "riskLevel": "high",
                },
                "action": {"type": "merge", "name": "github.merge_pr"},
                "resource": {"type": "code_repository", "environment": "production"},
            },
            {
                "tool": {
                    "name": "shell.rm_rf",
                    "provider": "shell",
                    "riskLevel": "critical",
                },
                "action": {"type": "delete", "name": "shell.rm_rf"},
                "resource": {"type": "shell_command", "environment": "production"},
            },
        ]

        for scenario in scenarios:
            apie.with_tool(
                {
                    "runId": run.id,
                    "tool": scenario["tool"],
                    "action": scenario["action"],
                    "resource": scenario["resource"],
                },
                lambda: {"ok": True},
            )

    apie.with_run(
        {"inputSummary": "Exercise starter guardrail packs in monitor mode"},
        run_smoke,
    )
    apie.flush()
    apie.shutdown()


if __name__ == "__main__":
    main()
