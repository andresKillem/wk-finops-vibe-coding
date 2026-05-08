"""Sub-agent tests — fallback path + mocked LLM path.

The deterministic fallback is the load-bearing surface (see ADR-007); we test
it without any network. The LLM path is exercised via a monkeypatched async
client so the test suite stays free of paid Anthropic calls.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from finops.agents.analyzer import AnalyzerAgent
from finops.agents.base import (
    AgentResponse,
    estimate_cost,
    extract_json_object,
)
from finops.agents.orchestrator import Orchestrator
from finops.agents.remediator import RemediatorAgent
from finops.detection.engine import run_scan
from finops.ingestion.router import ingest_file


# ─── extract_json_object helper ─────────────────────────────────────────────
def test_extract_json_object_clean() -> None:
    text = '{"foo": 1, "bar": [2, 3]}'
    assert extract_json_object(text) == {"foo": 1, "bar": [2, 3]}


def test_extract_json_object_with_prose() -> None:
    text = "Here is the result:\n\n```json\n{\"answer\": 42}\n```\n\nDone."
    assert extract_json_object(text) == {"answer": 42}


def test_extract_json_object_unparseable() -> None:
    assert extract_json_object("not json at all") == {}
    assert extract_json_object("") == {}


def test_extract_json_object_nested() -> None:
    text = '{"a": {"b": {"c": 1}}, "d": 2}'
    assert extract_json_object(text) == {"a": {"b": {"c": 1}}, "d": 2}


# ─── estimate_cost ───────────────────────────────────────────────────────────
def test_estimate_cost_opus() -> None:
    cost = estimate_cost("claude-opus-4-7", 10_000, 2_000)
    # 10000 * 15/M + 2000 * 75/M = 0.15 + 0.15 = 0.30
    assert cost == pytest.approx(0.30, rel=0.01)


def test_estimate_cost_haiku() -> None:
    cost = estimate_cost("claude-haiku-4-5", 5_000, 500)
    # 5000 * 1/M + 500 * 5/M = 0.005 + 0.0025 = 0.0075
    assert cost == pytest.approx(0.0075, rel=0.01)


def test_estimate_cost_unknown_model_defaults() -> None:
    # Unknown model defaults to deterministic-fallback rates (0, 0)
    cost = estimate_cost("totally-fake-model", 1_000_000, 1_000_000)
    assert cost == 0.0


# ─── Fallback path ───────────────────────────────────────────────────────────
def _seed_findings(samples_dir: Path) -> None:
    ingest_file(samples_dir / "aws_cur_sample.csv")
    run_scan()


def _disable_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force fallback by clearing the API key on the module-level settings."""
    from finops.config import settings as _s

    monkeypatch.setattr(_s, "anthropic_api_key", "")


