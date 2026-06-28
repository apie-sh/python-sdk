"""Example LangChain callback instrumentation."""

from apie import Apie
from apie.integrations.langchain_callback import ApieCallbackHandler


def main() -> None:
    apie = Apie.create(
        {
            "agent": {"key": "langchain-demo", "name": "LangChain Demo"},
            "release_mode": "monitor",
        }
    )
    apie.ready()
    handler = ApieCallbackHandler(apie, default_environment="development")
    _ = handler
    apie.shutdown()


if __name__ == "__main__":
    main()
