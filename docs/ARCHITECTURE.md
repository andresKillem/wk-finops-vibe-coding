# Architecture

This project is a layered Python application: data → domain → orchestration → edge. Every layer can be replaced independently because boundaries are explicit and the interfaces narrow.

## High-level diagram

```mermaid
graph TB
    subgraph Edges
        DASH[Streamlit Dashboard<br/>:8501]
        MCPC[MCP Client<br/>Claude Desktop · Cursor · Code]
        CLI[finops CLI<br/>typer-based]
    end

    subgraph Surfaces
        API[FastAPI :8000<br/>/upload /analyze /remediate /report /agents /alerts]
        MCPS[MCP Server<br/>stdio + streamable-http]
    end

    subgraph Orchestration
        ORCH[Orchestrator<br/>asyncio.gather · max 5 concurrent]
        ANL[AnalyzerAgent<br/>Opus 4.7 · 1 call]
        REM[RemediatorAgent<br/>Haiku 4.5 · N parallel]
    end

    subgraph Domain
        ING[Ingestion<br/>AWS CUR · Azure JSON]
        DET[Detection<br/>7 rules · scoring]
        REMG[Remediation<br/>18 templates · SafetyGate]
    end

    subgraph Data
        DB[(SQLite<br/>BillingRecord<br/>Resource · Finding<br/>RemediationPlan<br/>AgentRun)]
    end

    subgraph External
        ANTH[Anthropic API]
        WH[Webhook URL<br/>self-loopback /alert-sink]
    end

    DASH -->|httpx| API
    MCPC -->|MCP protocol| MCPS
    CLI -->|in-process| ING
    CLI -->|in-process| DET
    CLI -->|in-process| ORCH

    API --> ING
    API --> DET
    API --> ORCH
    API --> REMG
    API --> WH

    MCPS --> ING
    MCPS --> DET
    MCPS --> ORCH
    MCPS --> REMG

    ORCH --> ANL
    ORCH --> REM
    ANL --> ANTH
    REM --> ANTH

    ING --> DB
    DET --> DB
    ORCH --> DB
    REMG --> DB

    style ANL fill:#1B365D,color:#fff
    style REM fill:#3B5B8A,color:#fff
    style MCPS fill:#7B61FF,color:#fff
    style API fill:#2E7D55,color:#fff
```

## Layered modules

| Layer | Module | Responsibility | Boundary |
|---|---|---|---|
| **Edge** | `finops.api` | REST surface (FastAPI), request validation, response shaping | HTTP |
| | `finops.dashboard` | Streamlit UI; talks to API only (ADR-015) | HTTPS |
| | `finops.mcp_server` | MCP tools/resources/prompts | stdio · streamable-http |
| **Orchestration** | `finops.agents` | Sub-agent dispatch + audit (Opus + Haiku + reviewer) | Anthropic SDK |
| **Domain** | `finops.detection` | Rules engine, risk scoring | DB-only |
| | `finops.remediation` | Plan generation, SafetyGate | DB-only |
| **Data** | `finops.db` | Models (SQLModel), session lifecycle | DB |
| | `finops.ingestion` | AWS CUR + Azure parsers | Filesystem in / DB out |
| **Cross-cutting** | `finops.config` | Settings (pydantic-settings), `.env`-loaded | Process env |
| | `finops.utils` | Demo runner, status renderer | n/a |

## Data model

```mermaid
erDiagram
    BillingRecord ||--|{ Resource : "deduped from"
    Resource ||--o{ Finding : "produces"
    Finding ||--o{ RemediationPlan : "remediated by"
    AgentRun }o--|| AgentRun : "audit-only"

    BillingRecord {
        int id PK
        string cloud_provider
        string account_id
        string service
        string resource_id FK
        string region
        float usage_amount
        float cost
        datetime period_start
        datetime period_end
        json raw_record
        datetime ingested_at
    }
    Resource {
        int id PK
        string resource_id UK
        string type
        string state
        string region
        string account_id
        string cloud_provider
        datetime last_seen
        float monthly_cost
        json attrs
    }
    Finding {
        int id PK
        string resource_id FK
        string rule_id
        string severity
        string description
        float savings_estimate
        float risk_score
        float confidence
        json attrs
        datetime created_at
    }
    RemediationPlan {
        int id PK
        int finding_id FK
        string format
        json commands
        string blast_radius
        string status
        string rendered
        datetime created_at
    }
    AgentRun {
        int id PK
        string agent_name
        string model
        string prompt
        string response
        int tokens_in
        int tokens_out
        int duration_ms
        float cost_estimate
        datetime created_at
    }
```