@pytest.mark.asyncio
async def test_analyzer_fallback_no_key(samples_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_llm(monkeypatch)
    _seed_findings(samples_dir)
    findings_input = {
        "findings": [
            {"id": 1, "rule_id": "R-EBS-001", "resource_id": "vol-x", "severity": "HIGH",
             "savings_estimate": 80.0, "risk_score": 85, "confidence": 0.9, "description": "orphan"},
            {"id": 2, "rule_id": "R-EC2-001", "resource_id": "i-y", "severity": "MEDIUM",
             "savings_estimate": 50.0, "risk_score": 35, "confidence": 0.85, "description": "idle"},
        ],
        "total_monthly_waste": 130.0,
        "overall_risk": 60.0,
    }
    a = AnalyzerAgent()
    resp = await a.run(findings_input)
    assert resp.success
    assert resp.fallback_mode is True
    assert "executive_narrative" in resp.output
    assert len(resp.output["executive_narrative"]) >= 2
    assert "top_5" in resp.output
    assert "by_root_cause" in resp.output


@pytest.mark.asyncio
async def test_remediator_fallback_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_llm(monkeypatch)
    r = RemediatorAgent()
    resp = await r.run(
        {
            "finding": {
                "id": 1,
                "rule_id": "R-EBS-001",
                "resource_id": "vol-x",
                "severity": "HIGH",
                "savings_estimate": 80.0,
            },
            "base_plan": {"format": "aws_cli", "blast_radius": "low", "commands": ["..."]},
        }
    )
    assert resp.success
    assert resp.fallback_mode is True
    assert "preconditions_narrative" in resp.output
    assert "rollback_procedure" in resp.output
    assert "stakeholder_communication" in resp.output


# ─── Mocked LLM path ─────────────────────────────────────────────────────────
def _mock_anthropic_message(json_payload: str, model: str = "claude-opus-4-7-20260101") -> MagicMock:
    msg = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = json_payload
    msg.content = [block]
    msg.model = model
    msg.usage = MagicMock(input_tokens=100, output_tokens=50)
    return msg


@pytest.mark.asyncio
async def test_analyzer_llm_path_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the network: inject a fake AsyncAnthropic into the agent."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_message(
            '{"executive_narrative": ["a", "b", "c"], "by_root_cause": {}, '
            '"top_5": [{"finding_id": 1, "title": "x", "savings_per_month": 10, "rationale": "y"}], '
            '"recommended_next_action": {"finding_ids": [1], "reasoning": "z", '
            '"expected_savings": 10, "blast_radius": "low"}}'
        )
    )

    from finops.config import settings as _s
    monkeypatch.setattr(_s, "anthropic_api_key", "sk-ant-fake-test-key")

    a = AnalyzerAgent()
    a._client = fake_client  # bypass lazy init
    resp = await a.run({"findings": [{"id": 1, "savings_estimate": 10, "severity": "LOW"}]})

    assert resp.success
    assert resp.fallback_mode is False
    assert resp.tokens_in == 100
    assert resp.tokens_out == 50
    assert resp.cost_estimate > 0
    assert resp.output["executive_narrative"] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_remediator_llm_path_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_message(
            '{"preconditions_narrative": "ok", "rollback_procedure": ["s1"], '
            '"stakeholder_communication": "msg", "adjacent_optimizations": []}',
            model="claude-haiku-4-5-20251001",
        )
    )

    from finops.config import settings as _s
    monkeypatch.setattr(_s, "anthropic_api_key", "sk-ant-fake-test-key")

    r = RemediatorAgent()
    r._client = fake_client
    resp = await r.run({"finding": {"rule_id": "R-EBS-001"}, "base_plan": {}})

    assert resp.success
    assert resp.fallback_mode is False
    assert resp.output["preconditions_narrative"] == "ok"


@pytest.mark.asyncio
async def test_analyzer_llm_invalid_json_falls_back_to_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_message("This is not JSON at all, just prose.")
    )
    from finops.config import settings as _s
    monkeypatch.setattr(_s, "anthropic_api_key", "sk-ant-fake-test-key")

    a = AnalyzerAgent()
    a._client = fake_client
    resp = await a.run({"findings": []})
    # Surface should still be valid AgentResponse; success=False since output is empty
    assert resp.success is False
    assert "raw_text" in resp.output


# ─── Orchestrator end-to-end (fallback) ──────────────────────────────────────
@pytest.mark.asyncio
async def test_orchestrator_end_to_end_fallback(samples_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_llm(monkeypatch)
    _seed_findings(samples_dir)

    result = await Orchestrator(max_concurrent=3).run(top_n=3, fmt="aws_cli")

    assert "summary" in result
    assert "analyzer" in result
    assert "remediations" in result

    assert result["summary"]["findings_count"] >= 7
    assert result["summary"]["fallback_mode"] is True
    assert result["summary"]["agents_invoked"] >= 1

    assert result["analyzer"]["output"]["executive_narrative"]
    assert len(result["remediations"]) >= 1
    for r in result["remediations"]:
        assert "base_plan" in r
        assert "enrichment" in r
        assert "preconditions_narrative" in r["enrichment"]


# ─── Audit run is persisted ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_agent_run_persisted(samples_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_llm(monkeypatch)
    _seed_findings(samples_dir)
    a = AnalyzerAgent()
    await a.run({"findings": [{"id": 1, "rule_id": "R-EBS-001", "severity": "HIGH",
                               "savings_estimate": 50.0, "confidence": 0.9}],
                 "total_monthly_waste": 50.0})

    from sqlmodel import select
    from finops.db.session import get_session
    from finops.db.models import AgentRun

    with get_session() as s:
        rows = list(s.exec(select(AgentRun).where(AgentRun.agent_name == "analyzer")).all())
    assert len(rows) >= 1
    assert rows[-1].model == "deterministic-fallback"
