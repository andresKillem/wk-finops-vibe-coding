"""POST /agents/analyze — orchestrator end-to-end (Analyzer + parallel Remediators).

Returns the structured Analyzer output (executive narrative, top_5, root-cause
groupings, recommended_next_action) plus per-top-finding remediator enrichment.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlmodel import select

from finops.agents.orchestrator import Orchestrator
from finops.db.models import AgentRun
from finops.db.session import get_session

router = APIRouter()


@router.post("/analyze", summary="Run Opus analyzer + parallel Haiku remediators")
async def analyze_with_agents(
    top_n: int = Query(5, ge=1, le=10, description="How many findings to enrich with Remediator"),
    fmt: str = Query(
        "aws_cli",
        pattern="^(aws_cli|boto3|terraform_import)$",
        description="Format for the base plan that Remediator enriches",
    ),
) -> dict:
    return await Orchestrator().run(top_n=top_n, fmt=fmt)


@router.get("/runs", summary="Recent AgentRun audit entries")
async def recent_runs(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    """Return the most-recent AgentRun rows. Useful for the System dashboard page."""
    with get_session() as s:
        rows = list(
            s.exec(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)).all()
        )
    return [
        {
            "id": r.id,
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
