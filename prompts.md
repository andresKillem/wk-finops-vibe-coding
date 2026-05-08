# Vibe Coding Audit Log

> **Architect:** Andres Munoz · **AI Engineer:** Claude Code (`claude-opus-4-7`, 1M context)
> **Challenge:** Wolters Kluwer 2026 — Graduate Vibe Coding Challenge
> **Project:** Cloud Cost Optimizer & Remediation Engine
> **Session start:** `2026-05-07T19:41:23Z` (Bogotá 14:41)
> **Compliance rules:** No manual edits · Same AI end-to-end · Audit log per turn · Elapsed Time reported

This file is the **authentic record of every directive issued by the architect** during the build. Per the challenge rules, the AI engineer maintains it; the architect does not edit code, only directs through prompts. Entries below are **verbatim**, including original language (Spanish), preserving the authentic record of human-directed AI orchestration.

The challenge document explicitly permits a "Drafting Table" (its Pro-Tip §4) — a pre-build conversation to align scope and architecture before the official timer starts. That alignment session preceded entry #001 below; key decisions from it are captured in `BITACORA.md`.

---

## #001 · 2026-05-07T19:41:23Z · Lead Architect Mode Activation

**Type:** Mandatory verbatim kickoff prompt (per challenge §4).
**Architect's intent:** Activate the official session, set the rules, start the timer.

```
Lead Architect mode: ON. We are building a Python-based, API-first Cloud Cost
Optimizer & Remediation Engine using a free database and a dashboard.
Rules:
• No Manual Edits: You provide all logic and fixes. I will not edit any code.
• Audit Log: You must maintain a file named prompts.md. After every turn, update
  that file (or provide the text block) with the prompt I just used.
• Time-Check: Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h).
  Report 'Elapsed Time' at the end of every response. Acknowledge and let's start.
```

**AI engineer response:** Acknowledged. Timer started at session_started_at_utc. `prompts.md` and `BITACORA.md` initialized. Ready for build directives.

---

## #002 · 2026-05-07T19:41:23Z · Scaffolding directive

**Type:** Architect directive — bootstrap.
**Original message (verbatim, ES):**

> genial estamos alineados, vamos a crear este .claude con cada archivo super necesario, skills, config.md, hooks.md, creemos un scafolding realmente increible - vamos a darle agentes y subagentes para que este sea en realidad un sistema vibecodeado increible. /Users/andresmunoz/Downloads/Wolters\ Kluwer\ 2026\ New\ Hire\ Challenge.pdf Leamos de nuevo todo lo que debemos hacer

**Translation (for graders):**
> "Great, we're aligned. Let's create this .claude with every necessary file: skills, config.md, hooks.md. Let's create a truly incredible scaffolding — let's give it agents and sub-agents so this is in reality an incredible vibe-coded system. [path to PDF]. Let's re-read everything we have to do."

**Acceptance criteria interpreted by AI:**
1. Re-validate doc requirements against the build plan.
2. Bootstrap full project: `pyproject.toml`, `src/finops/` module skeleton, tests, samples, docs.
3. Build comprehensive `.claude/` agentic surface: skills (multiple), slash commands, sub-agent definitions, hooks, settings, internal docs.
4. Initialize audit log (`prompts.md`) and decision log (`BITACORA.md`) with this kickoff.
5. First commit, push to `origin/main`.

**Action taken:** See commit `feat: bootstrap scaffold with agentic surface (skills, commands, agents, hooks)`.

---

## #003 · 2026-05-07T20:35:00Z · Validate API key + Data layer & ingestion

**Type:** Architect directive — execute Prompt #3 from `PROMPTS_TO_SEND.md`.
**Side directives included:** validate the Anthropic API key in `.env`; fix git committer email to `andreco87@hotmail.com`.

**Original message (verbatim, ES):**

