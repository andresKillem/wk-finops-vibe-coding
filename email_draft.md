**To:** kash.kashyap@wolterskluwer.com
**From:** Andres Munoz <andreco87@hotmail.com>
**Subject:** Wolters Kluwer Vibe Coding Challenge — Submission — Andres Munoz
**Date:** 2026-05-08

---

Dear Kash,

Please find my submission for the Wolters Kluwer 2026 Graduate Vibe Coding Challenge — *Architecture and Engineering Services*. I selected **Project 1: Cloud Cost Optimizer & Remediation Engine**.

The deliverable is a Python 3.11, API-first FinOps engine built end-to-end via "vibe coding" — the architect (me) directed; the AI engineer (Claude Code, `claude-opus-4-7`, 1M context) wrote every line of code. Per the rules, I did not edit the codebase manually at any point. The verbatim audit log at `prompts.md` is the proof.

## Submission package

| Deliverable | Where |
|---|---|
| **Public GitHub repository** | https://github.com/andresKillem/wk-finops-vibe-coding |
| **prompts.md (verbatim audit log)** | https://github.com/andresKillem/wk-finops-vibe-coding/blob/main/prompts.md |
| **BITACORA.md (architectural decisions)** | https://github.com/andresKillem/wk-finops-vibe-coding/blob/main/BITACORA.md |
| **AI-generated presentation deck** | https://github.com/andresKillem/wk-finops-vibe-coding/blob/main/docs/PRESENTATION.md |
| **Architecture diagrams** | https://github.com/andresKillem/wk-finops-vibe-coding/blob/main/docs/ARCHITECTURE.md |
| **MCP integration guide** | https://github.com/andresKillem/wk-finops-vibe-coding/blob/main/docs/MCP_INTEGRATION.md |
| **Demo run output** | https://github.com/andresKillem/wk-finops-vibe-coding/blob/main/docs/demo_output.txt |
| **Runtime smoke logs (API + MCP + dashboard)** | https://github.com/andresKillem/wk-finops-vibe-coding/blob/main/docs/runtime_smoke.log |
| **Tagle.ai Tag** | `[INSERT TAG HERE WHEN AVAILABLE]` |

## Three innovations worth a closer look

1. **Sub-agent topology with measured cost-quality tradeoff (HERO #1)** — `AnalyzerAgent` (Opus 4.7, 1 call per audit) handles narrative + ranking; `RemediatorAgent` × N (Haiku 4.5, parallel via `asyncio.gather`, max 5 concurrent) enriches each top finding. Real numbers on the bundled sample: $0.148 / audit, 27s wall-clock, ROI > 140× detected savings. A deterministic-fallback path with the same JSON shape kicks in when no API key is present, so the demo runs anywhere. Documented in BITACORA ADR-002 + ADR-013.

2. **MCP server alongside REST (HERO #2)** — the same engine that backs the FastAPI surface is also exposed as a Model Context Protocol server. Five tools, two resources, and a parameterised audit prompt. Any MCP-aware client (Claude Desktop, Claude Code, Cursor, custom agents) can plug in with one config block — no client-specific glue. The optimizer becomes a *capability*, not just an app. Documented in BITACORA ADR-014.

3. **Functional agentic surface in `.claude/`** — skills, slash commands, sub-agent definitions, and lifecycle hooks (`safety_gate.sh` blocks `rm -rf` and `aws ec2 terminate` *before* execution; `prompt_logger.sh` auto-appends to `prompts.md`; `elapsed_time.sh` emits `Elapsed Time` at end of every turn). Defense-in-depth on safety, automatic compliance with the challenge rules, and a portfolio of agentic primitives a future engineer can read and reuse. Documented in BITACORA ADR-004.

## By the numbers

- 8 layers shipped across 11 commits.
- ~6,800 lines of Python.
- 150 tests passing (ingestion, detection, remediation, API, agents, MCP).
- 16 Architecture Decision Records (BITACORA.md), including one mid-build bug fix transparent to the grader (ADR-009, ADR-011).
- Built in approximately 8 hours of architect-led work.
- All cloud resources decommissioned: **N/A — offline-only build with synthetic billing data** (cleanest interpretation of the rule; nothing was provisioned).

## How to demo it locally

```bash
git clone https://github.com/andresKillem/wk-finops-vibe-coding && cd wk-finops-vibe-coding
cp .env.example .env       # optional: add ANTHROPIC_API_KEY for real sub-agents
uv sync --all-extras
make demo                  # ingest sample → scan → analyze → report (≈ 0.3s fallback / 25s LLM)
make run-api               # FastAPI :8000 with OpenAPI at /docs
make run-dashboard         # Streamlit :8501 with 5 polished pages
make run-mcp               # MCP server (stdio) for Claude Desktop / Cursor integration
```

## Closing

The challenge asked for "the architect; the AI is the engineer." I took that literally. Every directive went through `prompts.md`. Every decision went into `BITACORA.md`. The code is exactly what those two files described — no more, no less.

Looking forward to the final interview to walk you through the work.

Thank you for the opportunity.

Best regards,

**Andres Munoz**
andreco87@hotmail.com
github.com/andresKillem
