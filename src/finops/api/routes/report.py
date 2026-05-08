"""GET /report — current findings aggregate (no re-scan).

Use `POST /analyze` to recompute. `/report` reads the persisted Findings.
"""
from __future__ import annotations

from fastapi import APIRouter
from sqlmodel import select

from finops.api.schemas import CategoryAggregate, ReportOut, TopOffender
from finops.db.models import Finding, Resource
from finops.db.session import get_session
from finops.detection.scoring import aggregate_score

router = APIRouter()


@router.get("", response_model=ReportOut, summary="Current findings aggregate")
async def report() -> ReportOut:
    with get_session() as s:
        findings = list(s.exec(select(Finding)).all())
        resources = list(s.exec(select(Resource)).all())
    agg = aggregate_score(findings, resources)
    return ReportOut(
        total_monthly_waste=agg["total_monthly_waste"],
        annual_projection=agg["annual_projection"],
        overall_risk=agg["overall_risk"],
        calibration_label=agg["calibration_label"],
        findings_count=agg["findings_count"],
        by_severity=agg["by_severity"],
        by_category={k: CategoryAggregate(**v) for k, v in agg["by_category"].items()},
        top_5_offenders=[TopOffender(**o) for o in agg["top_5_offenders"]],
    )
