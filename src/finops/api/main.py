"""FastAPI application entrypoint.

Standard production shape:
- Request-ID middleware (added to every request + echoed in ``X-Request-ID``).
- Global exception handler (JSON shape with type, message, request_id).
- CORS open for dev — tighten before any production exposure.
- All routes mounted under tagged routers (visible in OpenAPI groupings).
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from finops import __version__
from finops.api.routes import alerts, analyze, health, remediate, report, upload

logger = logging.getLogger("finops.api")

app = FastAPI(
    title="Cloud Cost Optimizer",
    version=__version__,
    description=(
        "Wolters Kluwer 2026 Vibe Coding Challenge — Project 1.\n\n"
        "FastAPI surface for an architect-led, AI-engineered FinOps engine. "
        "Ingests AWS CUR / Azure billing exports, detects orphaned/idle resources "
        "via 7 declarative rules, generates safe multi-format remediation plans, "
        "and exposes the same engine as an MCP server.\n\n"
        "**Demo flow:** `POST /upload` → `POST /analyze` → `GET /report` → "
        "`POST /remediate/{finding_id}`."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — wide open for dev. Tighten via env in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id_and_timing(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Attach a request_id, time the request, log on exit."""
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    response.headers["X-Request-ID"] = rid
    logger.info(
        "%s %s -> %s (%.1f ms) rid=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        rid,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler returning a structured JSON error."""
    rid = getattr(request.state, "request_id", None)
    logger.exception("unhandled exception rid=%s", rid)
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
            "request_id": rid,
        },
    )


# Routers
app.include_router(health.router, tags=["health"])
app.include_router(upload.router, prefix="/upload", tags=["ingestion"])
app.include_router(analyze.router, prefix="/analyze", tags=["detection"])
app.include_router(remediate.router, prefix="/remediate", tags=["remediation"])
app.include_router(report.router, prefix="/report", tags=["report"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "Cloud Cost Optimizer",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
