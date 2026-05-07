# Architecture

## High-level

```
                              ┌────────────────────────────┐
                              │     Streamlit Dashboard    │
                              │  Home · Findings · Plans · │
                              │  AI Insights · System      │
                              └─────────────┬──────────────┘
                                            │ HTTP
                                            ▼
┌──────────────────┐   ┌───────────────────────────────────────────┐   ┌────────────────┐
│  Sample CUR/JSON │──▶│            FastAPI Core (REST)            │──▶│  Anthropic SDK │
│  AWS / Azure     │   │  /upload /analyze /remediate /report ...  │   │  Opus + Haiku  │
└──────────────────┘   └────┬───────────────┬──────────────────────┘   └────────────────┘
                            │               │
                  ┌─────────▼────┐   ┌──────▼──────────┐         ┌──────────────────┐
                  │   Detector   │   │  Sub-agents     │ ──────▶ │  Webhook (sim)   │
                  │   8 rules    │   │  (Orchestrator) │         │  on risk > 70    │
                  └─────────┬────┘   └──────┬──────────┘         └──────────────────┘
                            │               │
                            ▼               ▼
                       ┌──────────────────────────┐
                       │ SQLite + SQLModel        │
                       │ Resource · BillingRecord │
                       │ Finding  · RemediationPlan
                       │ AgentRun                 │
                       └──────────────────────────┘

                  ◆ MCP server: ingest_billing · analyze_billing
                                propose_remediation · estimate_savings
```

## Layered modules

| Layer | Module | Responsibility |
|---|---|---|
| Edge | `finops.api` | REST surface (FastAPI), request validation, response shaping |
| Orchestration | `finops.agents` | Sub-agent dispatch (Opus orchestrator + Haiku workers + reviewer) |
| Domain | `finops.detection`, `finops.remediation` | Rules engine, risk scoring, plan generation, safety gates |
| Data | `finops.db`, `finops.ingestion` | Models, sessions, billing parsers |
| Adapters | `finops.mcp_server`, `finops.dashboard` | Alternate frontends (MCP for agents, Streamlit for humans) |
| Cross-cutting | `finops.config`, `finops.utils` | Settings, demo runner, status renderer |

## Sequence — `/audit`

```
User → /audit samples/aws_cur_sample.csv
       │
       │ 1. ingest
       ▼
   ingestion.router.ingest_file
       │ 2. parse + upsert
       ▼
   db (BillingRecord + Resource)
       │ 3. scan
       ▼
   detection.engine.run_scan
       │ 4. rule fan-out + score
       ▼
   db (Finding × N)
       │ 5. orchestrate
       ▼
   agents.orchestrator.run
       ├─→ agents.analyzer (Opus, 1 call)        → narrative + top_5
       └─→ agents.remediator × N (Haiku, parallel) → enrichment per finding
       │ 6. assemble
       ▼
   final report (markdown + JSON)
       │ 7. (optional) webhook if overall_risk > threshold
       ▼
   POST WEBHOOK_URL
```

## Data model — entity-relationship

```
BillingRecord ────M:1────▶ Resource ────1:M────▶ Finding ────1:1────▶ RemediationPlan
                                                         │
                                                         └──────M:1──────▶ AgentRun
                                                                  (audit trail of LLM calls)
```

## Agentic surface (`.claude/`)

The `.claude/` directory is part of the architecture, not a separate concern. Skills, commands, sub-agent definitions, and hooks are *first-class artifacts* the AI engineer can interact with at every step. See [`AGENTIC_SURFACE.md`](./AGENTIC_SURFACE.md) for the narrative.

## Why this architecture

- **API-first** because the doc requires it, and because it's the only sane way to support multiple frontends (Streamlit, MCP, future React).
- **Layer separation** so the data layer can move from SQLite to Postgres without touching detection or agents.
- **Sub-agents over single-prompt** because (a) cost — 1 Opus call beats N Opus calls; (b) parallelism — `asyncio.gather` over Haiku workers; (c) failure isolation — one bad finding fails one Haiku, others continue.
- **Deterministic fallback** so the demo never depends on a working API key.
