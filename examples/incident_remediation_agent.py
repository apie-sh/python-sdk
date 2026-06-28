from __future__ import annotations

from apie import Apie


def main() -> None:
    apie = Apie.create(
        {
            "agent": {"key": "incident-remediation", "name": "Incident Remediation Agent"},
        }
    )
    apie.ready()

    def run_agent() -> None:
        apie.with_tool(
            {
                "tool": {"name": "search_incident", "provider": "ops", "riskLevel": "low"},
                "action": {"type": "read", "name": "search_incident"},
                "resource": {"type": "incident_signal", "provider": "pagerduty"},
            },
            lambda: {"ok": True},
        )

    apie.with_run({"inputSummary": "Process incident request"}, lambda _run: run_agent())
    apie.flush()
    apie.shutdown()


if __name__ == "__main__":
    main()
