# Cloud Cost Optimizer — Vibe Coding Submission Deck
*Wolters Kluwer 2026 Graduate Vibe Coding Challenge — Project 1*

---

## Slide 1 — Title

**Cloud Cost Optimizer & Remediation Engine**
A FinOps audit pipeline built end-to-end via "Vibe Coding"

- **Architect:** Andres Munoz
- **AI Engineer:** Claude Code (`claude-opus-4-7`)
- **Repo:** [github.com/andresKillem/wk-finops-vibe-coding](https://github.com/andresKillem/wk-finops-vibe-coding)
- **Tagle Tag:** `<INSERT TAG WHEN AVAILABLE>`

---

## Slide 2 — The Problem

> *The average organization wastes 32–40% of its cloud budget on idle resources, oversized instances, and unmonitored services.*
> — FinOps Foundation 2026 State of FinOps Report

**That's $4M annually for every $10M of cloud spend.** Most of it is *known unknowns* — orphaned EBS volumes, dangling Elastic IPs, idle NAT Gateways. Boring. Avoidable. Persistent.

---

## Slide 3 — The Solution

A Python-based, API-first engine that:
1. **Ingests** AWS CUR / Azure billing exports (CSV/JSON).
2. **Detects** orphaned/idle resources via 8 declarative rules.
3. **Scores** risk per resource and aggregate (volume-weighted, calibrated 0–100).
4. **Generates** safe remediation plans in three formats (CLI, boto3, Terraform import).
5. **Orchestrates** sub-agents (Opus + Haiku) for executive narratives and plan enrichment.
6. **Exposes** itself as an MCP server — pluggable into any AI client.

---

## Slide 4 — Architecture

```
Sample CUR/JSON ─▶ FastAPI ─▶ Detector ─▶ Sub-agents (Opus+Haiku) ─▶ Plans
                       │                                              │
                       ▼                                              ▼
                   SQLite                                       Streamlit Dashboard
                       │
                       ▼
                  MCP Server (universal interface)
```

Layered: **Data ⇆ Domain ⇆ Orchestration ⇆ Edge**. SQLite swaps to Postgres without touching domain. Sub-agents replace deterministic fallback transparently.

---

## Slide 5 — Demo 1: Ingest → Scan → Risk Score

```
$ make demo
✓ Ingested 200 billing rows (date range: 2026-04-01 → 2026-04-30)
✓ Resources upserted: 17

✓ Detection complete:
  Findings: 9 (3 HIGH, 4 MEDIUM, 2 LOW)
  Total monthly waste: $312.40
  12mo projection: $3,748.80
  Overall risk score: 67 (significant waste — weekly scan recommended)

  Top 5 offenders:
  1. R-NAT-001  · nat-0abcdef · idle 14d           · $32/mo  · risk 88
  2. R-RDS-001  · db-prod-old · 0 connections 7d   · $90/mo  · risk 96
  3. R-EBS-001  · vol-0abc01  · orphaned 12d       · $80/mo  · risk 84
  4. R-EBS-001  · vol-0abc02  · orphaned 8d        · $80/mo  · risk 78
  5. R-EIP-001  · 54.x.x.x    · dangling 21d       · $3.6/mo · risk 52
```

---

## Slide 6 — Demo 2: Sub-Agents

**Analyzer (Opus, 1 call)** returns:

> *"Three orphaned EBS volumes account for 51% of detected waste. Pattern suggests an EC2 fleet decommissioned in late Q1 left storage behind. The single highest-impact action is reviewing volumes tagged `Project=migration-pilot` — likely 5 more orphans not yet beyond our 7-day threshold."*

**Remediator (Haiku, parallel × N)** enriches each plan:

```
Pre-condition: Volume must remain `available` and not reattached since scan.
Rollback: Restore from snap-0xxxxx (retained 30d).
Stakeholder: :warning: FinOps action — vol-0abc01 (us-east-1a, 100GB gp3, $80/mo)
             Plan: snapshot → delete via aws_cli · Approval: :+1: from infra-on-call
```

---

## Slide 7 — Demo 3: MCP Integration

Add to Claude Desktop / Claude Code config:

```json
{ "mcpServers": { "finops": {
    "command": "uv",
    "args": ["run", "python", "-m", "finops.mcp_server.server"],
    "cwd": "/path/to/repo"
}}}
```

Tools immediately available in any MCP-aware client:
- `ingest_billing(file_path)`
- `analyze_billing()`
- `propose_remediation(finding_id, format)`
- `estimate_savings()`

**Why this matters:** the optimizer becomes a *capability*, not just an app. Cursor, Claude Desktop, custom agents — all consume the same tools.

---

## Slide 8 — Vibe Coding Meta

The architect did not edit a single line of code. The audit log proves it.

| Artifact | What it shows |
|---|---|
| `prompts.md` | Verbatim record of every architect directive (Spanish, authentic) |
| `BITACORA.md` | Architecture Decision Records for every meaningful technical choice |
| `.claude/` | Skills, sub-agents, slash commands, hooks — the AI's operating manual |
| Hooks | `prompt_logger`, `elapsed_time`, `safety_gate` — automatic compliance |

**Considered & rejected** (transparency on scope discipline):
- LangChain/LangGraph — overkill for a fixed 1→N→1 graph.
- n8n — workflow tool, wrong shape for an API-first deliverable.
- Claude Managed Agents — consumes cloud the doc requires us to decommission.
- React frontend — 5x build time vs Streamlit at the same polish.

---

## Slide 9 — Roadmap (if production)

| Phase | What |
|---|---|
| **0 → 1** (MVP, today) | SQLite, sample data, 8 rules, 2 sub-agents, MCP, dashboard |
| **1 → N** (multi-account) | Postgres, OIDC for AWS, scheduled CUR streaming, per-account RBAC |
| **N → governance** | Tag policy enforcement, Cost Anomaly Detection bridge, ChatOps approval flows |
| **Continuous** | Weekly auto-audit, drift-detection on remediated resources, savings attribution |

---

## Slide 10 — Q&A

**Repo:** [github.com/andresKillem/wk-finops-vibe-coding](https://github.com/andresKillem/wk-finops-vibe-coding)
**`prompts.md`:** the full audit log, verbatim.
**`BITACORA.md`:** every architectural decision, with rationale.

Thanks for the opportunity to think through this in public.

---

*Built end-to-end in <6 hours of architect-led, AI-engineered work.*
