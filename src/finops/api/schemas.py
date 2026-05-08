"""Pydantic IO schemas for the public API.

Why these are separate from SQLModel ``models``: see BITACORA ADR-011.
TL;DR — the wire shape and the storage shape have different lifecycles.
A breaking change to the DB shouldn't break our consumers; an API field
addition shouldn't require a DB migration.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ─── Ingestion ────────────────────────────────────────────────────────────────
class IngestSummaryOut(BaseModel):
    file: str
    provider: str
    rows_parsed: int
    skipped: int
    resources_upserted: int
    period_start: str | None = None
    period_end: str | None = None
    errors: list[str] = Field(default_factory=list)


# ─── Detection ────────────────────────────────────────────────────────────────
class FindingOut(BaseModel):
    id: int | None = None
    rule_id: str
    resource_id: str
    severity: str
    savings_estimate: float
    risk_score: float
    confidence: float
    description: str


class CategoryAggregate(BaseModel):
    count: int
    total_savings: float
    max_risk: float


class TopOffender(BaseModel):
    finding_id: int | None = None
    rule_id: str
    resource_id: str
    severity: str
    savings_per_month: float
    risk_score: float
    description: str


class ScanResultOut(BaseModel):
    resources_evaluated: int
    rules_evaluated: int
    total_monthly_waste: float
    annual_projection: float
    overall_risk: float
    calibration_label: str
    findings_count: int
    by_severity: dict[str, int]
    by_category: dict[str, CategoryAggregate]
    top_5_offenders: list[TopOffender]
    findings: list[FindingOut]


# ─── Remediation ──────────────────────────────────────────────────────────────
class RemediationPlanOut(BaseModel):
    id: int | None = None
    finding_id: int
    format: str = Field(description="aws_cli | boto3 | terraform_import")
    blast_radius: str = Field(description="low | medium | high")
    status: str = Field(default="draft")
    rendered: str = Field(description="Full markdown plan for human review")
    commands: list[str] = Field(default_factory=list)


class RemediateRequest(BaseModel):
    format: str = Field(default="aws_cli", pattern="^(aws_cli|boto3|terraform_import)$")
    allow_high_blast_radius: bool = False


# ─── Reports ──────────────────────────────────────────────────────────────────
class ReportOut(BaseModel):
    total_monthly_waste: float
    annual_projection: float
    overall_risk: float
    calibration_label: str
    findings_count: int
    by_severity: dict[str, int]
    by_category: dict[str, CategoryAggregate] = Field(default_factory=dict)
    top_5_offenders: list[TopOffender] = Field(default_factory=list)


# ─── Webhooks / alerts ────────────────────────────────────────────────────────
class WebhookResult(BaseModel):
    sent: bool
    status_code: int | None = None
    error: str | None = None
    attempts: int
    url: str


class AlertEcho(BaseModel):
    """Shape returned by the self-loopback /alert-sink endpoint for demo."""

    received: bool
    event_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ─── Health ───────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    llm_enabled: bool


class ReadyResponse(BaseModel):
    status: str
    db_ok: bool
    error: str | None = None
