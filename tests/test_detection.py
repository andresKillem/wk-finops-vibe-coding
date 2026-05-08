"""Detection layer tests.

Each rule has a positive case (rule fires) and a negative case (rule
deliberately does NOT fire on a similar-looking resource). Plus an end-to-end
scan against the generated samples to confirm the engine produces a sensible
aggregate readout.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from finops.db.models import BillingRecord, Finding, Resource
from finops.detection.aws_rules import (
    DanglingElasticIPRule,
    IdleEC2Rule,
    IdleNATGatewayRule,
    IdleRDSRule,
    LegacyGenInstanceRule,
    OrphanedEBSRule,
    UnusedLoadBalancerRule,
)
from finops.detection.engine import run_scan
from finops.detection.scoring import (
    aggregate_score,
    calibration_label,
    risk_score,
)
from finops.ingestion.router import ingest_file


# ─── Fixture builders ─────────────────────────────────────────────────────────
def _resource(rid: str, type_: str, *, lifecycle: str = "", monthly_cost: float = 50.0,
              instance_type: str = "", attached_to: str = "") -> Resource:
    attrs = {"tags": {"Lifecycle": lifecycle} if lifecycle else {}}
    if instance_type:
        attrs["instance_type"] = instance_type
    if attached_to:
        attrs["attached_to"] = attached_to
    return Resource(
        resource_id=rid,
        type=type_,
        cloud_provider="aws",
        monthly_cost=monthly_cost,
        attrs=attrs,
    )


def _billing(rid: str, usage_type: str = "", usage_amount: float = 0.0) -> BillingRecord:
    raw = {"lineItem/UsageType": usage_type} if usage_type else {}
    return BillingRecord(
        cloud_provider="aws",
        account_id="test",
        service="test",
        resource_id=rid,
        usage_amount=usage_amount,
        cost=0.0,
        period_start=datetime(2026, 4, 1),
        period_end=datetime(2026, 4, 30),
        raw_record=raw,
    )


# ─── R-EBS-001 OrphanedEBS ────────────────────────────────────────────────────
def test_orphaned_ebs_positive() -> None:
    r = _resource("vol-orphan", "ebs", lifecycle="orphaned", monthly_cost=80.0)
    f = OrphanedEBSRule().evaluate(r, [])
    assert f is not None
    assert f.severity == "HIGH"
    assert f.savings_estimate == 80.0
    assert f.confidence > 0.5


def test_orphaned_ebs_negative() -> None:
    r = _resource("vol-attached", "ebs", lifecycle="persistent", attached_to="i-abc")
    f = OrphanedEBSRule().evaluate(r, [])
    assert f is None


# ─── R-EC2-001 IdleEC2 ────────────────────────────────────────────────────────
def test_idle_ec2_positive() -> None:
    r = _resource("i-idle", "ec2", lifecycle="idle", monthly_cost=92.0, instance_type="r5.large")
    f = IdleEC2Rule().evaluate(r, [])
    assert f is not None
    assert f.severity == "MEDIUM"
    # 95% of 92 = 87.4
    assert f.savings_estimate == round(92.0 * 0.95, 2)


def test_idle_ec2_negative_active() -> None:
    r = _resource("i-active", "ec2", lifecycle="persistent", instance_type="m5.xlarge")
    f = IdleEC2Rule().evaluate(r, [])
    assert f is None


def test_idle_ec2_negative_wrong_type() -> None:
    r = _resource("vol-idle", "ebs", lifecycle="idle")
    f = IdleEC2Rule().evaluate(r, [])
    assert f is None


# ─── R-EIP-001 DanglingEIP ────────────────────────────────────────────────────
def test_dangling_eip_positive_via_idle_charge() -> None:
    r = _resource("eip-dangling", "eip", monthly_cost=3.6)
    billing = [_billing("eip-dangling", "ElasticIP:IdleAddress", 24)]
    f = DanglingElasticIPRule().evaluate(r, billing)
    assert f is not None
    assert f.severity == "MEDIUM"
    assert f.savings_estimate >= 3.6


def test_dangling_eip_positive_via_lifecycle() -> None:
    r = _resource("eip-other", "eip", lifecycle="orphaned", monthly_cost=3.6)
    f = DanglingElasticIPRule().evaluate(r, [])
    assert f is not None


def test_dangling_eip_negative_attached() -> None:
    r = _resource("eip-prod", "eip", lifecycle="persistent", monthly_cost=0.0)
    billing = [_billing("eip-prod", "ElasticIP:InUseAddress", 24)]
    f = DanglingElasticIPRule().evaluate(r, billing)
    assert f is None


# ─── R-NAT-001 IdleNAT ────────────────────────────────────────────────────────
def test_idle_nat_positive() -> None:
    r = _resource("nat-idle", "nat", monthly_cost=33.5, lifecycle="idle")
    # 12 daily records, each 0.0001 GB → total 0.0012 GB << threshold 0.03
    billing = [_billing("nat-idle", "NatGateway-Bytes", 0.0001) for _ in range(12)]
    f = IdleNATGatewayRule().evaluate(r, billing)
    assert f is not None
    assert f.severity == "HIGH"


def test_idle_nat_negative_active() -> None:
    r = _resource("nat-active", "nat", monthly_cost=33.5, lifecycle="persistent")
    # 12 daily records, each 8.5 GB → ample traffic
    billing = [_billing("nat-active", "NatGateway-Bytes", 8.5) for _ in range(12)]
    f = IdleNATGatewayRule().evaluate(r, billing)
    assert f is None


# ─── R-RDS-001 IdleRDS ────────────────────────────────────────────────────────
def test_idle_rds_positive() -> None:
    r = _resource("arn:aws:rds:us-east-1::db:idle", "rds", lifecycle="idle", monthly_cost=60.0)
    f = IdleRDSRule().evaluate(r, [])
    assert f is not None
    assert f.severity == "HIGH"
    assert f.savings_estimate == 60.0


def test_idle_rds_negative() -> None:
    r = _resource("arn:aws:rds:us-east-1::db:active", "rds", lifecycle="persistent")
    f = IdleRDSRule().evaluate(r, [])
    assert f is None


# ─── R-ELB-001 UnusedELB ──────────────────────────────────────────────────────
def test_unused_elb_positive() -> None:
    r = _resource("arn:aws:elasticloadbalancing:::loadbalancer/app/idle/abc",
                  "elb", lifecycle="idle", monthly_cost=16.2)
    f = UnusedLoadBalancerRule().evaluate(r, [])
    assert f is not None
    assert f.severity == "MEDIUM"


def test_unused_elb_negative() -> None:
    r = _resource("arn:aws:elasticloadbalancing:::loadbalancer/app/healthy/abc",
                  "elb", lifecycle="persistent")
    f = UnusedLoadBalancerRule().evaluate(r, [])
    assert f is None


# ─── R-INST-LEGACY-001 LegacyGen ──────────────────────────────────────────────
@pytest.mark.parametrize("instance_type", ["t2.medium", "m4.large", "r4.xlarge", "c4.2xlarge"])
def test_legacy_gen_positive(instance_type: str) -> None:
    r = _resource("i-legacy", "ec2", instance_type=instance_type, monthly_cost=100.0)
    f = LegacyGenInstanceRule().evaluate(r, [])
    assert f is not None
    assert f.severity == "LOW"
    assert f.savings_estimate == 20.0  # 20% of 100


@pytest.mark.parametrize("instance_type", ["m5.xlarge", "c5.large", "r5.2xlarge", "m6i.large"])
def test_legacy_gen_negative(instance_type: str) -> None:
    r = _resource("i-current", "ec2", instance_type=instance_type)
    f = LegacyGenInstanceRule().evaluate(r, [])
    assert f is None


# ─── Scoring ──────────────────────────────────────────────────────────────────
def test_risk_score_high_severity_high_cost() -> None:
    f = Finding(
        resource_id="vol-x",
        rule_id="R-EBS-001",
        severity="HIGH",
        savings_estimate=200.0,
        confidence=0.9,
    )
    score = risk_score(f)
    # severity_weight=8 × 0.9 × (1 + min(200/100, 2.0)=2.0) × 10 = 216 → clamped to 100
    assert score == 100.0


def test_risk_score_low_severity_small_cost() -> None:
    f = Finding(
        resource_id="i-x",
        rule_id="R-INST-LEGACY-001",
        severity="LOW",
        savings_estimate=5.0,
        confidence=1.0,
    )
    score = risk_score(f)
    # 1 × 1.0 × (1 + 0.05) × 10 = 10.5
    assert 10.0 <= score <= 11.0


def test_calibration_labels() -> None:
    assert calibration_label(0) == "Healthy"
    assert calibration_label(30) == "Healthy"
    assert calibration_label(31) == "Attention"
    assert calibration_label(60) == "Attention"
    assert calibration_label(61) == "Significant waste"
    assert calibration_label(80) == "Significant waste"
    assert calibration_label(81) == "Critical"
    assert calibration_label(100) == "Critical"


def test_aggregate_empty() -> None:
    agg = aggregate_score([], [])
    assert agg["total_monthly_waste"] == 0.0
    assert agg["overall_risk"] == 0.0
    assert agg["calibration_label"] == "Healthy"
    assert agg["findings_count"] == 0


# ─── Engine end-to-end ────────────────────────────────────────────────────────
def test_engine_scan_real_samples(samples_dir: Path) -> None:
    """Ingest the AWS sample, run scan, sanity-check the aggregate."""
    ingest_file(samples_dir / "aws_cur_sample.csv")
    result = run_scan()

    assert result.resources_evaluated == 17
    assert result.rules_evaluated == 7
    # We seeded 2 orphaned EBS, 1 idle EC2, 1 dangling EIP, 1 idle NAT, 1 idle RDS,
    # 1 unused ELB, plus a t2.medium triggering LegacyGen → at least 7 findings.
    assert result.aggregate["findings_count"] >= 7
    assert result.aggregate["total_monthly_waste"] > 0
    assert 0 <= result.aggregate["overall_risk"] <= 100

    # Severity mix should include all 3 levels
    sev = result.aggregate["by_severity"]
    assert sev["HIGH"] >= 2  # at least the 2 orphaned EBS
    assert sev["MEDIUM"] >= 1
    # LegacyGen is LOW; t2.medium in sample
    assert sev["LOW"] >= 1


def test_engine_idempotent(samples_dir: Path) -> None:
    """Re-scan must produce the same set of findings (deletes priors)."""
    ingest_file(samples_dir / "aws_cur_sample.csv")
    r1 = run_scan()
    r2 = run_scan()
    assert r1.aggregate["findings_count"] == r2.aggregate["findings_count"]
    assert r1.aggregate["total_monthly_waste"] == r2.aggregate["total_monthly_waste"]
