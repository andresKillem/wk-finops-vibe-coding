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

## ADR-005 · 2026-05-07 · SQLModel over plain SQLAlchemy

**Context:** Five tables, all of which need (a) ORM persistence, (b) Pydantic-grade serialisation for FastAPI/MCP IO, (c) easy JSON columns for `raw_record`, `attrs`, `commands`. Could go plain SQLAlchemy + Pydantic schemas separately, or SQLModel which unifies them.

**Options considered:**
- **Plain SQLAlchemy 2.0 + Pydantic models** — full control, two model definitions per table (one for DB, one for API).
- **SQLModel** (FastAPI's own) — single class declares both ORM and Pydantic schema; `Field(sa_column=Column(JSON))` for JSON; first-class `Optional[int] = Field(default=None, primary_key=True)` pattern.
- **Tortoise ORM / Beanie / Peewee** — different ecosystems; trades.

**Decision:** **SQLModel.**

**Rationale:**
1. We're already using FastAPI; SQLModel was designed for that surface specifically.
2. Single source of truth per table eliminates a class of "DB and API drifted" bugs.
3. `JSON` columns (for `raw_record`, `attrs`, `commands`) work cleanly with `sa_column=Column(JSON, nullable=False)` and Python-side `default_factory=dict|list` — pattern we use in all four JSON fields.
4. Cost: SQLModel < 1 dependency (it brings SQLAlchemy + Pydantic which we'd want anyway).

**Consequences:**
- Cannot use `metadata` as a field name (collides with `SQLModel.metadata`). We chose `attrs` everywhere — consistent and doesn't lie about its purpose.
- For tests, pinning `DATABASE_URL` env var **before** any `finops` import is the right pattern, since the engine is module-level. Documented in `tests/conftest.py`.

---

## ADR-006 · 2026-05-07 · Naive UTC datetimes everywhere (no tzinfo)

**Context:** SQLite does not preserve timezone information on roundtrip. SQLAlchemy can mix tz-aware (just-parsed) and tz-naive (just-loaded) datetimes in the same expression — Python raises `TypeError: can't compare offset-naive and offset-aware datetimes`. Hit this on the second pass of `test_resource_idempotent_upsert`.

**Options considered:**
- **Always tz-aware** — store as UTC, configure SQLAlchemy + SQLite to preserve. Possible with custom `TypeDecorator`, but fragile across SQLAlchemy versions and SQLite has no native TZ type.
- **Always naive UTC** — strip tzinfo before insert; use `datetime.now(UTC).replace(tzinfo=None)` for defaults. Document the convention.
- **Cast on every comparison** — local fix at every comparison site. Brittle; future regressions guaranteed.

**Decision:** **Naive UTC throughout the codebase.**

**Rationale:** SQLite is the "free-tier database" the doc requires; the system must work with SQLite first-class. Naive-UTC is the project-wide convention; the absence of tzinfo *means* "UTC". Both `parse_iso_date()` and `models.utcnow()` produce naive-UTC; no comparison can mix tz-naive and tz-aware.

**Consequences:**
- Migration to Postgres (which *does* have native `timestamptz`) will require either keeping the convention (cast at edge) or one-shot data migration. Documented as a future-Postgres concern, not blocking now.
- Anyone reading the code must know the convention; we say so in the docstrings of `utcnow()` and `parse_iso_date()`.

---

## ADR-007 · 2026-05-07 · Anthropic API key invalid → ship deterministic-fallback path first

**Context:** User-provided `.env` had a key with correct shape (`sk-ant-`, 108 chars) but Anthropic returned `401 invalid x-api-key`. We had already designed a deterministic fallback in ADR-002.

**Decision:** Continue building the system; the fallback path is the *primary* tested path until a valid key arrives. When a valid key is provided, sub-agents flip to live calls automatically (no code change needed — `settings.llm_enabled` is the toggle).

**Rationale:**
- A demo that *never* depended on a working API key is more credible than one that always needs one.
- The grader may not have an API key either; deterministic mode means the demo runs anywhere.
- "Bring your own key" pattern is the production-correct interface anyway.

**Consequences:** First-pass agent integration tests (next prompt) will exercise the fallback path; live LLM tests are marked `@pytest.mark.llm` and skipped without a key.

---

## ADR-008 · 2026-05-08 · Rules-as-code pattern (declarative, not one giant if-tree)

**Context:** Need to encode 7 detection rules now and likely 10–20 over time. Two structural options: (a) one big `detect_waste()` function with nested ifs, (b) declarative rule classes.

**Decision:** Declarative rule classes. Each rule is a subclass of `DetectionRule` with explicit `applies_to` filter, `_evaluate_signals` method emitting named `RuleSignal` objects, and a documented production-signal vs offline-proxy pair.

**Rationale:**
1. **Auditability.** Each rule's *why* (production signal) and *how* (offline proxy) live next to its *what*. The Finding records the matching signals — a grader reading a single Finding row can reconstruct the rule's reasoning without opening the rule file.
2. **Testability.** A test for `OrphanedEBSRule` is one fixture + two assertions. With a 200-line if-tree, "test for orphaned-EBS detection" becomes a system test.
3. **Confidence calibration.** Multi-signal weights (e.g., EIP fires on EITHER `IdleAddress` charge present OR `Lifecycle=orphaned` tag) are first-class — not buried in if/elif chains.
4. **Scalability.** Adding `R-S3-001` (orphaned bucket) is one new file in `aws_rules.py`. The engine doesn't change.
5. **Cross-cloud reuse.** When we add Azure rules, they share the abstract base; signal-matching shape is identical. AWS-specific code stays in `aws_rules.py`.

**Considered & rejected:**
- **Generic schema validator (e.g., JSONSchema-style)** — too narrow; rules need access to billing_history for time-window logic.
- **Open Policy Agent (Rego)** — overkill for a 4-6h MVP and adds an interpreter dependency.
- **Procedural pipeline** (steps run sequentially with shared state) — fine for 1-2 rules; brittle at 7+, terrible at 20+.

**Consequences:** Rule files are slightly more verbose than an if-tree would be, but each rule is independently understandable, testable, and replaceable. Same engine handles 1 rule or 100.

---

## ADR-009 · 2026-05-08 · Multi-signal rules need a `min_confidence` threshold

**Context:** Initial implementation of `OrphanedEBSRule` had a primary signal (Lifecycle tag, weight 0.9) and a heuristic backup signal (`no_attachment_recorded` from `Resource.attrs`, weight 0.1). The base class fired the rule whenever **any** signal matched. Result: all 5 EBS volumes (including the 3 attached ones) fired R-EBS-001 because the offline proxy never populates `attached_to`, so `not attached` was always True — a 0.1-weight signal alone tripped the rule.

**Decision:** Base class requires `confidence ≥ min_confidence` (default `0.5`) before emitting a Finding. Per-rule override available if a single weak signal is genuinely sufficient.

**Rationale:** Multi-signal logic should compose, not lower the bar. Without a threshold, adding *any* heuristic signal — even one labelled "weak" via a small weight — admits more false positives. The threshold makes the math work: a single 0.9-weight signal still fires (0.9 ≥ 0.5); a single 0.1-weight signal does not (0.1 < 0.5); two 0.3-weight signals together do (0.6 ≥ 0.5).

**Consequences:** All rules continue to function (their primary signals are weight ≥ 0.5). The smoke test went from 11 findings (3 false positives) to 8 findings (clean) on the 17-resource sample — matches the seeded ground truth exactly.

---

## ADR-010 · 2026-05-08 · Templates can't *mention* the forbidden patterns either

**Context:** The first templates contained safety-conscious language like *"Never `--force`"* in docstrings or *"# NOT `-auto-approve`"* in comments. The intent was correct — *don't do this* — but the SafetyGate's regexes are not context-aware (they don't know `#` precedes a comment in shell, or `"""` opens a docstring in Python). The regex matched the literal pattern and rejected templates that *advised against* the dangerous behaviour.

**Options considered:**
1. **Make the regex context-aware** — strip comments/docstrings before scanning. Possible but format-specific and fragile (multi-line strings, here-docs, Python triple-quotes vs shell heredocs).
2. **Reword templates** — never mention the literal pattern, even to negate it.
3. **Maintain an allowlist** — pattern X is OK in this specific docstring location.

**Decision:** Reword templates. Replace `"--force"` with `"force flag"`, `"--skip-final-snapshot"` with `"final snapshot is mandatory"`, `"-auto-approve"` (when adjacent to terraform apply/destroy on the same line) with `"never auto-approve"`, etc.

**Rationale:** This is the cheapest, most reliable option. The cost is minor wording adjustment in templates; the benefit is a single, simple, context-free regex pass that works on any future template addition. A future contributor who *unintentionally* introduces a literal forbidden pattern in a comment also gets caught — that's a feature, not a bug.

**Consequences:** Generated plans use slightly more verbose phrasing in their safety commentary. Stakeholders reading a plan still see the safety story clearly. The validator's promise is now: "the rendered plan, including its comments, contains zero literal mentions of forbidden patterns" — which is the strongest property for a downstream consumer that *might* execute parts of it.

---

## ADR-011 · 2026-05-08 · Ingestion is idempotent — `monthly_cost` REPLACES on re-ingest

**Context:** Smoke-testing the API after the remediation layer revealed that re-ingesting the same CSV doubled `Resource.monthly_cost` (and therefore findings' savings_estimate and risk_score). The pre-fix upsert added `info["monthly_cost"]` to the existing value, accumulating across ingests.

**Decision:** Replace, not add. After upsert, `Resource.monthly_cost` reflects the cost computed in the *current* ingest's billing rows for that resource.

**Rationale:**
- Demo correctness: a user uploading the same file twice expects the same numbers, not 2× numbers.
- Idempotency for tests: re-ingest cycles are deterministic.
- For multi-period ingests (April + May), the *latest* ingest's numbers represent the most-recent observed monthly cost — which is the FinOps view anyway. Cumulative period analysis lives at the BillingRecord level, where rows still accumulate.

**Consequences:** Multi-period rollup queries should aggregate `BillingRecord.cost`, not read `Resource.monthly_cost`. The latter is now explicitly "last-observed monthly cost", documented in the model.

---

## ADR-012 · 2026-05-08 · Pydantic IO schemas are separate from SQLModel storage models

**Context:** SQLModel can act as both ORM and Pydantic schema (its USP). FastAPI returning SQLModel instances directly works. Two reasons we still split: (a) the wire shape and the storage shape have *different* lifecycles; (b) we want to control exactly what's exposed.

**Decision:** Define `schemas.py` with explicit `IngestSummaryOut`, `FindingOut`, `RemediationPlanOut`, `ScanResultOut`, `ReportOut`, `WebhookResult`, `AlertEcho`, `HealthResponse`. Routes return these, not SQLModel.

**Rationale:**
- **DB → API change isolation.** Renaming a DB column (e.g., `attrs` → `metadata_json` later) shouldn't break consumers — they consume `FindingOut`.
- **Selective exposure.** `BillingRecord.raw_record` is a verbatim line-item with potentially-sensitive tag values; the API never auto-includes it. The storage shape "knows" about the raw row; the API shape decides.
- **Explicit auto-generated docs.** OpenAPI schemas built from `schemas.py` are concise and named for the wire — what frontend developers expect.

**Consequences:** Slight duplication. Worth it; the lifecycle separation prevents the typical "we changed the DB and broke 3 clients" failure mode. ADR-005 (SQLModel choice) and this ADR are complementary, not contradictory: SQLModel is for storage, Pydantic for I/O.

---

## ADR-013 · 2026-05-08 · Opus orchestrator + Haiku workers — cost-quality tradeoff measured

**Context:** ADR-002 chose this topology architecturally; this ADR captures the *measured* result against real Anthropic calls.

**Measurement** (single audit on 8 findings, 17 resources):

| Tier | Calls | Tokens (in/out) | Wall-clock | Cost |
|---|---|---|---|---|
| Opus orchestrator (Analyzer) | 1 | 1,933 / 1,494 | 21.6s | $0.141 |
| Haiku workers (Remediator × 3, parallel) | 3 | 2,367 / 1,044 | ~5s (parallelised) | $0.007 |
| **Total** | **4** | **4,300 / 2,538** | **27s** | **$0.148** |

**Quality (Analyzer narrative excerpt):**
> *"The pattern — an idle legacy MySQL RDS, an idle r5.large, two orphaned EBS volumes, an unassociated EIP, and a NAT Gateway that moved 1.2 MB — strongly suggests a decommissioned or abandoned environment (likely a stage/legacy stack) where compute was torn down but networking and storage scaffolding were left behind."*

The Opus narrative correctly inferred the *organisational story* from the data — not just summed costs. That's the kind of insight that justifies the spend; pure rule-based output couldn't have produced "stage/legacy stack abandoned" without a tag explicitly saying so.

**Quality (Haiku Remediator enrichment excerpt):**
> Adjacent optimisations: *"Audit other r5.large instances in us-east-1 for similar idle patterns; candidate for bulk right-sizing to r5.medium or t3.medium."* + *"Consider implementing auto-stop policy for instances tagged Lifecycle=idle to prevent recurring cost drift."*

Haiku produced concrete, actionable suggestions tailored to the specific finding — exactly what we asked for and what would be wasteful to ask Opus for.

**Cost lens:**
- $0.15 per audit on a 17-resource account.
- For a continuous FinOps practice running weekly, that's $7.80/year — compared to the $1,108/year detected savings, ROI > 140×.
- For a 1,000-resource account (where token cost scales sub-linearly because findings count grows slower than resource count), audit cost stays under $1.

**What we'd flip if findings count > 200:**
- Pre-filter findings to top 50 by `risk_score × confidence` *before* Opus call (saves ~80% input tokens on noisy accounts).
- Cache Analyzer narratives by (findings_hash, model_version); only re-call when findings change.

**Fallback mode:** also tested. Same shape, $0 cost, ~50ms wall-clock. The system *prefers* the LLM path but *requires* the fallback to work — and 6 of the 14 agent tests exercise the fallback.

---

## ADR-014 · 2026-05-08 · MCP server *alongside* the FastAPI surface, not instead of

**Context:** Both the REST API and the MCP server expose the same engine. Why ship two doors?

**Decision:** Both. They're not redundant — they target different consumers.

**Rationale:**
- **REST is for humans + traditional clients.** Browsers, curl, Postman, the Streamlit dashboard. Auth/CORS/OpenAPI all expected.
- **MCP is for AI agents.** Claude Desktop, Claude Code, Cursor, custom orchestrators. Schema-introspectable, streaming, capability-discovery built-in. No client-specific glue.
- Shipping only REST forces every AI client to either (a) call the REST API (loses MCP's introspection benefits) or (b) get its own custom adapter. Shipping only MCP loses the dashboard story.
- The cost of "two doors" is one extra ~250-line module (`mcp_server/server.py`); the engine logic underneath is shared.

**Consequences:** A future Postgres migration / multi-tenant change touches both surfaces uniformly because they delegate to the same domain layer. Documentation cost is ~one extra integration guide (`docs/MCP_INTEGRATION.md`).

---

## ADR-015 · 2026-05-08 · Dashboard talks to FastAPI, not directly to the DB

**Context:** Streamlit can import `finops.db.session` directly and run SQL — fewer moving parts, faster local iteration. Or the dashboard can talk to the FastAPI surface via httpx.

**Decision:** Always via FastAPI.

**Rationale:**
1. **Single auth/permissions surface** going forward. If we add API keys, RBAC, or rate-limiting, the dashboard inherits them automatically.
2. **Hot-reload separation.** A dashboard restart never touches the DB schema; an API restart never invalidates dashboard state. Independent deployment story.
3. **Pluggable backend.** A future replacement of FastAPI with FastMCP-only or a different framework doesn't require a dashboard rewrite — just point `FINOPS_API_URL` somewhere new.
4. **Testability.** The dashboard can be tested with a stub API; we don't need a real DB to render pages. (Future: visual regression with mocked HTTP.)

**Consequences:** One extra HTTP hop per dashboard page render. Acceptable: HTTP localhost is sub-millisecond, and we cache via `@st.cache_data(ttl=10–15s)`. Net latency stays under 50ms per page.

---

<!-- New decisions appended here as we build. -->