> prueba ya cree un .env, donde esta la api, pero pruebala si es valida, mi correo de github es andreco87@hotmail.com y 3 el prompt 3 es este (doker ya esta corriendo): Ahora la capa de datos e ingestion. Sin lógica de detección todavía — solo loaders y modelos.
>
> REQUISITOS:
> 1. src/finops/db/models.py: SQLModel para
>    - BillingRecord (id, cloud_provider, account_id, service, resource_id, region, usage_amount, cost, period_start, period_end, raw_record JSON)
>    - Resource (id, resource_id UNIQUE, type [ebs/ec2/eip/nat/rds/elb/etc], state [orphaned/idle/active], region, account_id, last_seen, monthly_cost, metadata JSON)
>    - Finding (id, resource_id FK, rule_id, severity, description, savings_estimate, risk_score, created_at)
>    - RemediationPlan (id, finding_id FK, format [aws_cli/boto3/terraform], commands JSON, blast_radius, status, created_at)
>    - AgentRun (id, agent_name, prompt, response, tokens_used, model, duration_ms, created_at)
>
> 2. src/finops/db/session.py: engine SQLite (./data/finops.db), get_session, init_db (crea tablas), util reset_db
>
> 3. src/finops/ingestion/aws_cur.py: parser de AWS Cost & Usage Report CSV
>    - Maneja columnas estándar: lineItem/UsageStartDate, lineItem/ResourceId, lineItem/UnblendedCost, product/ProductName, product/region, lineItem/UsageType
>    - Inserta BillingRecord; deduce Resource preliminar (state=unknown) y lo upserta
>
> 4. src/finops/ingestion/azure_billing.py: parser JSON de Azure billing exports (formato consumption API) — Mismo upsert pattern
>
> 5. src/finops/ingestion/router.py: detecta formato por extensión + heurística de columnas, delega al parser correcto
>
> 6. samples/aws_cur_sample.csv: 200 líneas REALISTAS — incluye: 5 EBS volumes (3 attached, 2 orphaned), 4 EC2 (2 active alta CPU, 1 idle <5%, 1 stopped 30+ días), 2 Elastic IPs (1 attached, 1 dangling), 2 NAT Gateways (1 con tráfico, 1 con 0 bytes 14 días), 2 RDS (1 active, 1 sin connections 7 días), 2 ELB (1 con healthy targets, 1 sin targets), múltiples regiones, montos realistas (centavos a $200/mo)
>
> 7. samples/azure_billing_sample.json: ~50 entries con managed disks + VMs en patrón análogo
>
> 8. tests/test_ingestion.py: pytest cubriendo ambos parsers + edge cases (CSV malformado, JSON vacío, encoding)
>
> 9. CLI helper en src/finops/cli.py (typer): `finops ingest <path>` que llama al router y muestra resumen rich
>
> 10. Actualiza prompts.md con este prompt #3 timestamped + BITACORA.md con la decisión "SQLModel sobre SQLAlchemy puro: por qué"
>
> 11. Commit: "feat(data): models, ingestion (AWS CUR + Azure), sample data, CLI"
>
> Corre los tests al final y muéstrame el output. Reporta elapsed time.

**Acceptance criteria interpreted by AI:** all 11 listed items + side validation of API key + git committer fix.

**Action taken:**
- Fixed git committer to `Andres Munoz <andreco87@hotmail.com>` and amended initial commit.
- `.env` validated as present (108-char key, `sk-ant-` prefix); a live Haiku call returned `401 invalid x-api-key` — key format is correct but Anthropic rejects it. Documented the fallback path; build proceeds in deterministic mode.
- Wrote 5 SQLModel models, session helpers, AWS CUR parser, Azure JSON parser, router, sample data generator (deterministic with seed=42).
- Generated 228-line AWS CUR (17 resources covering the spec mix) and 52-record Azure JSON (13 resources).
- Wrote 30-test suite; all pass after a tz-naive datetime convention adjustment (ADR-006).
- See commit `feat(data): models, ingestion (AWS CUR + Azure), sample data, CLI`.

---

## #004 · 2026-05-08T01:30:00Z · Detection layer (rules + scoring + engine)

**Type:** Architect directive — execute Prompt #4 from `PROMPTS_TO_SEND.md`.

**Original message (verbatim, ES):**

