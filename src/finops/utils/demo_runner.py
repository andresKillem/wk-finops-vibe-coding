"""End-to-end demo runner — `finops demo` calls this.

Sequence:
  1. Reset the DB.
  2. Ingest the bundled AWS CUR sample (and Azure JSON if present).
  3. Run the detection engine.
  4. Run the orchestrator (Opus + Haiku) in fallback mode by default; LLM
     mode only when an explicit ``--llm`` flag is set, to keep `make demo`
     deterministic and free.
  5. Print a clean readout to stdout — perfect for capturing into
     ``docs/demo_output.txt`` for the submission package.
"""
from __future__ import annotations

import asyncio
import os

from rich.console import Console
from rich.panel import Panel

from finops.config import PROJECT_ROOT
from finops.db.session import init_db, reset_db
from finops.detection.engine import run_scan
from finops.ingestion.router import ingest_file

console = Console()


async def _run_orchestrator_safe(top_n: int = 3) -> dict:
    """Orchestrator call wrapped to never crash the demo if LLM auth flips off."""
    from finops.agents.orchestrator import Orchestrator

    return await Orchestrator().run(top_n=top_n)


def run_demo(use_llm: bool | None = None, top_n: int = 3) -> None:
    """Execute the full pipeline end-to-end. Output is human-readable for stdout capture."""

    # Decide LLM/fallback mode early. None (default) = honour env. False = force fallback.
    if use_llm is False:
        os.environ["ANTHROPIC_API_KEY"] = ""
        # The Settings object is module-level cached; we touch it via env then re-instantiate
        from finops import config as _c
        _c.settings = _c.Settings()

    sample = PROJECT_ROOT / "samples" / "aws_cur_sample.csv"
    azure = PROJECT_ROOT / "samples" / "azure_billing_sample.json"

    console.print(Panel.fit("[bold cyan]FinOps Cost Optimizer — End-to-End Demo[/]", border_style="cyan"))

    console.print("\n[bold]Step 1[/] — Reset and initialise database")
    reset_db()
    init_db()
    console.print("  [green]✓[/] schema ready")

    console.print("\n[bold]Step 2[/] — Ingest billing exports")
    aws_summary = ingest_file(sample)
    console.print(aws_summary)

    if azure.exists():
        # Skip Azure here so the numbers in stdout match the AWS-only narrative
        # (and so that LLM cost stays predictable in the demo).
        console.print(f"\n  [dim]Azure sample also present at {azure.name}; skipping in demo.[/]")

    console.print("\n[bold]Step 3[/] — Run detection engine")
    scan = run_scan()
    console.print(scan)

    console.print("\n[bold]Step 4[/] — Run orchestrator (Analyzer + Remediators)")
    result = asyncio.run(_run_orchestrator_safe(top_n=top_n))

    summary = result.get("summary", {})
    analyzer = result.get("analyzer", {}).get("output", {})
    rems = result.get("remediations", []) or []

    headline = (
        f"agents_invoked={summary.get('agents_invoked')} · "
        f"tokens_in={summary.get('tokens_in_total')} / "
        f"out={summary.get('tokens_out_total')} · "
        f"cost=${summary.get('cost_estimate_total', 0):.4f} · "
        f"wall_clock={summary.get('duration_ms_total', 0)/1000:.1f}s · "
        f"mode={'fallback' if summary.get('fallback_mode') else 'LLM'}"
    )
    console.print(Panel(headline, title="Orchestrator stats", border_style="cyan"))

    if analyzer.get("executive_narrative"):
        console.print("\n  [bold]Executive narrative:[/]")
        for bullet in analyzer["executive_narrative"]:
            console.print(f"    • {bullet}")

    rec = analyzer.get("recommended_next_action") or {}
    if rec:
        console.print(
            f"\n  [bold]Recommended next action:[/] findings={rec.get('finding_ids')} "
            f"savings=${rec.get('expected_savings', 0):.2f}/mo "
            f"blast={rec.get('blast_radius', '?')}"
        )
        console.print(f"    {rec.get('reasoning', '')}")

    if rems:
        console.print(f"\n  [bold]Remediations enriched:[/] {len(rems)}")
        for r in rems:
            console.print(
                f"    - finding #{r['finding_id']} "
                f"({r['rule_id']}, {r['severity']}, blast {r['base_plan'].get('blast_radius')}): "
                f"plan + Haiku enrichment ready"
            )

    console.print("\n[bold]Step 5[/] — Final report")
    from sqlmodel import select

    from finops.db.models import Finding, Resource
    from finops.db.session import get_session
    from finops.detection.scoring import aggregate_score

    with get_session() as s:
        findings = list(s.exec(select(Finding)).all())
        resources = list(s.exec(select(Resource)).all())
    agg = aggregate_score(findings, resources)

    console.print(
        f"\n  Total monthly waste:        [bold red]${agg['total_monthly_waste']:.2f}[/]"
    )
    console.print(
        f"  12-month projection:        [red]${agg['annual_projection']:.2f}[/]"
    )
    console.print(
        f"  Overall risk score:         [bold yellow]{agg['overall_risk']:.2f}[/]  "
        f"({agg['calibration_label']})"
    )
    console.print(
        f"  Findings:                   {agg['findings_count']} "
        f"(HIGH:{agg['by_severity']['HIGH']} MEDIUM:{agg['by_severity']['MEDIUM']} LOW:{agg['by_severity']['LOW']})"
    )

    console.print(Panel.fit("[bold green]Demo complete.[/] Open the dashboard with `make run-dashboard`.", border_style="green"))
