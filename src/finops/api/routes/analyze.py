"""POST /analyze — run the detection engine against currently-ingested data.

If the resulting overall_risk crosses the env-configured threshold, fires
the webhook simulator with the aggregate payload.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from finops.api.schemas import (
    CategoryAggregate,
    FindingOut,
    ScanResultOut,
    TopOffender,
)
from finops.api.webhooks import WebhookEmitter
from finops.config import settings
from finops.detection.engine import run_scan

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=ScanResultOut, summary="Run detection rules + score")
async def analyze() -> ScanResultOut:
    result = run_scan()
    agg = result.aggregate

    if agg["overall_risk"] >= settings.risk_threshold:
        # Best-effort fire-and-forget; we log but do not fail the response.
        try:
            await WebhookEmitter().send("risk_threshold_exceeded", agg)
        except Exception as e:  # noqa: BLE001
            logger.warning("webhook emit failed: %s", e)

    return ScanResultOut(
        resources_evaluated=result.resources_evaluated,
        rules_evaluated=result.rules_evaluated,
        total_monthly_waste=agg["total_monthly_waste"],
        annual_projection=agg["annual_projection"],
        overall_risk=agg["overall_risk"],
        calibration_label=agg["calibration_label"],
        findings_count=agg["findings_count"],
        by_severity=agg["by_severity"],
        by_category={k: CategoryAggregate(**v) for k, v in agg["by_category"].items()},
        top_5_offenders=[TopOffender(**o) for o in agg["top_5_offenders"]],
        findings=[
            FindingOut(
                id=f.id,
                rule_id=f.rule_id,
                resource_id=f.resource_id,
                severity=f.severity,
                savings_estimate=f.savings_estimate,
                risk_score=f.risk_score,
                confidence=f.confidence,
                description=f.description,
            )
            for f in result.findings
        ],
    )
