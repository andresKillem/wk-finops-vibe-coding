# Cloud Cost Optimizer & Remediation Engine

> **Wolters Kluwer 2026 — Graduate Vibe Coding Challenge** · Project 1 (FinOps)
> Built end-to-end via [Claude Code](https://claude.com/code) under a strict no-manual-edits regime. Architect-led, AI-engineered.

Ingest AWS Cost & Usage Reports or Azure billing exports → detect orphaned/idle resources → produce a safe, multi-format decommission plan with a sub-agent enriched executive readout. **API-first, MCP-pluggable, dashboard-ready.**

[![Repo](https://img.shields.io/badge/GitHub-andresKillem%2Fwk--finops--vibe--coding-181717?logo=github)](https://github.com/andresKillem/wk-finops-vibe-coding)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Vibe Coding](https://img.shields.io/badge/Built%20with-Vibe%20Coding-7B61FF)](./prompts.md)

---

## Table of Contents

- [Quickstart](#quickstart)
- [Architecture](#architecture)
- [Features](#features)
- [Stack & Rationale](#stack--rationale)
- [Vibe Coding Compliance](#vibe-coding-compliance)
- [Demo URLs](#demo-urls)
- [MCP Integration](#mcp-integration)
- [Submission Checklist](#submission-checklist)

---

## Quickstart

```bash
git clone https://github.com/andresKillem/wk-finops-vibe-coding && cd wk-finops-vibe-coding
cp .env.example .env                 # add your ANTHROPIC_API_KEY (optional — fallback works without)
make install                         # uv sync
make demo                            # ingest sample CUR → scan → analyze → report
```

Then in three terminals (or split-pane):
```bash
make run-api          # FastAPI on :8000  (OpenAPI at /docs)
make run-dashboard    # Streamlit on :8501
make run-mcp          # MCP server (stdio)
```

## Architecture

```
                                    ┌─────────────────────────┐
                                    │  Streamlit Dashboard    │
                                    │  (5 pages, polished)    │
                                    └────────────┬────────────┘
                                                 │ HTTP
                                                 ▼
┌────────────┐    ingest    ┌──────────────────────────────────┐    invoke
│  Sample    │ ────────────▶│      FastAPI Core (REST)         │ ──────────▶  Anthropic
│  CUR/JSON  │              │  /upload /analyze /remediate ... │              SDK
└────────────┘              └──────┬─────────────┬─────────────┘
                                   │             │
                          ┌────────▼───┐   ┌─────▼─────────┐         ┌──────────────┐
                          │  Detector  │   │  Sub-agents   │ ──────▶ │ Anthropic    │
                          │  (rules +  │   │  Analyzer/    │         │ Opus + Haiku │
                          │   scoring) │   │  Remediator   │         └──────────────┘
                          └────────┬───┘   └─────┬─────────┘
                                   │             │
                                   ▼             ▼
                              ┌────────────────────────┐
                              │   SQLite + SQLModel    │
                              │   Resource · Finding · │
                              │   RemediationPlan      │
                              └────────────────────────┘

                    ◆ MCP server (stdio + http) exposes:
                       ingest_billing · analyze_billing
                       propose_remediation · estimate_savings
                    so any MCP-aware client can use this engine as a tool.
```

## Features

| Layer | What it does |
|---|---|
| **Ingestion** | AWS CUR (CSV) and Azure Consumption (JSON) parsers; auto-format detection; resource upsert. |
| **Detection** | 8 declarative rules covering EBS/EC2/EIP/NAT/RDS/ELB plus legacy generation. Risk-scored, severity-weighted. |
| **Sub-agents (HERO #1)** | Opus orchestrator (single call, executive narrative) + Haiku workers (parallel, plan enrichment). Deterministic fallback if no API key. |
| **MCP Server (HERO #2)** | Same engine exposed as universal tools — pluggable into Claude Code, Cursor, Claude Desktop. |
| **Remediation** | Three formats per finding (`aws_cli`, `boto3`, `terraform_import`) with pre-checks, snapshots, dry-runs, rollback, stakeholder comms. |
| **Safety gates** | Deny-list in `settings.json` + `safety_gate.sh` PreToolUse hook + Python-side validator. Multi-layered. |
| **Dashboard** | Streamlit, 5 pages: Home (KPIs), Findings, Remediation Studio, AI Insights, System. |
| **Webhook simulator** | POST to configurable URL when `overall_risk > threshold`. Async retry. |
| **Agentic surface** | Custom skills, slash commands, sub-agent definitions, hooks — all functional, not decorative. |
| **CI** | GitHub Actions running `uv sync + ruff + pytest` on every push. |

## Stack & Rationale

| Choice | Why |
|---|---|
| **FastAPI** | OpenAPI for free; native Pydantic; async first-class. |
| **SQLite + SQLModel** | Zero infra; SQLModel = Pydantic + SQLAlchemy unified; trivial Postgres upgrade path. |
| **Streamlit** | 5x faster to ship than React for analytical dashboards at this scope. |
| **Anthropic SDK direct** | No LangChain overhead; sub-agents as plain `asyncio` coroutines. |
| **MCP** | Reusable interface; pluggable into any MCP-aware client. |
| **uv** | 10x faster than pip; lockfile included; reproducible installs. |

Considered & rejected: LangGraph (overkill for fixed 1→N→1 topology), n8n (workflow-tool mismatch), Claude Managed Agents (consumes cloud the doc requires us to decommission), React (5x dashboard build time).

Full ADRs in [`BITACORA.md`](./BITACORA.md).

## Vibe Coding Compliance

This entire project was built without the architect editing a single line of code. The audit log is the proof.

- **`prompts.md`** — verbatim record of every architect directive (in original language: Spanish for authenticity).
- **`BITACORA.md`** — Architecture Decision Records (ADR-lite) for every meaningful technical choice.
- **`.session_meta.json`** — `STARTED_AT` timestamp source for elapsed-time hook.
- **`.claude/hooks/elapsed_time.sh`** — Stop hook that emits `Elapsed Time: Xh Ym Zs` at end of every turn.
- **`.claude/hooks/prompt_logger.sh`** — UserPromptSubmit hook that auto-appends prompts to `prompts.md` (deduplicated).
- **`.claude/hooks/safety_gate.sh`** — PreToolUse hook that blocks destructive commands.

The agentic surface in `.claude/` (skills, commands, sub-agents, hooks) is itself a deliverable — see [`docs/AGENTIC_SURFACE.md`](./docs/AGENTIC_SURFACE.md).

## Demo URLs

After `make run-api`, `make run-dashboard`, `make run-mcp`:

| Service | URL |
|---|---|
| API root | http://localhost:8000/ |
| OpenAPI docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| Streamlit dashboard | http://localhost:8501/ |
| MCP server (HTTP optional) | http://localhost:8765/ |

## MCP Integration

To plug this into Claude Desktop or Claude Code, add to your MCP config:

```json
{
  "mcpServers": {
    "finops": {
      "command": "uv",
      "args": ["run", "python", "-m", "finops.mcp_server.server"],
      "cwd": "/absolute/path/to/wk-finops-vibe-coding"
    }
  }
}
```

Then in any MCP-aware client, tools `ingest_billing`, `analyze_billing`, `propose_remediation`, `estimate_savings` are available. Full integration guide: [`docs/MCP_INTEGRATION.md`](./docs/MCP_INTEGRATION.md).

## Submission Checklist

- [x] Public GitHub repository — [andresKillem/wk-finops-vibe-coding](https://github.com/andresKillem/wk-finops-vibe-coding)
- [x] Python-based, API-first, free-tier database (SQLite)
- [x] Ingests AWS/Azure billing exports (JSON/CSV)
- [x] Identifies orphaned resources
- [x] Generates CLI commands / API logic to decommission
- [x] `prompts.md` audit log (verbatim)
- [x] `BITACORA.md` decision log (architectural reasoning)
- [x] AI-generated presentation deck — [`docs/PRESENTATION.md`](./docs/PRESENTATION.md)
- [x] All cloud resources decommissioned: **N/A — offline-only build with synthetic billing data** (cleanest interpretation)
- [ ] Tagle.ai "Tag" output: `<INSERT TAG HERE WHEN AVAILABLE>`

## License

MIT. See [LICENSE](./LICENSE).

---

Built by Andres Munoz · Architect · 2026
