"""POST /remediate/{finding_id} — generate a multi-format remediation plan."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from finops.api.schemas import RemediationPlanOut
from finops.remediation.generator import build_plan

router = APIRouter()


@router.post("/{finding_id}", response_model=RemediationPlanOut, summary="Generate a remediation plan")
async def remediate(
    finding_id: int,
    fmt: str = Query("aws_cli", pattern="^(aws_cli|boto3|terraform_import)$", description="Output format"),
) -> RemediationPlanOut:
    try:
        out = build_plan(finding_id=finding_id, fmt=fmt)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return RemediationPlanOut(**out)
