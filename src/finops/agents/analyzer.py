"""AnalyzerAgent — Opus orchestrator-grade. Runs once per audit.

Receives the full findings list. Returns prioritized analysis with executive
narrative. The most expensive call in the orchestration; we make exactly one
per audit and let Haiku workers handle the rest.
"""
from __future__ import annotations

import time
from typing import Any

from finops.agents.base import AgentResponse, BaseAgent, estimate_cost, extract_json_object
from finops.config import settings


SYSTEM_PROMPT = """\
You are a senior FinOps engineer reviewing a cloud account's waste findings.
You operate within the FinOps Foundation framework: Inform → Optimize → Operate → Report.

Your job: turn a list of detected findings into a prioritized plan with an executive narrative.

You MUST output ONLY a single JSON object — no markdown, no prose before or after.

Output schema:
{
  "executive_narrative": ["bullet 1", "bullet 2", "bullet 3"],
  "by_root_cause": {
    "forgotten_resources": {"total_savings": 0.0, "count": 0, "examples": []},
    "idle_resources":      {"total_savings": 0.0, "count": 0, "examples": []},
    "outdated_families":   {"total_savings": 0.0, "count": 0, "examples": []}
  },
  "top_5": [
    {"finding_id": 0, "title": "...", "savings_per_month": 0.0, "rationale": "..."}
  ],
  "recommended_next_action": {
    "finding_ids": [0],
    "reasoning": "...",
    "expected_savings": 0.0,
    "blast_radius": "low | medium | high"
  }
}

Tone & quality:
- Concrete over abstract. "Three orphaned EBS volumes account for 60% of detected waste"
  beats "We see significant storage waste."
- Narrative bullet 2 should explain the *organisational story* you infer (e.g.,
  "Likely a deleted EC2 fleet from late Q1 left these volumes behind").
- No CYA hedging. If the data is clear, say so. If signals are mixed, name them.
- Recommend ONE next action — the cheapest, lowest-blast-radius win that
  delivers credible savings.
- Exclude findings with confidence < 0.5 from top_5.
"""


def _categorise(rule_id: str) -> str:
    if rule_id in {"R-EBS-001", "R-EIP-001"}:
        return "forgotten_resources"
    if rule_id in {"R-EC2-001", "R-NAT-001", "R-RDS-001", "R-ELB-001"}:
        return "idle_resources"
    if rule_id == "R-INST-LEGACY-001":
        return "outdated_families"
    return "idle_resources"


