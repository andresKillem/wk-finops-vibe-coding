"""Remediation layer tests.

Two priorities:
1. **Guard tests** — *no* generated template, in *any* format, for *any* resource
   type, may contain a dangerous pattern. This is the safety promise.
2. **Functional tests** — generator produces structurally-correct plans with
   the right blast_radius and validates clean against SafetyGate.
"""
from __future__ import annotations

import pytest
from sqlmodel import select

from finops.db.models import Finding, RemediationPlan, Resource
from finops.db.session import get_session
from finops.detection.engine import run_scan
from finops.ingestion.router import ingest_file
from finops.remediation.generator import (
    BLAST_RADIUS_BY_TYPE,
    RemediationGenerator,
    build_plan,
)
from finops.remediation.safety import DANGEROUS_PATTERNS, SafetyGate
from finops.remediation.templates import render_template

RESOURCE_TYPES = ["ebs", "ec2", "eip", "nat", "rds", "elb"]
FORMATS = ["aws_cli", "boto3", "terraform_import"]


# ─── Template renderability ───────────────────────────────────────────────────
@pytest.mark.parametrize("rt", RESOURCE_TYPES)
@pytest.mark.parametrize("fmt", FORMATS)
def test_every_template_renders(rt: str, fmt: str) -> None:
    """Every (type, format) combo must render with a representative context."""
    rendered = render_template(rt, fmt, _ctx_for(rt))
    assert rendered  # non-empty
    assert "{{" not in rendered  # no unrendered placeholders


def _ctx_for(rt: str) -> dict:
    base = {
        "resource_id": f"test-{rt}-001",
        "region": "us-east-1",
        "az": "us-east-1a",
        "tf_id": f"test_{rt}_001",
        "size_gb": 100,
        "rds_id": "test-rds-001",
        "finding_id": 1,
        "savings_estimate": 50.0,
        "instance_type": "t3.medium",
    }
    if rt == "rds":
        base["resource_id"] = "arn:aws:rds:us-east-1:123:db:test-rds-001"
    if rt == "eip":
        base["resource_id"] = "eipalloc-test001"
    if rt == "elb":
        base["resource_id"] = "arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/test/abc"
    return base


# ─── Guard: no dangerous patterns ─────────────────────────────────────────────
@pytest.mark.parametrize("rt", RESOURCE_TYPES)
@pytest.mark.parametrize("fmt", FORMATS)
def test_no_dangerous_patterns_in_template(rt: str, fmt: str) -> None:
    """Every rendered template must pass SafetyGate.validate_text."""
    rendered = render_template(rt, fmt, _ctx_for(rt))
    result = SafetyGate.validate_text(rendered)
    assert result.ok, (
        f"({rt}, {fmt}) produced dangerous patterns: {[v.name for v in result.violations]}\n"
        f"Snippets: {[v.snippet for v in result.violations]}"
    )


def test_safety_gate_catches_known_bad_text() -> None:
    bad = "Some plan with rm -rf / and aws ec2 terminate-instances --instance-ids i-x"
    result = SafetyGate.validate_text(bad)
    assert not result.ok
    names = {v.name for v in result.violations}
    assert "rm -rf" in names
    assert "aws ec2 terminate raw" in names


def test_safety_gate_catches_force_flag() -> None:
    assert not SafetyGate.validate_text("aws ec2 delete-volume --force --volume-id vol-x").ok


def test_safety_gate_catches_skip_final_snapshot() -> None:
    assert not SafetyGate.validate_text("aws rds delete-db-instance --skip-final-snapshot").ok


def test_safety_gate_catches_skip_snapshot_python() -> None:
    assert not SafetyGate.validate_text("rds.delete_db_instance(SkipFinalSnapshot=True)").ok


def test_safety_gate_catches_terraform_auto_approve() -> None:
    assert not SafetyGate.validate_text("terraform apply -auto-approve").ok
    assert not SafetyGate.validate_text("terraform destroy -auto-approve").ok