## Sequence — `/audit` end-to-end

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as FastAPI
    participant ING as Ingestion
    participant DET as Detection
    participant ORC as Orchestrator
    participant ANL as AnalyzerAgent (Opus)
    participant REM as RemediatorAgent×N (Haiku)
    participant DB as SQLite
    participant WH as Webhook

    U->>API: POST /upload (sample CSV)
    API->>ING: ingest_file(path)
    ING->>DB: insert BillingRecord rows · upsert Resource
    ING-->>API: IngestSummary
    API-->>U: 200 {rows_parsed, resources_upserted}

    U->>API: POST /analyze
    API->>DET: run_scan()
    DET->>DB: read Resource + BillingRecord
    DET->>DB: write Finding (with risk_score)
    DET-->>API: ScanResult (aggregate)
    API->>WH: emit if overall_risk ≥ threshold
    API-->>U: 200 {findings, by_severity, top_5_offenders}

    U->>API: POST /agents/analyze?top_n=5
    API->>ORC: run(top_n=5)
    ORC->>ANL: run(findings)
    ANL->>Anthropic API: messages.create (Opus)
    Anthropic API-->>ANL: narrative + top_5
    ORC->>REM: run(finding_i, base_plan) (parallel × N)
    Note over REM,Anthropic API: asyncio.gather + Semaphore(5)
    REM-->>ORC: enrichment per finding
    ORC->>DB: persist AgentRun rows (audit)
    ORC-->>API: {summary, analyzer, remediations}
    API-->>U: 200 (full orchestration result)

    U->>API: POST /remediate/{id}?fmt=aws_cli
    API->>RemediationGenerator: build_plan(id, fmt)
    RemediationGenerator->>SafetyGate: validate
    RemediationGenerator->>DB: persist RemediationPlan
    RemediationGenerator-->>API: rendered markdown
    API-->>U: 200 {commands, blast_radius, rendered}
```

## Sequence — MCP client interaction

```mermaid
sequenceDiagram
    participant Client as MCP Client (Claude Code)
    participant Server as finops MCP Server (stdio)
    participant Engine as finops domain layer

    Client->>Server: initialize
    Server-->>Client: capabilities (tools, resources, prompts)
    Client->>Server: list_tools
    Server-->>Client: 5 tools
    Client->>Server: read_resource(finops://findings)
    Server->>Engine: query Finding rows
    Engine-->>Server: JSON
    Server-->>Client: resource content
    Client->>Server: call_tool(estimate_savings)
    Server->>Engine: aggregate_score
    Engine-->>Server: aggregate dict
    Server-->>Client: tool result
```

## Why this architecture

- **API-first** because the doc requires it, and because it's the only sane way to support multiple frontends (Streamlit, MCP, future React).
- **Layer separation** so the data layer can move from SQLite to Postgres without touching detection or agents.
- **Sub-agents over single-prompt** because (a) cost — 1 Opus call beats N Opus calls; (b) parallelism — `asyncio.gather` over Haiku workers; (c) failure isolation — one bad finding fails one Haiku, others continue. ADR-002, ADR-013.
- **MCP alongside REST** because the targets are different — humans/dashboards vs AI clients. Same engine, two doors. ADR-014.
- **Deterministic fallback** so the demo never depends on a working API key. ADR-007.

## Failure isolation

| Failure | What happens | Recovery |
|---|---|---|
| Anthropic API key invalid | Sub-agents use deterministic fallback path. Output shape identical. | Provide a valid key; system flips automatically (no code change). |
| One Haiku call crashes mid-orchestration | `asyncio.gather` resolves the survivors; result includes only successful enrichments. | None needed — Analyzer narrative still produced. |
| Detection rule throws | Caught at `DetectionEngine.scan` level; that rule's findings missing for one resource. | Fix and re-scan. Other rules unaffected. |
| Webhook URL unreachable | `WebhookEmitter.send` retries 3× with exponential backoff, returns `{sent: false, error: ...}`. Analyze response unaffected. | Update `WEBHOOK_URL`. |
| Bad CSV row | Parser counts in `summary.skipped`, records line number in `summary.errors`, continues. | Inspect errors; fix source data. |

## Performance characteristics

Measured on the bundled 17-resource / 228-line sample (Apple Silicon, Python 3.11.14):

| Operation | Wall-clock |
|---|---|
| Ingest (sample CUR) | ~0.05s |
| Scan (7 rules × 17 resources) | ~0.05s |
| Generate one remediation plan | ~0.01s |
| Orchestrate fallback (3 enrichments) | ~0.05s |
| Orchestrate LLM (1 Opus + 3 Haiku parallel) | ~25s |
| Full demo (`make demo`) in fallback | ~0.3s |
| Test suite (150 tests) | ~5s |

Cost (LLM): **~$0.15 per audit** at the Opus-orchestrator + Haiku-workers topology. ROI > 140× on the bundled sample.

## File map

See [`docs/AGENTIC_SURFACE.md`](./AGENTIC_SURFACE.md) for the `.claude/` agentic surface — that's part of the architecture, not a side concern.
