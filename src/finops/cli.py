"""Typer-based CLI entry point. `finops <subcommand>`.

Subcommands are intentionally thin — they call into the relevant module so the
behavior is identical whether invoked via CLI, FastAPI, or MCP server.
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from finops import __version__
from finops.config import settings

app = typer.Typer(
    name="finops",
    help="Cloud Cost Optimizer & Remediation Engine — Wolters Kluwer 2026 Vibe Coding Challenge.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


@app.command()
def version() -> None:
    """Print the package version."""
    console.print(f"finops [bold cyan]{__version__}[/]")


@app.command("init-db")
def init_db_cmd() -> None:
    """Initialize the SQLite schema. Idempotent."""
    # Import is local to avoid loading the data layer for `finops version`.
    from finops.db.session import init_db

    init_db()
    console.print("[green]✓[/] Database schema initialized at [cyan]" + settings.database_url + "[/]")


@app.command()
def ingest(path: Path = typer.Argument(..., exists=True, help="Path to AWS CUR CSV or Azure billing JSON")) -> None:
    """Ingest a billing file into the local database."""
    from finops.ingestion.router import ingest_file

    summary = ingest_file(path)
    console.print(summary)


@app.command()
def scan() -> None:
    """Run the detection rules engine against ingested data."""
    from finops.detection.engine import run_scan

    result = run_scan()
    console.print(result)


@app.command()
def analyze() -> None:
    """Run the sub-agent orchestrator (Analyzer + Remediator) against current findings."""
    from finops.agents.orchestrator import run_orchestrator

    result = run_orchestrator()
    console.print(result)


@app.command()
def plan(
    finding_id: int = typer.Option(..., "--finding-id", help="Finding to remediate"),
    fmt: str = typer.Option("aws_cli", "--format", help="aws_cli | boto3 | terraform_import"),
) -> None:
    """Generate a remediation plan for a single finding."""
    from finops.remediation.generator import build_plan

    rendered = build_plan(finding_id=finding_id, fmt=fmt)
    console.print(rendered)


@app.command()
def demo() -> None:
    """End-to-end demo: ingest sample → scan → analyze → report."""
    from finops.utils.demo_runner import run_demo

    run_demo()


@app.command()
def serve(host: str = settings.api_host, port: int = settings.api_port) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("finops.api.main:app", host=host, port=port, reload=True)


@app.command()
def dashboard() -> None:
    """Start the Streamlit dashboard."""
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "src/finops/dashboard/app.py", "--server.port", str(settings.dashboard_port)],
        check=False,
    )


@app.command()
def mcp(http: bool = typer.Option(False, "--http", help="Use HTTP transport instead of stdio")) -> None:
    """Start the MCP server (stdio default; --http for inspection)."""
    from finops.mcp_server.server import run_server

    run_server(http=http)


@app.command()
def status() -> None:
    """Print session telemetry: elapsed, prompts, findings, agent runs."""
    from finops.utils.status import render_status

    console.print(render_status())


if __name__ == "__main__":
    app()
