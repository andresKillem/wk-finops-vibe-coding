"""SQLModel models — the canonical data shape of the FinOps optimizer.

Five tables:
- BillingRecord    — one line-item from a billing export (insert-once, immutable)
- Resource         — canonical cloud resource, deduped across BillingRecords (upsert)
- Finding          — a detected waste/risk pattern attached to a Resource
- RemediationPlan  — a generated decommission plan for a Finding
- AgentRun         — audit trail of every LLM/agent invocation

All JSON fields use SQLAlchemy's ``JSON`` type so SQLite serialises automatically.
``utcnow()`` is used as the default for every timestamp; comparisons in detection rules
expect timezone-aware datetimes throughout.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Default timestamp factory — naive UTC.

    SQLite doesn't preserve tz info on roundtrip, and SQLAlchemy comparisons
    mix offset-naive/aware datetimes. We normalise to naive UTC throughout —
    the convention is documented; absence of tzinfo means "UTC" project-wide.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class BillingRecord(SQLModel, table=True):
    """A single line-item from an AWS CUR or Azure billing export.

    Records are insert-once. The ``raw_record`` column preserves the full source row
    verbatim so we never lose audit fidelity, even if upstream schemas change.
    """

    id: int | None = Field(default=None, primary_key=True)
    cloud_provider: str = Field(index=True, description="aws | azure")
    account_id: str = Field(default="", index=True)
    service: str = Field(default="", description="AmazonEC2, AmazonRDS, Microsoft.Compute, ...")
    resource_id: str = Field(index=True)
    region: str | None = Field(default=None, index=True)
    usage_amount: float = 0.0
    cost: float = 0.0
    period_start: datetime
    period_end: datetime
    raw_record: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Verbatim source row preserved for audit",
    )
    ingested_at: datetime = Field(default_factory=utcnow)


class Resource(SQLModel, table=True):
    """Canonical cloud resource — one row per ``resource_id`` regardless of how many
    billing line-items reference it. Upserted on every ingest.

    ``state`` defaults to ``unknown`` after pure ingestion; the detection engine
    flips it to ``orphaned`` / ``idle`` / ``active`` once rules run.
    """

    id: int | None = Field(default=None, primary_key=True)
    resource_id: str = Field(unique=True, index=True)
    type: str = Field(default="other", index=True, description="ebs|ec2|eip|nat|rds|elb|s3|other")
    state: str = Field(default="unknown", index=True, description="orphaned|idle|active|unknown")
    region: str | None = Field(default=None, index=True)
    account_id: str | None = Field(default=None, index=True)
    cloud_provider: str = Field(default="aws", index=True)
    last_seen: datetime = Field(default_factory=utcnow)
    monthly_cost: float = Field(default=0.0, description="Aggregated cost across BillingRecords")
    attrs: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("attrs", JSON, nullable=False),
        description="Free-form attributes — tags, instance_type, az, usage_types, etc.",
    )


class Finding(SQLModel, table=True):
    """A detected waste/risk pattern attached to a Resource.

    Rules emit Findings; the detection engine persists them. Each Finding is a
    candidate for one or more RemediationPlans.
    """

    id: int | None = Field(default=None, primary_key=True)
    resource_id: str = Field(foreign_key="resource.resource_id", index=True)
    rule_id: str = Field(index=True, description="R-EBS-001, R-EC2-001, ...")
    severity: str = Field(index=True, description="LOW|MEDIUM|HIGH")
    description: str = ""
    savings_estimate: float = Field(default=0.0, description="USD per month")
    risk_score: float = Field(default=0.0, description="0..100")
    confidence: float = Field(default=1.0, description="0..1")
    attrs: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("attrs", JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)


class RemediationPlan(SQLModel, table=True):
    """A generated decommission plan for a Finding.

    ``commands`` is the structured list (one entry per shell line / boto3 statement);
    ``rendered`` is the full text the user will see and approve.
    """

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int = Field(foreign_key="finding.id", index=True)
    format: str = Field(description="aws_cli|boto3|terraform_import")
    commands: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    blast_radius: str = Field(default="low", description="low|medium|high")
    status: str = Field(default="draft", description="draft|approved|executed|failed|rolled_back")
    rendered: str = Field(default="", description="Full rendered plan text for human review")
    created_at: datetime = Field(default_factory=utcnow, index=True)


class AgentRun(SQLModel, table=True):
    """Audit trail of every LLM/agent invocation.

    Captures prompt, response, tokens, model, latency, and a cost estimate so the
    architect can review *how the AI reasoned* turn-by-turn after the fact.
    """

    id: int | None = Field(default=None, primary_key=True)
    agent_name: str = Field(index=True, description="analyzer | remediator | reviewer | compliance")
    model: str = Field(description="claude-opus-4-7 | claude-haiku-4-5 | deterministic-fallback")
    prompt: str = ""
    response: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    cost_estimate: float = Field(default=0.0, description="USD; 0.0 for fallback path")
    created_at: datetime = Field(default_factory=utcnow, index=True)
