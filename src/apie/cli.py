from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional, cast

import typer

from .apie import Apie
from .config import load_apie_config
from .types import BoundaryReportCreateInput

app = typer.Typer(help="Apie CLI for agent instrumentation")
capabilities_app = typer.Typer(help="Capability management commands")
guardrails_app = typer.Typer(help="Guardrail management commands")
report_app = typer.Typer(help="Boundary report commands")

app.add_typer(capabilities_app, name="capabilities")
app.add_typer(guardrails_app, name="guardrails")
app.add_typer(report_app, name="report")


def _slugify(name: str) -> str:
    normalized = "".join(c if c.isalnum() else "-" for c in name.lower())
    return "-".join(part for part in normalized.split("-") if part)


def _detect_framework() -> str:
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8").lower()
        if "langgraph" in content:
            return "langgraph"
        if "openai" in content:
            return "openai-agents"
        if "anthropic" in content:
            return "anthropic"
    req = Path("requirements.txt")
    if req.exists():
        content = req.read_text(encoding="utf-8").lower()
        if "langgraph" in content:
            return "langgraph"
        if "openai" in content:
            return "openai-agents"
        if "anthropic" in content:
            return "anthropic"
    return "langgraph"


@app.command("init")
def init_command() -> None:
    typer.echo("Initialize Apie")
    detected_framework = _detect_framework()

    name = typer.prompt("Agent name", default="Incident Remediation Agent").strip()
    if not name:
        raise typer.BadParameter("Agent name is required")
    key = typer.prompt("Agent key", default=_slugify(name)).strip()
    if not key:
        raise typer.BadParameter("Agent key is required")
    environment = typer.prompt("Environment", default="development").strip()
    framework = typer.prompt("Framework", default=detected_framework).strip()
    project_key = typer.prompt("Project key (from Apie dashboard)", hide_input=False).strip()
    if not project_key.startswith("apie_sk_"):
        raise typer.BadParameter("Enter a valid apie_sk_* project key")

    declare_now = typer.confirm("Do you want to declare expected tools now?", default=False)
    capabilities: list[dict[str, object]] = []
    while declare_now:
        tool_name = typer.prompt("Tool name").strip()
        provider = typer.prompt("Provider", default="internal").strip()
        actions = typer.prompt(
            "Actions (comma-separated: read/create/update/delete/execute/communicate)",
            default="read",
        )
        resources = typer.prompt("Resource types (comma-separated)", default="internal_api")
        risk_level = typer.prompt("Risk level", default="low")
        capabilities.append(
            {
                "tool": {"name": tool_name, "provider": provider},
                "actions": [a.strip() for a in actions.split(",") if a.strip()],
                "resources": [r.strip() for r in resources.split(",") if r.strip()],
                "risk_level": risk_level.strip(),
            }
        )
        declare_now = typer.confirm("Add another tool?", default=False)

    config_path = Path("apie.config.py")
    if config_path.exists() and not typer.confirm(
        "apie.config.py already exists. Overwrite?", default=False
    ):
        raise typer.Exit(1)

    capability_block = ""
    if capabilities:
        rendered = json.dumps(capabilities, indent=2)
        capability_block = f'\n        "capabilities": {rendered},'

    config_contents = f"""from apie import Apie

apie = Apie(
    {{
        "api_key": None,  # pulled from APIE_API_KEY
        "agent": {{
            "key": "{key}",
            "name": "{name}",
        }},
        "runtime": {{
            "environment": "{environment}",
            "framework": "{framework}",
            "language": "python",
        }},
        "release_mode": "monitor",{capability_block}
    }}
)
"""
    config_path.write_text(config_contents, encoding="utf-8")

    env_path = Path(".env")
    env_line = f"APIE_API_KEY={project_key}\nAPIE_BASE_URL=http://localhost:3000\n"
    if not env_path.exists():
        env_path.write_text(env_line, encoding="utf-8")

    env_example = Path(".env.example")
    if not env_example.exists():
        env_example.write_text(
            "APIE_API_KEY=apie_sk_test_...\nAPIE_BASE_URL=http://localhost:3000\n",
            encoding="utf-8",
        )

    typer.echo("Apie initialized")
    typer.echo("Import and initialize:")
    typer.echo("from apie.config import apie\napie.ready()")


@app.command("send-test-event")
def send_test_event_command(
    mode: str = typer.Option("pipeline", help="pipeline (default) or single"),
) -> None:
    normalized = "single" if mode == "single" else "pipeline"
    apie = Apie.create()
    registration = apie.ready()
    typer.echo(f"Sending test event for agent {registration.agent_id} ({normalized} mode)...")
    result = apie.send_test_event({"mode": normalized})
    apie.flush()
    apie.shutdown()
    typer.echo("Test event sent successfully.")
    typer.echo(f"Session: {result.session_id}")
    typer.echo(f"Runs: {', '.join(result.run_ids)}")
    typer.echo(
        f"Session replay: {registration.dashboard_url.rstrip('/')}/sessions/{result.session_id}"
    )
    typer.echo(f"Agent dashboard: {registration.dashboard_url}")


