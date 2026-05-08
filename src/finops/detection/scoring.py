"""Risk scoring — per-finding and account-aggregate.

Formula and calibration documented in `.claude/skills/finops-architect/references/risk-scoring.md`;
this file is the executable form of that spec.
"""
from __future__ import annotations

from typing import Iterable

from finops.config import settings
from finops.db.models import Finding, Resource


def risk_score(finding: Finding) -> float:
    """Compute risk score in [0, 100] for a single Finding.

        risk_score = severity_weight × confidence × (1 + cost_factor) × 10
        cost_factor = min(monthly_savings / 100, 2.0)
        clamp(0, 100)

    Severity weights come from settings (env-overridable for what-if analysis).
    The cost_factor saturates at $200/mo so a single mega-finding can't
    monopolise the whole risk budget.
    """
    sev_w = settings.severity_weight.get(finding.severity.upper(), 1)
    cost_factor = min(max(finding.savings_estimate, 0.0) / 100.0, 2.0)
    score = sev_w * max(finding.confidence, 0.0) * (1.0 + cost_factor) * 10.0
    return round(min(score, 100.0), 2)


def calibration_label(overall_risk: float) -> str:
    """Map an overall_risk score to a human label per ADR-recorded calibration."""
    if overall_risk < 31:
        return "Healthy"
    if overall_risk < 61:
        return "Attention"
    if overall_risk < 81:
        return "Significant waste"
    return "Critical"


def aggregate_score(
    findings: Iterable[Finding], resources: Iterable[Resource] | None = None
) -> dict:
    """Compute account-level metrics from a set of findings.

    `overall_risk` is the **volume-weighted mean** of per-finding risk_score —
    a $500 finding outweighs fifty $1 findings, which is the right priority
    for an executive readout. See ADR-002 in BITACORA.md.

    Returns a dict ready for both JSON serialisation (API/MCP) and rich
    rendering (dashboard).
    """
    findings = list(findings)
    resource_by_id: dict[str, Resource] = (
        {r.resource_id: r for r in resources} if resources else {}
    )

    if not findings:
        return {
            "total_monthly_waste": 0.0,
            "annual_projection": 0.0,
            "overall_risk": 0.0,
            "calibration_label": "Healthy",
            "findings_count": 0,
            "top_5_offenders": [],
            "by_category": {},
            "by_severity": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
        }

    total_waste = sum(f.savings_estimate for f in findings)
    weights = [max(f.savings_estimate, 1.0) for f in findings]
    weight_sum = sum(weights)
    overall = sum(f.risk_score * w for f, w in zip(findings, weights)) / weight_sum
    overall = round(min(overall, 100.0), 2)

    top_5 = sorted(findings, key=lambda f: f.risk_score, reverse=True)[:5]

    by_cat: dict[str, dict] = {}
    for f in findings:
        r = resource_by_id.get(f.resource_id)
        cat = (r.type if r else "other") or "other"
        d = by_cat.setdefault(cat, {"count": 0, "total_savings": 0.0, "max_risk": 0.0})
        d["count"] += 1
        d["total_savings"] = round(d["total_savings"] + f.savings_estimate, 2)
        d["max_risk"] = max(d["max_risk"], f.risk_score)

    by_sev = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f.severity.upper()
        if sev in by_sev:
            by_sev[sev] += 1

    return {
        "total_monthly_waste": round(total_waste, 2),
        "annual_projection": round(total_waste * 12, 2),
        "overall_risk": overall,
        "calibration_label": calibration_label(overall),
        "findings_count": len(findings),
        "top_5_offenders": [
            {
                "finding_id": f.id,
                "rule_id": f.rule_id,
                "resource_id": f.resource_id,
                "severity": f.severity,
                "savings_per_month": f.savings_estimate,
                "risk_score": f.risk_score,
                "description": f.description,
            }
            for f in top_5
        ],
        "by_category": by_cat,
        "by_severity": by_sev,
    }