class AnalyzerAgent(BaseAgent):
    """Single Opus call per audit. Prioritises findings + writes the narrative."""

    name = "analyzer"

    def __init__(self) -> None:
        super().__init__(model=settings.anthropic_orchestrator_model)

    async def _run_llm(self, input_dict: dict[str, Any]) -> AgentResponse:
        client = self.client
        assert client is not None

        findings = input_dict.get("findings", [])
        # Compress findings to the keys Opus actually needs
        compact = [
            {
                "id": f.get("id"),
                "rule_id": f.get("rule_id"),
                "resource_id": f.get("resource_id"),
                "severity": f.get("severity"),
                "savings_estimate": f.get("savings_estimate"),
                "risk_score": f.get("risk_score"),
                "confidence": f.get("confidence"),
                "description": f.get("description"),
            }
            for f in findings
        ]
        user_msg = (
            f"Aggregate metrics: total_monthly_waste=${input_dict.get('total_monthly_waste', 0):.2f}, "
            f"overall_risk={input_dict.get('overall_risk', 0):.2f}, "
            f"findings_count={len(findings)}.\n\n"
            f"Findings:\n```json\n{compact}\n```\n\n"
            "Produce the JSON readout per the schema in your system prompt."
        )

        start = time.perf_counter()
        msg = await client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        text = "".join(b.text for b in msg.content if b.type == "text")
        output = extract_json_object(text)
        success = bool(output)

        return AgentResponse(
            agent_name=self.name,
            model=msg.model,
            success=success,
            output=output if success else {"raw_text": text},
            raw_response=text,
            tokens_in=msg.usage.input_tokens,
            tokens_out=msg.usage.output_tokens,
            duration_ms=duration_ms,
            cost_estimate=estimate_cost(msg.model, msg.usage.input_tokens, msg.usage.output_tokens),
            error=None if success else "could not extract JSON object from response",
        )

    def _run_fallback(self, input_dict: dict[str, Any]) -> AgentResponse:
        findings = input_dict.get("findings", [])
        weights = {"HIGH": 8, "MEDIUM": 3, "LOW": 1}

        sorted_f = sorted(
            findings,
            key=lambda f: weights.get(str(f.get("severity", "LOW")).upper(), 1)
            * float(f.get("savings_estimate", 0) or 0),
            reverse=True,
        )

        by_cause: dict[str, dict[str, Any]] = {
            "forgotten_resources": {"total_savings": 0.0, "count": 0, "examples": []},
            "idle_resources":      {"total_savings": 0.0, "count": 0, "examples": []},
            "outdated_families":   {"total_savings": 0.0, "count": 0, "examples": []},
        }
        for f in findings:
            cat = _categorise(str(f.get("rule_id", "")))
            d = by_cause.setdefault(cat, {"total_savings": 0.0, "count": 0, "examples": []})
            d["total_savings"] = round(d["total_savings"] + float(f.get("savings_estimate", 0) or 0), 2)
            d["count"] += 1
            if len(d["examples"]) < 3:
                d["examples"].append(f.get("resource_id"))

        top_5 = [
            {
                "finding_id": f.get("id"),
                "title": (f.get("description") or "")[:80],
                "savings_per_month": float(f.get("savings_estimate", 0) or 0),
                "rationale": f"severity={f.get('severity')}, ${f.get('savings_estimate'):.2f}/mo",
            }
            for f in sorted_f[:5]
            if float(f.get("confidence", 1) or 1) >= 0.5
        ]

        # Pick lowest-blast-radius high-impact next action — prefer EBS/EIP (low blast)
        safe_first = next(
            (f for f in sorted_f if f.get("rule_id") in ("R-EBS-001", "R-EIP-001")),
            sorted_f[0] if sorted_f else None,
        )

        total_waste = sum(float(f.get("savings_estimate", 0) or 0) for f in findings)
        dominant = max(by_cause, key=lambda k: by_cause[k]["total_savings"]) if findings else "none"

        narrative = [
            f"Detected ${total_waste:.2f}/month in waste across {len(findings)} findings; "
            f"12-month projection ${total_waste * 12:.2f}.",
            f"Dominant root-cause category: {dominant.replace('_', ' ')} "
            f"({by_cause.get(dominant, {}).get('count', 0)} findings, "
            f"${by_cause.get(dominant, {}).get('total_savings', 0):.2f}/mo).",
            f"Recommended first action: address {safe_first.get('rule_id')} on "
            f"{safe_first.get('resource_id')} — lowest blast radius, "
            f"${safe_first.get('savings_estimate', 0):.2f}/mo savings."
            if safe_first
            else "No findings detected; account hygiene is good.",
        ]

        return AgentResponse(
            agent_name=self.name,
            model="deterministic-fallback",
            success=True,
            output={
                "executive_narrative": narrative,
                "by_root_cause": by_cause,
                "top_5": top_5,
                "recommended_next_action": {
                    "finding_ids": [safe_first.get("id")] if safe_first else [],
                    "reasoning": "Highest impact among low-blast-radius findings; safe first execute."
                    if safe_first
                    else "No actionable findings.",
                    "expected_savings": float(safe_first.get("savings_estimate", 0) or 0)
                    if safe_first
                    else 0.0,
                    "blast_radius": "low",
                },
            },
            raw_response="",
            tokens_in=0,
            tokens_out=0,
            duration_ms=0,
            cost_estimate=0.0,
            fallback_mode=True,
        )
