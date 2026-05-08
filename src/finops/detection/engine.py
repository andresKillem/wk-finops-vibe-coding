"""DetectionEngine — orchestrates rule fan-out, persistence, and aggregation.

Single public entrypoint: ``run_scan()`` (used by CLI / API / MCP). The engine
deletes prior Findings before each scan so re-scanning produces fresh, current
state — never accumulating stale signal.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import delete
from sqlmodel import Session, select

from finops.db.models import BillingRecord, Finding, Resource
from finops.db.session import get_session, init_db
from finops.detection.aws_rules import ALL_AWS_RULES
from finops.detection.rules import DetectionRule
from finops.detection.scoring import aggregate_score, risk_score


@dataclass
class ScanResult:
    """Renderable result of a scan. Used by CLI rich panel and API JSON."""

    findings: list[Finding] = field(default_factory=list)
    resources_evaluated: int = 0
    rules_evaluated: int = 0
    aggregate: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "resources_evaluated": self.resources_evaluated,
            "rules_evaluated": self.rules_evaluated,
            **self.aggregate,
            "findings": [
                {
                    "id": f.id,
                    "rule_id": f.rule_id,
                    "resource_id": f.resource_id,
                    "severity": f.severity,
                    "savings_estimate": f.savings_estimate,
                    "risk_score": f.risk_score,
                    "confidence": f.confidence,
                    "description": f.description,
                }
                for f in self.findings
            ],
        }

    def __rich_console__(self, console, options):  # rich protocol
        from rich.panel import Panel
        from rich.table import Table

        agg = self.aggregate

        # Headline panel
        head = Table(show_header=False, box=None, expand=False)
        head.add_column(style="bold cyan", width=22)
        head.add_column()
        head.add_row("Total monthly waste", f"[bold red]${agg['total_monthly_waste']:.2f}[/]")
        head.add_row("Annual projection", f"[red]${agg['annual_projection']:.2f}[/]")
        head.add_row(
            "Overall risk score",
            f"[bold]{agg['overall_risk']:.2f}[/] · [yellow]{agg['calibration_label']}[/]",
        )
        head.add_row("Findings", f"{agg['findings_count']} (HIGH:{agg['by_severity']['HIGH']} MEDIUM:{agg['by_severity']['MEDIUM']} LOW:{agg['by_severity']['LOW']})")
        head.add_row("Resources evaluated", str(self.resources_evaluated))
        head.add_row("Rules evaluated", str(self.rules_evaluated))
        yield Panel(head, title="Detection Scan", border_style="cyan")

        # Top offenders
        if agg["top_5_offenders"]:
            t = Table(title="Top 5 offenders by risk_score", show_lines=False)
            t.add_column("rule_id", style="bold")
            t.add_column("resource_id", overflow="fold", max_width=44)
            t.add_column("severity")
            t.add_column("$/mo", justify="right", style="red")
            t.add_column("risk", justify="right", style="bold yellow")
            for o in agg["top_5_offenders"]:
                sev_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "blue"}.get(
                    o["severity"], "white"
                )
                t.add_row(
                    o["rule_id"],
                    o["resource_id"],
                    f"[{sev_color}]{o['severity']}[/]",
                    f"{o['savings_per_month']:.2f}",
                    f"{o['risk_score']:.2f}",
                )
            yield t

        # By category
        if agg["by_category"]:
            cat = Table(title="By resource category", show_lines=False)
            cat.add_column("category", style="bold")
            cat.add_column("count", justify="right")
            cat.add_column("total $/mo", justify="right", style="red")
            cat.add_column("max risk", justify="right", style="yellow")
            for c, d in sorted(agg["by_category"].items(), key=lambda kv: -kv[1]["total_savings"]):
                cat.add_row(c, str(d["count"]), f"{d['total_savings']:.2f}", f"{d['max_risk']:.2f}")
            yield cat


class DetectionEngine:
    """Apply a set of DetectionRules to all Resources in the DB."""

    def __init__(self, rules: list[DetectionRule] | None = None) -> None:
        if rules is None:
            rules = [cls() for cls in ALL_AWS_RULES]
        self.rules = rules

    def scan(self, session: Session) -> ScanResult:
        """Re-scan: delete prior Findings, fan out rules over Resources, persist."""
        # Wipe prior findings & remediation plans (cascades not configured; do explicitly)
        from finops.db.models import RemediationPlan

        session.exec(delete(RemediationPlan))
        session.exec(delete(Finding))

        resources = list(session.exec(select(Resource)).all())
        new_findings: list[Finding] = []
        for r in resources:
            billing = list(
                session.exec(select(BillingRecord).where(BillingRecord.resource_id == r.resource_id)).all()
            )
            for rule in self.rules:
                f = rule.evaluate(r, billing)
                if f is None:
                    continue
                f.risk_score = risk_score(f)
                # Update Resource state (best-effort)
                if r.state == "unknown" and rule.severity == "HIGH":
                    r.state = "orphaned" if "orphan" in rule.rule_id.lower() else "idle"
                session.add(f)
                new_findings.append(f)

        session.flush()  # assigns IDs to findings

        agg = aggregate_score(new_findings, resources)

        return ScanResult(
            findings=new_findings,
            resources_evaluated=len(resources),
            rules_evaluated=len(self.rules),
            aggregate=agg,
        )


def run_scan() -> ScanResult:
    """Convenience: open a session, scan, commit."""
    init_db()
    eng = DetectionEngine()
    with get_session() as s:
        return eng.scan(s)
