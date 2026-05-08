"""Health + readiness checks.

`/health` is a process-liveness probe — always returns 200 if the app is up.
`/ready` exercises the DB so a load balancer can route around a broken instance.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from finops import __version__
from finops.api.schemas import HealthResponse, ReadyResponse
from finops.config import settings
from finops.db.session import engine

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="finops-cost-optimizer",
        version=__version__,
        llm_enabled=settings.llm_enabled,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return ReadyResponse(status="ready", db_ok=True)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "not ready", "db_ok": False, "error": str(e)},
        )
