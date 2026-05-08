"""Orchestrator — coordinates one Analyzer call + parallel Remediator workers.

Topology (per BITACORA ADR-002 + ADR-013):

        all findings ──▶ AnalyzerAgent (Opus, 1 call)
                              │
                              ▼
                   prioritised top_5
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  RemediatorAgent       RemediatorAgent       RemediatorAgent
  (Haiku, finding 1)    (Haiku, finding 2)    (Haiku, finding N)
        │                     │                     │
        └────── asyncio.gather (max 5 concurrent) ──┘
                              │
                              ▼
                       merged result
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sqlmodel import select

from finops.agents.analyzer import AnalyzerAgent
from finops.agents.base import AgentResponse
from finops.agents.remediator import RemediatorAgent
from finops.config import settings
from finops.db.models import Finding, Resource
from finops.db.session import get_session, init_db
from finops.detection.scoring import aggregate_score
from finops.remediation.generator import RemediationGenerator

logger = logging.getLogger(__name__)


class Orchestrator:
    """Public entrypoint for the agent layer. ``await orch.run()`` returns a dict."""

    def __init__(self, max_concurrent: int = 5) -> None:
        self.analyzer = AnalyzerAgent()
        self.remediator = RemediatorAgent()
        self.max_concurrent = max_concurrent

    async def run(self, top_n: int = 5, fmt: str = "aws_cli") -> dict[str, Any]:
        init_db()
        start = time.perf_counter()

        with get_session() as s:
            findings = list(s.exec(select(Finding)).all())
            resources = list(s.exec(select(Resource)).all())

        if not findings:
            return {
                "summary": {"findings_count": 0, "fallback_mode": not settings.llm_enabled},
                "analyzer": {},
                "remediations": [],
                "warning": "No findings; run POST /analyze first.",
            }

        agg = aggregate_score(findings, resources)

        analyzer_input = {
            "total_monthly_waste": agg["total_monthly_waste"],
            "overall_risk": agg["overall_risk"],
            "findings_count": len(findings),
            "findings": [self._serialise_finding(f) for f in findings],
        }
        analyzer_resp: AgentResponse = await self.analyzer.run(analyzer_input)

        # Build top-N target list; prefer Analyzer's top_5 if produced, else fall back to risk_score.
        top_ids: list[int] = []
        for item in analyzer_resp.output.get("top_5", [])[:top_n]:
            fid = item.get("finding_id")
            if isinstance(fid, int):
                top_ids.append(fid)
        if not top_ids:
            top_ids = [f.id for f in sorted(findings, key=lambda x: -x.risk_score)[:top_n] if f.id]

        # Build a fast lookup dict for resources by id
        res_by_id = {r.resource_id: r for r in resources}
        find_by_id = {f.id: f for f in findings if f.id is not None}

        sem = asyncio.Semaphore(self.max_concurrent)

        async def enrich(finding_id: int) -> dict[str, Any] | None:
            async with sem:
                f = find_by_id.get(finding_id)
                if f is None:
                    return None
                r = res_by_id.get(f.resource_id)
                if r is None:
                    return None
                # Build base plan deterministically (fast, no LLM)
                try:
                    base_plan = RemediationGenerator().build(f, r, fmt=fmt)
                except ValueError as e:
                    logger.warning("skip enrich for %s: %s", f.resource_id, e)
                    return None

                rem_resp = await self.remediator.run(
                    {
                        "finding": self._serialise_finding(f),
                        "base_plan": {
                            "format": base_plan.format,
                            "blast_radius": base_plan.blast_radius,
                            "commands": base_plan.commands[:30],  # cap for token budget
                        },
                    }
                )
                return {
                    "finding_id": finding_id,
                    "resource_id": f.resource_id,
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "base_plan": {
                        "format": base_plan.format,
                        "blast_radius": base_plan.blast_radius,
                        "rendered": base_plan.rendered,
                    },
                    "enrichment": rem_resp.output,
                    "agent_meta": {
                        "model": rem_resp.model,
                        "tokens_in": rem_resp.tokens_in,
                        "tokens_out": rem_resp.tokens_out,
                        "duration_ms": rem_resp.duration_ms,
                        "cost_estimate": rem_resp.cost_estimate,
                        "fallback_mode": rem_resp.fallback_mode,
                    },
                }

        rem_results = await asyncio.gather(*(enrich(fid) for fid in top_ids))
        remediations = [r for r in rem_results if r is not None]

        total_duration_ms = int((time.perf_counter() - start) * 1000)
        total_tokens_in = analyzer_resp.tokens_in + sum(r["agent_meta"]["tokens_in"] for r in remediations)
        total_tokens_out = analyzer_resp.tokens_out + sum(r["agent_meta"]["tokens_out"] for r in remediations)
        total_cost = analyzer_resp.cost_estimate + sum(r["agent_meta"]["cost_estimate"] for r in remediations)

        return {
            "summary": {
                "findings_count": len(findings),
                "agents_invoked": 1 + len(remediations),
                "tokens_in_total": total_tokens_in,
                "tokens_out_total": total_tokens_out,
                "cost_estimate_total": round(total_cost, 6),
                "duration_ms_total": total_duration_ms,
                "fallback_mode": analyzer_resp.fallback_mode,
                "total_monthly_waste": agg["total_monthly_waste"],
                "overall_risk": agg["overall_risk"],
                "calibration_label": agg["calibration_label"],
            },
            "analyzer": {
                "output": analyzer_resp.output,
                "meta": {
                    "model": analyzer_resp.model,
                    "tokens_in": analyzer_resp.tokens_in,
                    "tokens_out": analyzer_resp.tokens_out,
                    "duration_ms": analyzer_resp.duration_ms,
                    "cost_estimate": analyzer_resp.cost_estimate,
                    "fallback_mode": analyzer_resp.fallback_mode,
                },
            },
            "remediations": remediations,
        }

    @staticmethod
    def _serialise_finding(f: Finding) -> dict[str, Any]:
        return {
            "id": f.id,
            "rule_id": f.rule_id,
            "resource_id": f.resource_id,
            "severity": f.severity,
            "savings_estimate": f.savings_estimate,
            "risk_score": f.risk_score,
            "confidence": f.confidence,
            "description": f.description,
        }


def run_orchestrator() -> dict[str, Any]:
    """Sync wrapper for the CLI."""
    return asyncio.run(Orchestrator().run())
