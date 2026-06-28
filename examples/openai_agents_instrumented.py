"""Example OpenAI Agents hooks instrumentation."""

from apie import Apie
from apie.integrations.openai_agents_hooks import create_apie_run_hooks


def main() -> None:
    apie = Apie.create(
        {
            "agent": {"key": "openai-agents-demo", "name": "OpenAI Agents Demo"},
            "release_mode": "monitor",
        }
    )
    apie.ready()
    hooks = create_apie_run_hooks(apie, agent_name="triage-agent")
    _ = hooks
    apie.shutdown()


if __name__ == "__main__":
    main()
