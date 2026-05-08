# Cloud Cost Optimizer — Vibe Coding Submission Deck
*Wolters Kluwer 2026 Graduate Vibe Coding Challenge — Project 1 (FinOps)*

> Render this markdown with any deck tool (Marp, Pandoc-Beamer, Slides) or read inline. Each `---` separates one slide.

---

## Slide 1 — Title

**Cloud Cost Optimizer & Remediation Engine**
A FinOps audit pipeline built end-to-end via "Vibe Coding"

- **Architect:** Andres Munoz
- **AI Engineer:** Claude Code (`claude-opus-4-7`, 1M context)
- **Tagle Tag:** **The Architect** (Navigator edge · Developing) — G:63 · A:75 · C:75 · R:72 · I:50
- **Repo:** [github.com/andresKillem/wk-finops-vibe-coding](https://github.com/andresKillem/wk-finops-vibe-coding)
- **Submission date:** 2026-05-08

> *"Architects don't settle for surface-level understanding. You build deep expertise and create solid foundations for AI integration."* — Tagle.ai
>
> The challenge says *"You are the architect; the AI is the engineer."* The Tagle assessment independently flagged the same type. This deck and the work behind it are the architect mindset applied end-to-end.

---

## Slide 2 — The Problem

> *The average organization wastes 32–40% of its cloud budget on idle resources, oversized instances, and unmonitored services.*
> — FinOps Foundation, *2026 State of FinOps Report*

That's **$3–4M annually** for every $10M of cloud spend. Most of it is *known unknowns* — orphaned EBS volumes, dangling Elastic IPs, idle NAT Gateways. Boring. Avoidable. Persistent.

The blockers are not technical. They are organisational:
1. Detection is per-team and ad hoc.
2. Remediation requires writing a runbook by hand.
3. Approvals stall because nobody knows the blast radius.

---

## Slide 3 — The Solution

A Python-based, API-first engine that:

1. **Ingests** AWS CUR / Azure billing exports (CSV / JSON).
2. **Detects** orphaned and idle resources via 7 declarative rules.
3. **Scores** risk per resource and aggregate (volume-weighted, calibrated 0–100).
4. **Generates** safe remediation plans in three formats (`aws_cli`, `boto3`, `terraform_import`).
5. **Orchestrates** Opus + Haiku sub-agents to produce executive narrative and per-finding enrichment.
6. **Exposes** itself as an MCP server — pluggable into any AI client.

```
sample CSV ─▶ detect ─▶ score ─▶ analyze (Opus) ─▶ enrich (Haiku × N) ─▶ approve ─▶ act
```

Demo timing: **27 seconds end-to-end** with real Anthropic calls. **<1 second** in deterministic fallback mode.

---

## Slide 4 — Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  EDGE                Streamlit · FastAPI · MCP · CLI         │
├──────────────────────────────────────────────────────────────┤
│  ORCHESTRATION       Orchestrator (asyncio.gather, 5 max)    │
│                      ├─ AnalyzerAgent (Opus, 1 call)         │
│                      └─ RemediatorAgent × N (Haiku, parallel)│
├──────────────────────────────────────────────────────────────┤
│  DOMAIN              detection (7 rules, scoring) ·          │
│                      remediation (18 templates, SafetyGate)  │
├──────────────────────────────────────────────────────────────┤
│  DATA                ingestion (CUR + Azure) · SQLite        │
└──────────────────────────────────────────────────────────────┘
```

Each layer can be replaced independently. SQLite → Postgres? Touch only data layer. Add Cursor as a client? It already works (MCP). Add LangGraph for orchestration? Wrap `Orchestrator.run` once, leave the agents alone.

---

## Slide 5 — Demo 1: Ingest → Scan → Risk Score

```
$ make demo
✓ Ingested 228 billing rows (date range: 2026-04-01 → 2026-04-30)
✓ Resources upserted: 17

Detection complete:
  Findings: 8 (HIGH:4 MEDIUM:3 LOW:1)
  Total monthly waste: $92.34
  Annual projection:   $1108.08
  Overall risk score:  61.01 (Significant waste — weekly scan recommended)

  Top 5 offenders:
  1. R-NAT-001  · nat-...60002    · idle 14d            · $12.96/mo · risk 90.4
  2. R-RDS-001  · legacy-mysql-old · 0 connections 7d   · $24.19/mo · risk 89.4
  3. R-EBS-001  · vol-...60005    · orphaned            · $6.00/mo  · risk 84.8
  4. R-EBS-001  · vol-...60004    · orphaned            · $4.00/mo  · risk 83.2
  5. R-EC2-001  · i-...567803     · idle r5.large       · $34.47/mo · risk 34.3
```

Bundled sample: 17 deliberately mixed resources (3 attached EBS / 2 orphaned, 4 EC2 of varying state, 2 EIPs, 2 NATs, 2 RDS, 2 ELBs, 1 legacy `t2.medium`).

---

## Slide 6 — Demo 2: Sub-Agents (Real Anthropic Calls)

**AnalyzerAgent (Opus 4.7, 1 call, 21 seconds, $0.14)** returns:

> *"Eight findings total $92.34/mo in recoverable spend, with idle compute and a barely-used NAT Gateway driving 77% of the waste."*

> *"The pattern — an idle legacy MySQL RDS, an idle r5.large, two orphaned EBS volumes, an unassociated EIP, and a NAT Gateway that moved 1.2 MB — strongly suggests a decommissioned or abandoned environment (likely a stage/legacy stack) where compute was torn down but networking and storage scaffolding were left behind."*

> *"Quick wins are unusually safe here: $26.56/mo sits in fully orphaned/unassociated resources at confidence 1.0, recoverable with near-zero blast radius before touching anything still attached to a workload."*

**RemediatorAgent (Haiku 4.5, parallel × 3, $0.007)** enriches each plan:

```
Pre-condition: Verify the volume remains 'available' and not reattached since the last scan.
Rollback procedure (3 steps): create snapshot · restore from snapshot · reattach to source.
Stakeholder communication (Slack-ready): :warning: FinOps action — vol-...
Adjacent optimisations:
  • Audit other r5.large instances in us-east-1 for similar idle patterns.
  • Consider auto-stop policy for instances tagged Lifecycle=idle.
```

**Cost lens:** $0.15/audit. ROI on this sample: **140×**. (Detected savings: $1,108/yr; weekly audit cost: $7.80/yr.)

---

## Slide 7 — Demo 3: MCP Integration

**One config block. Zero glue code.**

```json
{
  "mcpServers": {
    "finops": {
      "command": "uv",
      "args": ["run", "python", "-m", "finops.mcp_server"],
      "cwd": "/path/to/wk-finops-vibe-coding"
    }
  }
}
```

Tools that immediately appear in Claude Code / Claude Desktop / Cursor:

| Tool | Purpose |
|---|---|
| `ingest_billing(file_path)` | Load a billing export |
| `analyze_billing(top_n=5)` | Run scan + Opus + Haiku orchestrator |
| `propose_remediation(finding_id, format)` | Render plan in `aws_cli` / `boto3` / `terraform_import` |
| `estimate_savings()` | Aggregate metrics |
| `list_findings(severity, limit)` | Filterable listing |

Plus resources `finops://findings` + `finops://agent-runs`, and a parameterised `finops_audit` prompt with `audience: exec | engineer | compliance`.

**Why this matters:** the optimizer becomes a *capability*, not just an app. Cursor, Claude Desktop, custom agents — all consume the same tools.

---

## Slide 8 — Vibe Coding Meta

The architect did not edit a single line of code. The audit log proves it.

**`prompts.md` stats** (at submission):
- 12 architect directives logged verbatim
- Spanish-language prompts preserved with English translations
- 11 commits across 8 layers, all AI-generated

**`BITACORA.md` stats:**
- 16 ADRs covering every meaningful technical choice
- Includes one mid-build bug fix (ADR-009 — `min_confidence` threshold caught a false-positive in smoke testing)
- Includes one cost-quality measurement (ADR-013 — actual Anthropic spend on real audit)

**Considered & rejected** (transparency on scope discipline):

| Option | Why not |
|---|---|
| LangGraph | Overkill for a fixed 1→N→1 graph |
| n8n | Workflow tool, wrong shape for an API-first deliverable |
| Claude Managed Agents | Consumes cloud the doc explicitly requires us to decommission |
| React frontend | 5× build time vs Streamlit at the same polish |

**Defense in depth on safety**: settings deny-list + `safety_gate.sh` PreToolUse hook + Python `SafetyGate` validator + `min_confidence` per-rule threshold + blast-radius gating override.

---

## Slide 9 — Roadmap (if production)

| Phase | What |
|---|---|
| **0 → 1** *(MVP, today)* | SQLite, sample data, 7 rules, 2 sub-agents, MCP, 5-page dashboard |
| **1 → multi-account** | Postgres, OIDC for AWS, scheduled CUR streaming, per-account RBAC |
| **multi-account → governance** | Tag policy enforcement, Cost Anomaly Detection bridge, ChatOps approval flows |
| **continuous** | Weekly auto-audit, drift-detection on remediated resources, savings attribution |

**Specific next steps that fit our architecture without rewrites:**

1. Replace SQLite with Postgres — only the engine creation in `db/session.py` changes.
2. Add multi-tenant isolation — Resource adds `tenant_id`; queries filter on it.
3. Stream CUR via S3 events — new ingestion entrypoint, same Resource model.
4. Add a Reviewer sub-agent (already defined in `.claude/agents/reviewer-agent.md`) to gate high-blast-radius plans before publishing.
5. Add Cost Anomaly Detection bridge — read AWS native events, surface as Findings.

Architecture survives all of this because boundaries are thin and explicit.

---

## Slide 10 — Q&A + Thanks

**Repo:** [github.com/andresKillem/wk-finops-vibe-coding](https://github.com/andresKillem/wk-finops-vibe-coding)
**`prompts.md`:** the full audit log, verbatim, with English translations.
**`BITACORA.md`:** 16 ADRs documenting every decision and one fixed bug.
**`docs/MCP_INTEGRATION.md`:** copy-paste config to plug into any MCP client.

**By the numbers:**
- 8 layers shipped
- 11 commits
- ~6,800 lines of Python
- 150 tests passing
- 16 ADRs
- 1 working MCP server
- 1 working multi-page dashboard
- 1 architect, 0 manual edits

Thanks for the opportunity to think through this in public. Questions to: kash.kashyap@wolterskluwer.com.

---

*Built end-to-end in <8 hours of architect-led, AI-engineered work.*