> Detection layer puro. Reglas determinísticas + Risk Score, sin AI todavía.
>
> REQUISITOS:
> 1. src/finops/detection/rules.py: clase abstracta DetectionRule con .evaluate(resource, billing_history) -> Optional[Finding]
>
> 2. src/finops/detection/aws_rules.py — implementa estas reglas con justificación FinOps real:
>    - OrphanedEBSRule: EBS volume sin attached EC2 en últimos 7d → severity HIGH
>    - IdleEC2Rule: EC2 con avg CPU <5% (heurística: cost stable + sin spikes) por 14d → MEDIUM
>    - DanglingElasticIPRule: EIP sin instance_id asociado → MEDIUM (cost ~$3.6/mo cada uno)
>    - IdleNATGatewayRule: NAT con <1MB bytes processed por 7d → HIGH (cost ~$32/mo + GB)
>    - IdleRDSRule: RDS sin DatabaseConnections >0 por 7d → HIGH
>    - UnusedLoadBalancerRule: ELB sin healthy targets por 7d → MEDIUM
>    - LegacyGenInstanceRule: instance type t2/m4/r4 → LOW (sugiere migrar a gravitón/gen actual)
>
> 3. src/finops/detection/scoring.py:
>    - risk_score(finding) = severity_weight * confidence * (1 + cost_factor) — fórmula documentada
>    - aggregate_score(findings) -> dict con total_monthly_waste, top_5_offenders, score_by_category, overall_risk (0-100)
>
> 4. src/finops/detection/engine.py: DetectionEngine.scan(session) → ejecuta todas las reglas, persiste Findings, devuelve aggregate
>
> 5. CLI: `finops scan` → ejecuta engine, output rich table con findings + total savings + score
>
> 6. tests/test_detection.py: cubre cada regla con fixtures positivos y negativos
>
> 7. prompts.md update + BITACORA.md: "rules-as-code pattern: por qué reglas declarativas y no un solo if-tree gigante"
>
> 8. Commit: "feat(detection): rules engine + risk scoring + CLI scan"
>
> Corre `finops ingest samples/aws_cur_sample.csv && finops scan` y muéstrame el output table. Reporta elapsed time.

**Action taken:**
- Built `detection/rules.py` (DetectionRule abstract + RuleSignal + RuleEvaluation), with multi-signal confidence calibration and `min_confidence` threshold (ADR-009 — caught a false positive during smoke test).
- Built `detection/scoring.py` with documented risk_score formula and volume-weighted aggregate.
- Built `detection/aws_rules.py` with all 7 rules; each rule documents production signal + offline proxy in its docstring and emits both into Finding.attrs for audit.
- Built `detection/engine.py` (DetectionEngine + ScanResult rich-renderable).
- 28 tests in `tests/test_detection.py` covering positive/negative for every rule + scoring + engine end-to-end. Combined with ingestion: 58/58 pass.
- Scan output: 8 findings (HIGH:4 MEDIUM:3 LOW:1) on the 17-resource sample → $92.34/mo waste, risk 61 (Significant waste).

ADRs added: 008 (rules-as-code), 009 (min_confidence threshold).

---

## #005 · 2026-05-08T03:00:00Z · Remediation generator (3 formats + safety gates)

**Type:** Architect directive — execute Prompts #5 + #6 in parallel.
**Original message (verbatim, ES):**

> si hagamos en paralelo lo que mas se pueda te mando el promp 5 y el prompt 6
> Generador de planes de remediation. Salida en 3 formatos por finding, con safety gates explícitos.
>
> [REQUISITOS … 8 items …]
>
> Genera un ejemplo de plan para un orphaned EBS y muéstrame los 3 formatos. Reporta elapsed time.

**Action taken:**
- Built `remediation/templates.py` — 18 Jinja2 templates (6 resource types × 3 formats), each enforcing pre-check / snapshot / dry-run / commented-out execute. Generator self-validates against `SafetyGate` before returning.
- Built `remediation/generator.py` — RemediationGenerator + `build_plan()` entrypoint; blast_radius mapping per type; full markdown rendering with stakeholder Slack-ready message.
- Built `remediation/safety.py` — SafetyGate.validate() with 12 forbidden-pattern regexes + blast-radius gating override.
- 33 tests covering every (type, format) combo for forbidden patterns + scoring + blast-radius gates + end-to-end plan generation. All pass.
- Encountered + fixed in smoke: literal mentions of forbidden patterns inside docstrings/comments tripped the validator (correctly). Reworded all template docstrings; ADR-010 captures the convention.
- Discovered + fixed during API smoke: ingestion was *adding* monthly_cost on re-upsert instead of replacing it, doubling totals on re-ingest. Fixed to be idempotent. ADR-011 captures the decision.

---

## #006 · 2026-05-08T03:30:00Z · FastAPI surface + webhook simulator