@app.command("doctor")
def doctor_command(
    send_test: bool = typer.Option(False, "--send-test", help="Send a test event after checks"),
) -> None:
    apie = Apie.create()
    try:
        diagnosis = apie.doctor()
        registration = diagnosis["registration"]
        queue = diagnosis["queue"]
        typer.echo("Apie doctor")
        typer.echo(f"Enabled: {'yes' if diagnosis['enabled'] else 'no'}")
        typer.echo(f"Base URL: {diagnosis['baseUrl']}")
        typer.echo(f"API key configured: {'yes' if diagnosis['apiKeyConfigured'] else 'no'}")
        typer.echo(f"Release mode: {diagnosis['releaseMode']}")
        typer.echo(f"Guard failure mode: {diagnosis['guardFailureMode']}")
        typer.echo(f"Runtime environment: {diagnosis['runtimeEnvironment'] or 'unset'}")
        typer.echo(f"Runtime framework: {diagnosis['runtimeFramework'] or 'unset'}")
        typer.echo(f"Queue storage path: {diagnosis['queueStoragePath'] or 'disabled'}")
        typer.echo(f"Redaction enabled: {'yes' if diagnosis['redactionEnabled'] else 'no'}")
        if registration:
            typer.echo(f"Agent ID: {registration.agent_id}")
            typer.echo(f"Workspace ID: {registration.workspace_id}")
            typer.echo(f"Dashboard URL: {registration.dashboard_url}")
            validation = apie.validate_events(
                {
                    "type": "agent.resource.touched",
                    "agentKey": "doctor_preview",
                    "action": {"type": "read", "name": "doctor_preview"},
                    "resource": {"type": "internal_api", "environment": "development"},
                }
            )
            previews = validation.get("previews", [])
            status = previews[0].get("validation_status") if previews else "unknown"
            typer.echo(f"Event validation preview: {status}")

        typer.echo(
            "Queue diagnostics: "
            f"size={queue.queue_size}, dropped={queue.dropped_count}, "
            f"deduplicated={queue.deduplicated_count}, flushes={queue.flush_count}, "
            f"retries={queue.retry_count}"
        )
        if queue.last_flush_at:
            typer.echo(f"Last successful flush at: {queue.last_flush_at}")
        if queue.last_error_at:
            suffix = f" ({queue.last_error_message})" if queue.last_error_message else ""
            typer.echo(f"Last queue error at: {queue.last_error_at}{suffix}")

        if send_test:
            typer.echo("Sending doctor test event...")
            result = apie.send_test_event({"mode": "pipeline"})
            typer.echo(f"Doctor test session: {result.session_id}")
            if registration:
                typer.echo(
                    f"Session replay: {registration.dashboard_url.rstrip('/')}/sessions/{result.session_id}"
                )
    finally:
        try:
            apie.flush()
        finally:
            apie.shutdown()


@capabilities_app.command("declare")
def capabilities_declare_command() -> None:
    file_config = load_apie_config()
    if not file_config or not file_config.capabilities:
        typer.echo("No capabilities found in apie.config.py/json")
        raise typer.Exit(0)

    apie = Apie.create()
    result = apie.declare_capabilities(file_config.capabilities)
    declared = result.get("declared", [])
    typer.echo(f"Declared {len(declared)} capabilities")


@guardrails_app.command("enable")
def guardrails_enable_command(
    key: str,
    mode: Optional[str] = typer.Option(None, help="monitor or enforce (informational)"),
) -> None:
    apie = Apie.create()
    result = apie.enable_guardrail_template(key)
    if mode == "monitor":
        typer.echo("Template enabled. Keep release_mode='monitor' to observe without blocking.")
    elif mode == "enforce":
        typer.echo("Set release_mode='guard' (or mode='enforce') in apie config to enforce.")
    typer.echo(f"Enabled {result.get('key', key)}")


@report_app.command("create")
def report_create_command(
    last: str = typer.Option("7d", "--last", help="Time window: 24h, 7d, or 30d"),
    environment: Optional[str] = typer.Option(None, "--environment"),
    title: Optional[str] = typer.Option(None, "--title"),
) -> None:
    apie = Apie.create()
    apie.ready()
    normalized = (last.replace("last_", "") if last else "7d").lower()
    if normalized not in {"24h", "7d", "30d"}:
        raise typer.BadParameter("last must be one of: 24h, 7d, 30d")
    window = cast(Literal["24h", "7d", "30d"], normalized)
    result = apie.reports.create(
        BoundaryReportCreateInput(
            title=title,
            window=window,
            environments=[environment] if environment else [],
        )
    )
    typer.echo("Agent Boundary Report generated.")
    typer.echo(f"Web report:\n{result.web_url}")
    if result.status == "draft":
        typer.echo("Waiting for report generation...")
        report = apie.reports.wait_until_ready(result.report_id)
        export_urls = report.get("export_urls") or {}
        if isinstance(export_urls, dict) and export_urls.get("json"):
            typer.echo(f"JSON export:\n{export_urls['json']}")
    apie.shutdown()
    typer.echo(f"Report {result.report_id}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