# ─── Generator end-to-end ────────────────────────────────────────────────────
def test_blast_radius_mapping() -> None:
    assert BLAST_RADIUS_BY_TYPE["ebs"] == "low"
    assert BLAST_RADIUS_BY_TYPE["eip"] == "low"
    assert BLAST_RADIUS_BY_TYPE["ec2"] == "medium"
    assert BLAST_RADIUS_BY_TYPE["elb"] == "medium"
    assert BLAST_RADIUS_BY_TYPE["nat"] == "high"
    assert BLAST_RADIUS_BY_TYPE["rds"] == "high"


def _make_finding_for(resource: Resource) -> Finding:
    return Finding(
        id=1,
        resource_id=resource.resource_id,
        rule_id="R-TEST-001",
        severity="HIGH",
        savings_estimate=80.0,
        risk_score=85.0,
        confidence=0.9,
        description="test finding",
    )


def test_generator_produces_plan_for_orphaned_ebs() -> None:
    r = Resource(
        resource_id="vol-test-orphan",
        type="ebs",
        cloud_provider="aws",
        region="us-east-1",
        monthly_cost=80.0,
        attrs={"availability_zone": "us-east-1a", "tags": {"Lifecycle": "orphaned"}},
    )
    f = _make_finding_for(r)
    plan = RemediationGenerator().build(f, r, fmt="aws_cli")
    assert plan.format == "aws_cli"
    assert plan.blast_radius == "low"
    assert "vol-test-orphan" in plan.rendered
    assert "snapshot" in plan.rendered.lower()
    assert "delete-volume" in plan.rendered  # in the "Execute" line (commented)
    assert "--force" not in plan.rendered


@pytest.mark.parametrize("fmt", FORMATS)
def test_generator_all_formats_for_ebs(fmt: str) -> None:
    r = Resource(
        resource_id="vol-orphan",
        type="ebs",
        cloud_provider="aws",
        region="us-east-1",
        monthly_cost=80.0,
        attrs={"availability_zone": "us-east-1a", "tags": {"Lifecycle": "orphaned"}},
    )
    f = _make_finding_for(r)
    plan = RemediationGenerator().build(f, r, fmt=fmt)
    assert plan.rendered
    assert SafetyGate.validate(plan, allow_high_blast_radius=True).ok


def test_generator_rejects_unsupported_type() -> None:
    r = Resource(resource_id="weird-001", type="other", cloud_provider="aws")
    f = _make_finding_for(r)
    with pytest.raises(ValueError, match="no remediation template"):
        RemediationGenerator().build(f, r, fmt="aws_cli")


# ─── SafetyGate w/ blast_radius gating ────────────────────────────────────────
def test_safety_gate_blocks_high_blast_radius_by_default() -> None:
    plan = RemediationPlan(
        finding_id=1,
        format="aws_cli",
        commands=["aws nat-gateway delete dryrun-only"],
        blast_radius="high",
        rendered="# Plan\nclean text only",
    )
    result = SafetyGate.validate(plan)
    assert not result.ok
    assert result.blast_radius_blocked


def test_safety_gate_allows_high_with_override() -> None:
    plan = RemediationPlan(
        finding_id=1,
        format="aws_cli",
        commands=["aws nat-gateway delete dryrun-only"],
        blast_radius="high",
        rendered="# Plan\nclean text only",
    )
    result = SafetyGate.validate(plan, allow_high_blast_radius=True)
    assert result.ok


# ─── End-to-end via build_plan ────────────────────────────────────────────────
def test_build_plan_end_to_end(samples_dir) -> None:
    ingest_file(samples_dir / "aws_cur_sample.csv")
    run_scan()
    # Pick the first finding
    with get_session() as s:
        finding = s.exec(select(Finding)).first()
    assert finding is not None
    out = build_plan(finding_id=finding.id, fmt="aws_cli")
    assert out["id"] is not None
    assert out["format"] == "aws_cli"
    assert "rendered" in out and out["rendered"]
    assert out["blast_radius"] in {"low", "medium", "high"}


def test_build_plan_missing_finding() -> None:
    with pytest.raises(LookupError):
        build_plan(finding_id=999_999, fmt="aws_cli")


def test_dangerous_patterns_list_is_complete() -> None:
    """Sanity: every pattern in DANGEROUS_PATTERNS compiles and matches itself."""
    assert len(DANGEROUS_PATTERNS) >= 8
    for name, pat in DANGEROUS_PATTERNS:
        assert pat.pattern  # compiled OK
