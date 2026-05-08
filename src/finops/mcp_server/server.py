"""FinOps MCP server.

Exposes the cost optimizer's capabilities as MCP tools / resources / prompts so
**any MCP-aware client** (Claude Desktop, Claude Code, Cursor, custom agents)
can use the same engine that powers the FastAPI surface.

Default transport: ``stdio`` (most portable; standard for desktop clients).
HTTP mode (``--http``) binds streamable-http on ``MCP_HTTP_PORT`` for
inspection / curl-based testing.

Why ship this alongside the FastAPI app: see BITACORA ADR-014.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from sqlmodel import select

from finops.config import settings
from finops.db.models import AgentRun, Finding, Resource
from finops.db.session import get_session, init_db

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "finops-cost-optimizer",
    instructions=(
        "FinOps cost optimizer. Ingest AWS Cost & Usage Reports or Azure billing "
        "exports, detect orphaned/idle resources via 7 declarative rules, "
        "generate safe multi-format decommission plans (aws_cli / boto3 / "
        "terraform_import), and run Opus + Haiku sub-agents for executive "
        "narrative + remediation enrichment. All operations are idempotent and "
        "never auto-execute destructive commands."
    ),
)


# ─── Tools ────────────────────────────────────────────────────────────────────
@mcp.tool()
def ingest_billing(file_path: str) -> dict[str, Any]:
    """Ingest an AWS CUR (CSV) or Azure billing (JSON) export into the local DB.

    Args:
        file_path: absolute or relative path to the billing file.

    Returns:
        IngestSummary as a dict (provider, rows_parsed, resources_upserted, errors, ...).
    """
    init_db()
    from finops.ingestion.router import ingest_file

    summary = ingest_file(file_path)
    return summary.to_dict()


@mcp.tool()
async def analyze_billing(top_n: int = 5) -> dict[str, Any]:
    """Run the detection engine + Opus/Haiku sub-agent orchestrator.

    Args:
        top_n: how many top-risk findings to enrich with the Remediator agent.

    Returns:
        Full orchestration result (analyzer narrative + per-finding remediations + summary).
    """
    init_db()
    from finops.agents.orchestrator import Orchestrator
    from finops.detection.engine import run_scan

    run_scan()
    return await Orchestrator().run(top_n=top_n)


@mcp.tool()
def propose_remediation(
    finding_id: int,
    format: Literal["aws_cli", "boto3", "terraform_import"] = "aws_cli",
) -> dict[str, Any]:
    """Generate a safe multi-format remediation plan for a single finding.

    Args:
        finding_id: ID of the finding (visible in /report or finops://findings).
        format: one of ``aws_cli`` (default), ``boto3``, ``terraform_import``.

    Returns:
        RemediationPlan dict with ``commands``, ``blast_radius``, full ``rendered`` markdown.
    """
    init_db()
    from finops.remediation.generator import build_plan

    return build_plan(finding_id=finding_id, fmt=format)


@mcp.tool()
def estimate_savings() -> dict[str, Any]:
    """Aggregate savings potential across all current findings.

    Returns:
        ``total_monthly_waste``, ``annual_projection``, ``overall_risk``,
        ``calibration_label``, ``by_category``, ``by_severity``, ``top_5_offenders``.
    """
    init_db()
    from finops.detection.scoring import aggregate_score

    with get_session() as s:
        findings = list(s.exec(select(Finding)).all())
        resources = list(s.exec(select(Resource)).all())
    return aggregate_score(findings, resources)


@mcp.tool()
def list_findings(severity: str = "", limit: int = 50) -> list[dict[str, Any]]:
    """List current findings, optionally filtered by severity. Returns id-keyed dicts."""
    init_db()
    with get_session() as s:
        stmt = select(Finding).order_by(Finding.risk_score.desc()).limit(limit)
        if severity:
            stmt = stmt.where(Finding.severity == severity.upper())
        rows = list(s.exec(stmt).all())
    return [
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
        for f in rows
    ]


# ─── Resources ────────────────────────────────────────────────────────────────
@mcp.resource("finops://findings")
def findings_resource() -> str:
    """Current findings as a JSON string. Read this to reason over the raw set."""
    init_db()
    with get_session() as s:
        rows = list(s.exec(select(Finding).order_by(Finding.risk_score.desc())).all())
    payload = [
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
        for f in rows
    ]
    return json.dumps(payload, indent=2)


@mcp.resource("finops://agent-runs")
def agent_runs_resource() -> str:
    """Recent AgentRun audit entries — what the LLM did, how much it cost, how long it took."""
    init_db()
    with get_session() as s:
        rows = list(s.exec(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(50)).all())
    payload = [
        {
            "agent_name": r.agent_name,
            "model": r.model,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "duration_ms": r.duration_ms,
            "cost_estimate": r.cost_estimate,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return json.dumps(payload, indent=2)


# ─── Prompts ──────────────────────────────────────────────────────────────────
@mcp.prompt()
def finops_audit(
    file_path: str = "samples/aws_cur_sample.csv",
    audience: str = "exec",
) -> str:
    """Pre-templated audit-style prompt the orchestrator (or any agent) can act on.

    Args:
        file_path: billing file to ingest. Can be a synthetic sample or a real export.
        audience: ``exec`` (executive readout) | ``engineer`` (commands-first) |
                  ``compliance`` (tag/ownership-aware).
    """
    audience_guide = {
        "exec": (
            "Focus on dollars, percentage of total spend, and the organisational "
            "story behind the waste. 3-bullet narrative; no command listings."
        ),
        "engineer": (
            "Focus on the top 5 actionable findings with copy-pasteable commands. "
            "Lead with the lowest-blast-radius high-impact win."
        ),
        "compliance": (
            "Focus on tag/ownership gaps that block remediation. Flag any prod-tagged "
            "resource recommended for decommission as needs-owner-confirm."
        ),
    }.get(audience, "Provide a balanced engineering + financial readout.")

    return (
        f"Run a complete FinOps audit:\n\n"
        f"1. Call `ingest_billing(file_path={file_path!r})` to load the data.\n"
        f"2. Call `analyze_billing(top_n=5)` to run detection + sub-agent orchestrator.\n"
        f"3. For each top-3 finding, call `propose_remediation(finding_id=X, format='aws_cli')` "
        f"to surface the actual decommission commands.\n"
        f"4. Call `estimate_savings()` to obtain the aggregate savings number.\n\n"
        f"Audience for the readout: **{audience}**.\n"
        f"Style guidance: {audience_guide}"
    )


# ─── Entrypoint ───────────────────────────────────────────────────────────────
def run_server(http: bool = False) -> None:
    """Start the MCP server. ``http=True`` uses streamable-http; default is stdio."""
    if http:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = settings.mcp_http_port
        logger.info("starting MCP server (streamable-http) on :%s", settings.mcp_http_port)
        mcp.run(transport="streamable-http")
    else:
        logger.info("starting MCP server (stdio)")
        mcp.run()


if __name__ == "__main__":
    import sys

    run_server(http="--http" in sys.argv)
