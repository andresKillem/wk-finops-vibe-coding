"""MCP server smoke tests.

We test at the *function* level (not via stdio subprocess) — every tool is a
plain Python function under the @mcp.tool() decorator, so calling them directly
exercises the same code path the MCP runtime would.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import select

from finops.db.models import Finding
from finops.db.session import get_session
from finops.detection.engine import run_scan
from finops.ingestion.router import ingest_file
from finops.mcp_server import server as mcp_server


# ─── Module-level checks ─────────────────────────────────────────────────────
def test_mcp_instance_exists() -> None:
    assert mcp_server.mcp is not None
    assert mcp_server.mcp.name == "finops-cost-optimizer"


def test_run_server_callable() -> None:
    """Importing run_server must not start it. Just check it's callable."""
    assert callable(mcp_server.run_server)


# ─── Tool functions are directly callable ───────────────────────────────────
def test_ingest_billing_tool(samples_dir: Path) -> None:
    out = mcp_server.ingest_billing(str(samples_dir / "aws_cur_sample.csv"))
    assert out["provider"] == "aws"
    assert out["rows_parsed"] > 0
    assert out["resources_upserted"] == 17


def test_estimate_savings_empty_db() -> None:
    out = mcp_server.estimate_savings()
    assert out["findings_count"] == 0
    assert out["total_monthly_waste"] == 0.0


def test_estimate_savings_after_scan(samples_dir: Path) -> None:
    ingest_file(samples_dir / "aws_cur_sample.csv")
    run_scan()
    out = mcp_server.estimate_savings()
    assert out["findings_count"] >= 7
    assert out["total_monthly_waste"] > 0


def test_list_findings_tool(samples_dir: Path) -> None:
    ingest_file(samples_dir / "aws_cur_sample.csv")
    run_scan()
    rows = mcp_server.list_findings(severity="HIGH", limit=5)
    assert len(rows) >= 1
    assert all(r["severity"] == "HIGH" for r in rows)


def test_propose_remediation_tool(samples_dir: Path) -> None:
    ingest_file(samples_dir / "aws_cur_sample.csv")
    run_scan()
    with get_session() as s:
        f = s.exec(select(Finding)).first()
    assert f is not None
    plan = mcp_server.propose_remediation(finding_id=f.id, format="aws_cli")
    assert plan["format"] == "aws_cli"
    assert plan["rendered"]


# ─── Resources ───────────────────────────────────────────────────────────────
def test_findings_resource(samples_dir: Path) -> None:
    ingest_file(samples_dir / "aws_cur_sample.csv")
    run_scan()
    text = mcp_server.findings_resource()
    import json
    payload = json.loads(text)
    assert isinstance(payload, list)
    assert len(payload) >= 7
    for f in payload:
        assert "rule_id" in f and "resource_id" in f


# ─── Prompts ─────────────────────────────────────────────────────────────────
def test_finops_audit_prompt() -> None:
    text = mcp_server.finops_audit(file_path="some/path.csv", audience="exec")
    assert "ingest_billing" in text
    assert "analyze_billing" in text
    assert "exec" in text


def test_finops_audit_prompt_audiences() -> None:
    for aud in ("exec", "engineer", "compliance"):
        text = mcp_server.finops_audit(audience=aud)
        assert aud in text


# ─── Async tool ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_analyze_billing_tool(samples_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force fallback so the test runs offline."""
    from finops.config import settings as _s
    monkeypatch.setattr(_s, "anthropic_api_key", "")
    ingest_file(samples_dir / "aws_cur_sample.csv")
    result = await mcp_server.analyze_billing(top_n=2)
    assert "summary" in result
    assert result["summary"]["fallback_mode"] is True
