from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from typer.testing import CliRunner

import apie.cli as cli
from apie.cli import app


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Apie CLI" in result.stdout


def test_init_generates_valid_config_with_capabilities(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    input_text = "\n".join(
        [
            "Incident Bot",
            "incident-bot",
            "development",
            "langgraph",
            "apie_sk_test_123",
            "y",
            "search_incident",
            "internal",
            "read",
            "internal_api",
            "low",
            "n",
            "",
        ]
    )

    result = runner.invoke(app, ["init"], input=input_text)
    assert result.exit_code == 0

    config_path = tmp_path / "apie.config.py"
    assert config_path.exists()
    source = config_path.read_text(encoding="utf-8")
    assert '"capabilities": [' in source
    assert '"mode": "monitor"' in source
    compile(source, str(config_path), "exec")

    assert (tmp_path / ".env").exists()
    assert (tmp_path / ".env.example").exists()


def test_send_test_event_command(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[str] = []

    class FakeApie:
        @classmethod
        def create(cls):
            calls.append("create")
            return cls()

        def ready(self):
            calls.append("ready")
            return SimpleNamespace(agent_id="agt_1", dashboard_url="http://dash")

        def send_test_event(self, payload):
            calls.append(f"send:{payload['mode']}")
            return SimpleNamespace(session_id="ses_1", run_ids=["run_1"])

        def flush(self):
            calls.append("flush")

        def shutdown(self):
            calls.append("shutdown")

    monkeypatch.setattr(cli, "Apie", FakeApie)
    result = runner.invoke(app, ["send-test-event", "--mode", "single"])

    assert result.exit_code == 0
    assert "Test event sent successfully." in result.stdout
    assert calls == ["create", "ready", "send:single", "flush", "shutdown"]


def test_doctor_command_with_send_test(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[str] = []

    @dataclass
    class QueueStats:
        queue_size: int = 1
        dropped_count: int = 0
        deduplicated_count: int = 0
        flush_count: int = 2
        retry_count: int = 1
        last_flush_at: str | None = None
        last_error_at: str | None = None
        last_error_message: str | None = None

    class FakeApie:
        @classmethod
        def create(cls):
            return cls()

        def doctor(self):
            calls.append("doctor")
            return {
                "registration": SimpleNamespace(
                    agent_id="agt_1",
                    workspace_id="ws_1",
                    dashboard_url="http://dash",
                ),
                "enabled": True,
                "baseUrl": "http://localhost:3000",
                "apiKeyConfigured": True,
                "mode": "monitor",
                "guardFailureMode": "fail_open",
                "runtimeEnvironment": "development",
                "runtimeFramework": "langgraph",
                "queueStoragePath": None,
                "redactionEnabled": False,
                "trustWarnings": [],
                "queue": QueueStats(),
            }

        def validate_events(self, _):
            calls.append("validate")
            return {"previews": [{"validation_status": "queued"}]}

        def send_test_event(self, _):
            calls.append("send")
            return SimpleNamespace(session_id="ses_1")

        def flush(self):
            calls.append("flush")

        def shutdown(self):
            calls.append("shutdown")

    monkeypatch.setattr(cli, "Apie", FakeApie)
    result = runner.invoke(app, ["doctor", "--send-test"])

    assert result.exit_code == 0
    assert "Apie doctor" in result.stdout
    assert "Event validation preview: queued" in result.stdout
    assert calls == ["doctor", "validate", "send", "flush", "shutdown"]


def test_capabilities_declare_command(monkeypatch) -> None:
    runner = CliRunner()

    class FakeConfig:
        capabilities = [SimpleNamespace()]

    class FakeApie:
        @classmethod
        def create(cls):
            return cls()

        def declare_capabilities(self, _):
            return {"declared": [{"id": "cap_1"}]}

    monkeypatch.setattr(cli, "load_apie_config", lambda: FakeConfig())
    monkeypatch.setattr(cli, "Apie", FakeApie)
    result = runner.invoke(app, ["capabilities", "declare"])

    assert result.exit_code == 0
    assert "Declared 1 capabilities" in result.stdout


def test_guardrails_enable_command(monkeypatch) -> None:
    runner = CliRunner()

    class FakeApie:
        @classmethod
        def create(cls):
            return cls()

        def enable_guardrail_template(self, key: str):
            return {"key": key}

    monkeypatch.setattr(cli, "Apie", FakeApie)
    result = runner.invoke(app, ["guardrails", "enable", "prod-secrets", "--mode", "monitor"])

    assert result.exit_code == 0
    assert "Enabled prod-secrets" in result.stdout


def test_report_create_command(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[str] = []

    class FakeReports:
        def create(self, _input):
            calls.append("create")
            return SimpleNamespace(report_id="rpt_1", status="draft", web_url="http://report")

        def wait_until_ready(self, report_id: str):
            calls.append(f"wait:{report_id}")
            return {"export_urls": {"json": "http://report.json"}}

    class FakeApie:
        reports = FakeReports()

        @classmethod
        def create(cls):
            return cls()

        def ready(self):
            calls.append("ready")

        def shutdown(self):
            calls.append("shutdown")

    monkeypatch.setattr(cli, "Apie", FakeApie)
    result = runner.invoke(
        app,
        ["report", "create", "--last", "7d", "--environment", "production", "--title", "Weekly"],
    )

    assert result.exit_code == 0
    assert "Agent Boundary Report generated." in result.stdout
    assert "JSON export:" in result.stdout
    assert calls == ["ready", "create", "wait:rpt_1", "shutdown"]
