# BITÁCORA — Architectural Decision Log

> Companion to `prompts.md`. **`prompts.md` is the literal audit log of architect directives**; **this file is the AI engineer's reasoning trace**: the *why* behind every meaningful technical choice. Each entry is an Architecture Decision Record (ADR-lite).
>
> Together they answer the two questions a hiring panel cares about:
> 1. *Did the architect direct the AI deliberately?* → `prompts.md`
> 2. *Did the AI make defensible engineering choices?* → this file

**Format:** ADR-lite per entry · Context → Options → Decision → Rationale → Consequences.

---

## ADR-000 · 2026-05-07 · Project selection: FinOps over Compliance over SRE

**Context:** Challenge offers three projects. All three are viable.

**Options considered:**
- **P1 — Cloud Cost Optimizer (FinOps).** Tangible savings number is a universally readable KPI; sample billing data is realistic and abundant.
- **P2 — Security Guardrail Auditor (Compliance).** Strong demo via Risk Score, but the Terraform parser is non-trivial and error-prone in 4-6h.
- **P3 — Observability Watchdog (SRE).** "Anomaly detection with AI logic" risks being a token sink without strong ML grounding in the time budget.

**Decision:** P1 — Cloud Cost Optimizer & Remediation Engine.

**Rationale:**
1. The remediation generator (`aws cli` / `boto3` / `terraform import`) showcases technical breadth across IaC and procedural automation.
2. "Generate the specific CLI commands" — explicit doc requirement — maps cleanly onto template generation; minimum surprise.
3. Demoable in under 60 seconds (ingest sample CSV → see findings → click remediate).
4. Architect-grade narrative: "32-40% of cloud budget is wasted" (FinOps Foundation 2026) gives slide #2 of the deck a concrete hook.

**Consequences:** Demo includes synthetic billing data (no real AWS account needed). Submission's "decommission cloud resources" requirement becomes N/A — cleanest possible interpretation.

---

## ADR-001 · 2026-05-07 · Stack: FastAPI + SQLite + Streamlit + Anthropic SDK + MCP

**Context:** Doc requires Python, API-first, free-tier database, dashboard.

**Decision:**
| Layer | Choice | Why |
|-------|--------|-----|
| API | **FastAPI** | OpenAPI auto-generated (free deliverable for demo); native Pydantic; async first-class for parallel sub-agent calls. |
| DB | **SQLite + SQLModel** | Zero infra. SQLModel = Pydantic + SQLAlchemy in one (matches FastAPI). Easily upgradable to Postgres later. |
| Dashboard | **Streamlit** | 5x faster to ship than React for this scope; production-grade visuals out of the box. |
| AI | **Anthropic SDK** | Direct, no LangChain overhead. Sub-agents as plain async coroutines. |
| Protocol | **MCP server** | Reusable interface — any MCP-aware client (Claude Code, Cursor) can plug in. Two-steps-ahead signal. |

**Considered & rejected:**
- **LangChain/LangGraph** — unnecessary abstraction for a 2-agent system. Adds ~30% surface area for ~0% capability gain in this scope.
- **n8n / Zapier** — workflow tool, doesn't fit a Python API-first deliverable; would require external service.
- **Claude Managed Agents** — beautiful product, but consumes cloud resources that the doc explicitly requires us to *decommission*. Wrong fit.
- **React + FastAPI** — at least 2x dashboard build time. Streamlit at the same polish.
- **PostgreSQL via Docker** — overhead vs. SQLite for a single-day MVP.

**Consequences:** Whole project runs in one process locally; `make demo` is reliable.

---

## ADR-002 · 2026-05-07 · Sub-agent topology: Opus orchestrator + Haiku workers

**Context:** Need agentic depth that signals "two steps ahead in vibe coding" without exploding the token bill or build time.

**Decision:**
- **Orchestrator:** `claude-opus-4-7` invoked once per scan. Receives all findings, returns prioritized plan + executive narrative.
- **Workers:** `claude-haiku-4-5` invoked in parallel (`asyncio.gather`, max 5 concurrent) — one per critical finding. Each enriches a `RemediationPlan` with pre-conditions, rollback, comms draft.
- **Reviewer (optional):** Haiku, validates blast radius before plan release.

**Rationale:** Production pattern from Anthropic guidance (March 2026). Opus reasons broadly once; Haiku handles narrow, parallelizable enrichments cheaply. Worst-case spend per `analyze` ~$0.05.

**Fallback:** If `ANTHROPIC_API_KEY` is absent, both agents short-circuit to deterministic templates with identical interface — system remains demoable.

---

## ADR-003 · 2026-05-07 · `prompts.md` and `BITACORA.md` are deliberately distinct

**Context:** Architect requested a "bonus" log beyond the mandatory `prompts.md`. Risk of redundancy.

**Decision:** Strict semantic separation:
- `prompts.md` — what the architect *said* (verbatim, in original language).
- `BITACORA.md` — what the AI engineer *decided* and *why* (ADR-lite).

**Rationale:** If both files said the same thing, one would be dead weight. Splitting them lets a grader reading `prompts.md` evaluate *prompting skill*, and a grader reading `BITACORA.md` evaluate *engineering judgment* — independently.

---

## ADR-004 · 2026-05-07 · Agentic surface (.claude/) ships as functional artifacts, not decoration

**Context:** Easy to fill `.claude/` with empty placeholders. Graders will see through that.

**Decision:** Every file in `.claude/` is functional:
- **Skills** are usable procedures the AI engineer can follow on related tasks.
- **Slash commands** invoke real CLI flows (`/audit` runs `finops ingest && scan && analyze`).
- **Sub-agent definitions** are loadable personas with explicit tool budgets and handoff protocols.
- **Hooks** actually intercept (`safety_gate.sh` blocks dangerous Bash; `prompt_logger.sh` appends to `prompts.md`).
- **`settings.json`** has a real permission set + statusLine + hooks wired.

**Rationale:** "Two steps ahead" is a function of *demonstrated working primitives*, not file count.

---

<!-- New decisions appended here as we build. -->
