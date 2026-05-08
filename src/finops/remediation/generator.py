"""RemediationGenerator — turns a Finding into a multi-format RemediationPlan.

The generator is intentionally **deterministic and offline**: it produces a
plan from the Finding + Resource without any network calls. The optional
`RemediatorAgent` enrichment runs *on top* of a plan generated here.

Public entrypoints:
- ``RemediationGenerator().build(finding, fmt) -> RemediationPlan`` (no DB write)
- ``build_plan(finding_id: int, fmt: str) -> dict`` (CLI / API; opens DB session)
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select

from finops.config import RemediationFormat
from finops.db.models import Finding, RemediationPlan, Resource
from finops.db.session import get_session, init_db
from finops.remediation.safety import SafetyGate
from finops.remediation.templates import render_template, short_id

# Blast radius mapping per resource type. Documented in BITACORA ADR-010.
BLAST_RADIUS_BY_TYPE: dict[str, str] = {
    "ebs": "low",
    "eip": "low",
    "ec2": "medium",
    "elb": "medium",
    "nat": "high",
    "rds": "high",
    "s3": "high",
}


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _build_context(resource: Resource, finding: Finding) -> dict[str, Any]:
    """Assemble template context from Resource + Finding attrs."""
    attrs = resource.attrs or {}
    az = str(attrs.get("availability_zone") or "")
    region = resource.region or (az[:-1] if len(az) > 1 and az[-1].isalpha() else "us-east-1")

    # Extract numeric size from usage_types if present, otherwise default
    size_gb = 100
    for ut in attrs.get("usage_types", []) or []:
        m = re.search(r"(\d+)\s*GB", str(ut))
        if m:
            size_gb = int(m.group(1))
            break

    # RDS: extract identifier from ARN
    rds_id = resource.resource_id.split(":")[-1] if "arn:aws:rds" in resource.resource_id else resource.resource_id

    return {
        "resource_id": resource.resource_id,
        "region": region,
        "az": az,
        "tf_id": short_id(resource.resource_id),
        "size_gb": size_gb,
        "rds_id": rds_id,
        "finding_id": finding.id,
        "savings_estimate": finding.savings_estimate,
        "instance_type": str(attrs.get("instance_type") or ""),
    }


def _render_human_summary(
    resource: Resource, finding: Finding, plan_body: str, blast_radius: str
) -> str:
    """Build the markdown header + body the operator reads. Body is the rendered template."""
    rollback_window = "30 days (snapshot retention)" if resource.type in ("ebs", "rds") else "24h (instance/AMI capture)"
    stakeholder_msg = (
        ":warning: FinOps action required — "
        f"`{resource.resource_id}` ({resource.type}, {resource.region or 'unknown region'}, "
        f"~${finding.savings_estimate:.2f}/mo)\n"
        f"*Rule:* {finding.rule_id}  ·  *Blast radius:* {blast_radius}  ·  *Confidence:* {finding.confidence:.2f}\n"
        f"*Plan:* see attached ({plan_body.split(chr(10))[0][:60]}...)\n"
        f"*Approval needed* from on-call before execute. *Rollback window:* {rollback_window}."
    )

    return (
        f"# Remediation Plan — {finding.rule_id}\n"
        f"**Resource:** `{resource.resource_id}` ({resource.type})\n"
        f"**Region/Account:** {resource.region or 'n/a'} / {resource.account_id or 'n/a'}\n"
        f"**Estimated savings:** ${finding.savings_estimate:.2f}/mo "
        f"(${finding.savings_estimate * 12:.2f}/yr)\n"
        f"**Blast radius:** {blast_radius}\n"
        f"**Rule confidence:** {finding.confidence:.2f}\n"
        f"**Generated:** {_utcnow_naive().isoformat(timespec='seconds')} UTC\n\n"
        "## Procedure\n\n"
        f"```{('bash' if 'cli' in plan_body[:80].lower() or '#' in plan_body[:5] else 'python')}\n"
        f"{plan_body.rstrip()}\n"
        "```\n\n"
        "## Rollback\n"
        f"{rollback_window}. Restore from the snapshot/AMI captured before deletion.\n\n"
        "## Stakeholder communication (Slack-ready)\n"
        f"> {stakeholder_msg}\n"
    )


class RemediationGenerator:
    """Produce a RemediationPlan for a given (Finding, Resource, format)."""

    def build(
        self,
        finding: Finding,
        resource: Resource,
        fmt: RemediationFormat = "aws_cli",
    ) -> RemediationPlan:
        if resource.type not in {"ebs", "ec2", "eip", "nat", "rds", "elb"}:
            raise ValueError(f"no remediation template for resource type: {resource.type!r}")

        context = _build_context(resource, finding)
        body = render_template(resource.type, fmt, context)
        blast_radius = BLAST_RADIUS_BY_TYPE.get(resource.type, "medium")

        rendered = _render_human_summary(resource, finding, body, blast_radius)

        commands = [line for line in body.splitlines() if line.strip() and not line.strip().startswith("#")]

        plan = RemediationPlan(
            finding_id=finding.id or 0,
            format=fmt,
            commands=commands,
            blast_radius=blast_radius,
            status="draft",
            rendered=rendered,
        )

        # Self-validate (sanity); a generator should never produce a plan that
        # fails its own safety check. Raises if it does.
        result = SafetyGate.validate(plan, allow_high_blast_radius=True)
        if result.violations:
            raise RuntimeError(
                f"Generator produced a plan that fails SafetyGate: "
                f"{[v.name for v in result.violations]}"
            )
        return plan


def build_plan(finding_id: int, fmt: str = "aws_cli") -> dict:
    """CLI / API entrypoint. Opens a DB session, builds the plan, persists, returns dict."""
    init_db()
    with get_session() as s:
        finding = s.exec(select(Finding).where(Finding.id == finding_id)).first()
        if finding is None:
            raise LookupError(f"finding_id={finding_id} not found")
        resource = s.exec(select(Resource).where(Resource.resource_id == finding.resource_id)).first()
        if resource is None:
            raise LookupError(
                f"resource for finding {finding_id} ({finding.resource_id}) not found"
            )

        plan = RemediationGenerator().build(finding, resource, fmt=fmt)
        s.add(plan)
        s.flush()

        return {
            "id": plan.id,
            "finding_id": plan.finding_id,
            "format": plan.format,
            "blast_radius": plan.blast_radius,
            "rendered": plan.rendered,
            "commands": plan.commands,
            "status": plan.status,
        }
