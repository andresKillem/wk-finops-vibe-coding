# Cloud Cost Optimizer & Remediation Engine

> **Wolters Kluwer 2026 — Graduate Vibe Coding Challenge · Project 1 (FinOps)**
> Built end-to-end via [Claude Code](https://claude.com/code) under a strict no-manual-edits regime. The architect directs; the AI engineers.

[![Repo](https://img.shields.io/badge/GitHub-andresKillem%2Fwk--finops--vibe--coding-181717?logo=github)](https://github.com/andresKillem/wk-finops-vibe-coding)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-150%20passing-2E7D55)](#tests)
[![Vibe Coding](https://img.shields.io/badge/built%20with-Vibe%20Coding-7B61FF)](./prompts.md)

Ingests AWS Cost & Usage Reports or Azure billing exports → detects orphaned/idle resources via 7 declarative rules → generates safe multi-format decommission plans (`aws_cli`, `boto3`, `terraform_import`) → orchestrates Opus + Haiku sub-agents to produce executive narrative and per-finding enrichment → exposes the same engine as an MCP server pluggable into any AI client.

```
        ◆ Architect: Andres Munoz
        ◆ AI Engineer: Claude Code (claude-opus-4-7)
        ◆ Tagle Tag: The Architect (Navigator edge | Developing)
                     G:63 · A:75 · C:75 · R:72 · I:50
                     "You master what others skim — depth is your edge"
```

> The challenge document opens with: *"You are the architect; the AI is the engineer."* Per the Tagle.ai assessment, my AI-readiness type is also **The Architect** — *"Architects don't settle for surface-level understanding. You build deep expertise and create solid foundations for AI integration. While others experiment at random, you develop mastery that compounds over time."* The two framings line up; this submission is the architect mindset applied end-to-end.

---

## Highlights

- **150 tests passing** across ingestion, detection, remediation, API, sub-agents, and MCP layers.
- **Two-layer hero work**: real Anthropic sub-agents (Opus orchestrator + Haiku workers in parallel) **and** the optimizer exposed as an MCP server.
- **Defense in depth on safety**: settings deny-list + `safety_gate.sh` PreToolUse hook + Python `SafetyGate` validator + `min_confidence` threshold per rule + blast-radius gating.
- **Deterministic fallback** for the entire agent layer — the demo runs without an API key, with the same shape as the LLM path.
- **Architect's audit log** ([`prompts.md`](./prompts.md)) and **AI engineer's decision log** ([`BITACORA.md`](./BITACORA.md)) are deliberately distinct — see ADR-003.

## Quickstart (30 seconds)

```bash
git clone https://github.com/andresKillem/wk-finops-vibe-coding && cd wk-finops-vibe-coding
cp .env.example .env       # optional: add ANTHROPIC_API_KEY for real sub-agents
uv sync --all-extras
make demo                   # ingest sample CUR → scan → analyze → report
```

Three terminals (or split-pane) for the full surface:

```bash
make run-api         # FastAPI on :8000 (OpenAPI docs at /docs)
make run-dashboard   # Streamlit on :8501
make run-mcp         # MCP server (stdio) for any AI client
```

## Architecture

```
                                    ┌─────────────────────────┐
                                    │  Streamlit Dashboard    │
                                    │  5 pages, polished      │
                                    └────────────┬────────────┘
                                                 │ HTTP
                                                 ▼
┌────────────┐    ingest    ┌──────────────────────────────────┐    invoke
│  AWS CUR / │ ────────────▶│      FastAPI Core (REST)         │ ──────────▶  Anthropic
│  Azure JSON│              │  /upload /analyze /remediate ... │              SDK
└────────────┘              │  /agents/analyze  /report  ...   │              (Opus + Haiku)
                            └──────┬─────────────┬─────────────┘
                                   │             │
                          ┌────────▼───┐   ┌─────▼─────────┐         ┌──────────────┐
                          │  Detector  │   │  Sub-agents   │ ──────▶ │ Opus 4.7     │
                          │  7 rules   │   │  Analyzer +   │         │ Haiku 4.5    │
                          │  + scoring │   │  Remediator   │         │ asyncio.gather
                          └────────┬───┘   └─────┬─────────┘         └──────────────┘
                                   │             │
                                   ▼             ▼
                              ┌────────────────────────┐
                              │   SQLite + SQLModel    │
                              │   BillingRecord ·      │
                              │   Resource · Finding · │
                              │   RemediationPlan ·    │
                              │   AgentRun (audit)     │
                              └────────────────────────┘

                    ◆ MCP server (stdio + HTTP) exposes:
                       ingest_billing · analyze_billing
                       propose_remediation · estimate_savings
                       list_findings · finops://findings
                       finops://agent-runs · finops_audit prompt
                    so any MCP-aware client can use this engine as a tool.
```

Layered modules — see [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) for sequence diagrams.

| Layer | Module | Responsibility |
|---|---|---|
| **Edge** | `finops.api`, `finops.dashboard`, `finops.mcp_server` | REST + Streamlit + MCP surfaces |
| **Orchestration** | `finops.agents` | Sub-agent dispatch (Opus orchestrator + Haiku workers) |
| **Domain** | `finops.detection`, `finops.remediation` | Rules engine, risk scoring, plan generation, safety gates |
| **Data** | `finops.db`, `finops.ingestion` | Models, sessions, billing parsers |
| **Cross-cutting** | `finops.config`, `finops.utils` | Settings, demo runner, status renderer |

## Features

| Surface | What it does |
|---|---|
| **Ingestion** | AWS CUR (CSV) and Azure Consumption (JSON); UTF-8-BOM tolerant; idempotent upsert. |
| **Detection** | 7 declarative rules: orphaned EBS / idle EC2 / dangling EIP / idle NAT / idle RDS / unused ELB / legacy-gen instance. Multi-signal confidence calibration with `min_confidence` threshold. |
| **Risk scoring** | `risk_score = severity_weight × confidence × (1 + cost_factor) × 10`. Volume-weighted aggregate. Calibrated labels: Healthy / Attention / Significant waste / Critical. |
| **Remediation** | 18 templates (6 resource types × 3 formats: `aws_cli`, `boto3`, `terraform_import`). Pre-check / snapshot / dry-run / commented execute. Forbidden patterns blocked by `SafetyGate`. |
| **Sub-agents (HERO #1)** | `AnalyzerAgent` (Opus 4.7, 1 call → narrative + ranked top-5) + `RemediatorAgent` (Haiku 4.5, parallel via `asyncio.gather`, max 5 concurrent). Deterministic fallback identical interface. |
| **MCP server (HERO #2)** | 5 tools, 2 resources, 1 prompt template — pluggable into Claude Desktop, Claude Code, Cursor, custom agents. stdio + streamable-http. |
| **Dashboard** | Streamlit, 5 pages: Home (KPIs + donut + trend), Findings (filter + drill-down), Remediation Studio (multi-select + Slack), AI Insights (Opus narrative + Haiku enrichments), System (agent runs audit). |
| **Webhook simulator** | Async POST with 3-attempt exponential backoff; self-loopback `/alert-sink` so the demo runs without external services. |
| **Agentic surface** | `.claude/` with skills, slash commands, sub-agent definitions, hooks (`safety_gate`, `prompt_logger`, `elapsed_time`, `status_line`). All functional, see ADR-004. |
| **CI** | GitHub Actions: `uv sync` + `ruff` + `pytest -m "not integration and not llm"` on every push. |

## Stack & Rationale

| Choice | Why |
|---|---|
| **FastAPI** | OpenAPI auto-generated; native Pydantic; async first-class for parallel sub-agent calls. |
| **SQLite + SQLModel** | Zero infra; SQLModel = Pydantic + SQLAlchemy unified; trivial Postgres upgrade path. ADR-005. |
| **Streamlit** | 5× faster to ship than React for analytical dashboards at this scope. ADR-015. |
| **Anthropic SDK direct** | No LangChain overhead; sub-agents as plain `asyncio` coroutines. ADR-002, ADR-013. |
| **MCP** | Reusable interface; pluggable into any MCP-aware client. Additive to REST, not redundant. ADR-014. |
| **uv** | 10× faster than pip; lockfile included; reproducible installs. |

**Considered & rejected** (transparency on scope discipline):
- **LangGraph** — overkill for a fixed 1→N→1 graph.
- **n8n** — workflow tool, wrong shape for an API-first deliverable.
- **Claude Managed Agents** — consumes cloud the doc explicitly requires us to decommission.
- **React frontend** — 5× build time vs Streamlit at the same polish.

Full ADR catalogue in [`BITACORA.md`](./BITACORA.md) (16 entries covering every meaningful choice).

## Vibe Coding Compliance

The architect did not edit a single line of code. The audit log proves it.

| Artifact | What it shows |
|---|---|
| [`prompts.md`](./prompts.md) | Verbatim record of every architect directive, with English translations of Spanish-language prompts and AI-engineer action summaries. |
| [`BITACORA.md`](./BITACORA.md) | Architecture Decision Records (16 ADRs) for every meaningful technical choice — including the one bug we fixed mid-build (ADR-009). |
| [`.session_meta.json`](./.session_meta.json) | `STARTED_AT` timestamp source for the elapsed-time hook. |
| [`.claude/hooks/elapsed_time.sh`](./.claude/hooks/elapsed_time.sh) | Stop hook emitting `Elapsed Time: Xh Ym Zs` to stderr at end of every turn. |
| [`.claude/hooks/prompt_logger.sh`](./.claude/hooks/prompt_logger.sh) | UserPromptSubmit hook auto-appending prompts (deduplicated). |
| [`.claude/hooks/safety_gate.sh`](./.claude/hooks/safety_gate.sh) | PreToolUse hook blocking `rm -rf`, `aws ec2 terminate`, etc. |

The agentic surface in `.claude/` is itself a deliverable — see [`docs/AGENTIC_SURFACE.md`](./docs/AGENTIC_SURFACE.md).

## Demo URLs

After `make run-api`, `make run-dashboard`, `make run-mcp`:

| Service | URL |
|---|---|
| API root | http://localhost:8000/ |
| OpenAPI docs (Swagger) | http://localhost:8000/docs |
| OpenAPI ReDoc | http://localhost:8000/redoc |
| Health | http://localhost:8000/health |
| Streamlit dashboard | http://localhost:8501/ |
| MCP server (HTTP optional) | http://localhost:8765/ |

## MCP Integration

Add to your Claude Desktop / Claude Code config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "finops": {
      "command": "uv",
      "args": ["run", "python", "-m", "finops.mcp_server"],
      "cwd": "/absolute/path/to/wk-finops-vibe-coding",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Restart the client. Five tools, two resources, and one prompt template appear:

```
Tools:        ingest_billing · analyze_billing · propose_remediation
              estimate_savings · list_findings
Resources:    finops://findings · finops://agent-runs
Prompts:      finops_audit (audience: exec | engineer | compliance)
```

Full integration guide: [`docs/MCP_INTEGRATION.md`](./docs/MCP_INTEGRATION.md).

## Screenshots

<!-- Capture and replace these with real screenshots from the running dashboard -->

| Page | Path |
|---|---|
| Home (KPIs + donut + trend) | `./assets/dashboard-home.png` |
| Findings (filter + drill-down) | `./assets/dashboard-findings.png` |
| Remediation Studio | `./assets/dashboard-remediation.png` |
| AI Insights (Opus narrative + Haiku enrichments) | `./assets/dashboard-ai-insights.png` |
| System (agent runs audit) | `./assets/dashboard-system.png` |
| MCP client demo output | `./assets/mcp-client-demo.png` |

To regenerate: run `make run-api` + `make run-dashboard`, capture each page, and drop into `./assets/`.

## Submission Checklist

- [x] Public GitHub Repository — [andresKillem/wk-finops-vibe-coding](https://github.com/andresKillem/wk-finops-vibe-coding)
- [x] Python-based, API-first, free-tier database (SQLite)
- [x] Ingests AWS / Azure billing exports (JSON / CSV)
- [x] Identifies orphaned resources
- [x] Generates CLI commands / API logic to decommission
- [x] [`prompts.md`](./prompts.md) verbatim audit log
- [x] [`BITACORA.md`](./BITACORA.md) decision log (architectural reasoning)
- [x] AI-generated presentation deck — [`docs/PRESENTATION.md`](./docs/PRESENTATION.md)
- [x] All cloud resources decommissioned: **N/A — offline-only build with synthetic billing data** (cleanest interpretation; nothing was provisioned)
- [x] Tagle.ai "Tag" output: **The Architect (Navigator edge, Developing)** — Growth 63 · Autonomy 75 · Competence 75 · Relatedness 72 · Innovation 50 — [result link](https://tagle.ai/quiz/result?g=63&a=75&c=75&r=72&i=50)

## Tests

```bash
make test           # 150 tests
make test-fast      # excludes integration/llm
make lint           # ruff
make check-all      # lint + typecheck + tests
```

| Test file | Coverage | Cases |
|---|---|---|
| `test_ingestion.py` | AWS CUR / Azure JSON parsers, edge cases, idempotency | 30 |
| `test_detection.py` | 7 rules positive + negative, scoring, calibration, engine | 28 |
| `test_remediation.py` | every (type × format), forbidden-pattern guard, safety gate | 33 |
| `test_api.py` | every route, request-id, OpenAPI presence, alert sink | 16 |
| `test_agents.py` | JSON extraction, cost estimation, fallback + mocked LLM, orchestrator | 14 |
| `test_mcp.py` | tool/resource/prompt registration, direct callability | 11 |
| **Total** | | **150** |

## License

MIT. See [LICENSE](./LICENSE).

## Author

**Andres Munoz** · architect, with [Claude Code](https://claude.com/code) (`claude-opus-4-7`) as the AI engineer.

Submission for the Wolters Kluwer 2026 Graduate Vibe Coding Challenge — Architecture and Engineering Services. Questions: kash.kashyap@wolterskluwer.com.