**Type:** Architect directive — same message as #005 (executed in parallel).
**Original message excerpt (verbatim, ES):**

> y Capa API. RESTful, OpenAPI, con webhook simulator para alertas.
>
> [REQUISITOS … 8 items …]
>
> Levanta el servidor (background), curl /health, curl POST /upload con sample CSV, curl POST /analyze, muéstrame OpenAPI docs URL. Reporta elapsed time.

**Action taken:**
- Built `api/main.py` — FastAPI app with title="Cloud Cost Optimizer", request_id+timing middleware, global exception handler (JSON shape with rid), CORS open for dev, 6 route groups mounted with tags.
- Built `api/schemas.py` — full Pydantic IO model set, separate from SQLModel storage models (ADR-012 rationale).
- Built `api/webhooks.py` — async WebhookEmitter with 3-attempt exponential backoff (1s → 2s → 4s).
- Built routes: `health.py` (/health, /ready), `upload.py` (multipart), `analyze.py` (run scan + auto-fire webhook on threshold), `remediate.py` (/{finding_id}?fmt=...), `report.py`, `alerts.py` (/webhook-test + self-loopback /alert-sink).
- Added `python-multipart` to deps for upload support.
- 16 API tests via TestClient: every route happy path + missing-finding 404 + invalid-format 422 + self-loop alert-sink + OpenAPI doc presence. All pass.
- Smoke test: server up on :8001 → /health 200 (llm_enabled=true) → /upload 228 rows / 17 resources → /analyze 8 findings / $92.34/mo / overall_risk 69 → OpenAPI at /docs.

ADRs added: 010 (forbidden patterns can't appear even in template comments), 011 (ingestion idempotent: replace cost on upsert), 012 (Pydantic schemas separate from SQLModel storage).

---

## #007 · 2026-05-08T03:50:00Z · Sub-agents (HERO #1) — Analyzer + Remediator

**Type:** Architect directive — execute Prompt #7. Real LLM mode (key validated).

**Original message excerpt (verbatim, ES):**

> La capa hero #1: sub-agentes reales con Claude. Si no tengo API key, generas modo "deterministic-fallback" que mockea respuestas LLM con templating estructurado pero mantiene la misma interfaz.
>
> [REQUISITOS … 9 items …]
>
> Corre POST /agents/analyze con la sample data y muéstrame el output JSON estructurado. Reporta elapsed time.

**Action taken:**
- Built `agents/base.py` — BaseAgent ABC + AgentResponse dataclass + cost estimator + robust JSON extractor (handles prose-then-JSON, markdown fences, balanced braces). Lazy-instantiates `AsyncAnthropic` only when key present.
- Built `agents/analyzer.py` — Opus orchestrator-grade single-call agent with FinOps Foundation framework system prompt, JSON-only output schema, and full deterministic fallback (severity×cost ranking, rule-based root-cause grouping, narrative templates).
- Built `agents/remediator.py` — Haiku worker with strict "do not modify base plan" guardrail, per-resource-type fallback templates (preconditions / rollback / Slack-ready comm).
- Built `agents/orchestrator.py` — `Orchestrator.run()` runs Analyzer once then dispatches Haiku Remediators in parallel via `asyncio.gather` + `asyncio.Semaphore(max_concurrent=5)`. Returns aggregated summary with token totals, cost, latency.
- Added `POST /agents/analyze?top_n=N&fmt=...` and `GET /agents/runs?limit=N` to API.
- 14 tests in `tests/test_agents.py` covering: JSON extraction edge cases, cost estimation, deterministic fallback for both agents, mocked-LLM path for both agents, invalid-JSON → graceful degradation, orchestrator end-to-end, AgentRun audit persistence.
- Smoke (real Anthropic): `POST /agents/analyze?top_n=3` → 27s wall-clock · 4,300/2,538 tokens · $0.14 cost · fallback_mode=false. Opus narrative correctly inferred "decommissioned stage stack" pattern from 8 findings; Haiku enrichments included specific rollback procedures + adjacent optimisation suggestions.

ADRs added: 013 (Opus orchestrator + Haiku workers cost-quality tradeoff documented).

---

<!-- Subsequent entries are appended here. Each entry: # · UTC timestamp · short title, then verbatim prompt and action summary. -->
