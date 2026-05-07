# Sub-Agents — Reading Guide

This project uses a **multi-agent topology** for the AI inference layer. The orchestrator pattern is documented in `BITACORA.md` ADR-002.

## The four agents

| Agent | Model | Role | Invocation |
|---|---|---|---|
| `analyzer-agent` | Opus 4.7 | Triage all findings, produce prioritized plan + narrative | Once per audit |
| `remediator-agent` | Haiku 4.5 | Enrich one base plan with pre-conditions, rollback, comms | Up to 5 in parallel |
| `reviewer-agent` | Haiku 4.5 | Optional safety review of generated plans | On user opt-in |
| `compliance-agent` | Haiku 4.5 | Tag/ownership gating (bonus) | When tags missing or prod resource targeted |

## Orchestration flow

```
User → /audit
        │
        ▼
   [Detector]──→ raw findings
        │
        ▼
[analyzer-agent] (Opus, 1 call)
   │
   └─→ prioritized list + narrative
        │
        ▼
[remediator-agent] × N (Haiku, parallel)  ──┐
[compliance-agent] × N (Haiku, parallel) ──┤
                                            │
                                            ▼
                                  [reviewer-agent] (optional)
                                            │
                                            ▼
                                       Final report
```

## Why this topology and not "one big agent"

| Concern | One-big-agent | This topology |
|---|---|---|
| Context pollution | High — Opus must hold every finding's detail | Low — Opus sees summaries; Haiku sees one finding |
| Cost | High (Opus tokens × N) | Low (1 Opus call + N Haiku) |
| Latency | Sequential | Parallel via `asyncio.gather` |
| Failure isolation | One bad finding poisons all | Bad finding fails one Haiku, others continue |

## Why this topology and not LangGraph

LangGraph is excellent for arbitrary stateful graphs. We have one fixed graph (1→N→1). The overhead of LangGraph's abstractions exceeds its benefit at this scope. We stay native Anthropic SDK + asyncio. See `BITACORA.md` ADR-001 for full reasoning.

## Fallback when no API key

If `ANTHROPIC_API_KEY` is unset, every agent short-circuits to deterministic templates:
- `analyzer-agent` → severity × cost descending sort + canned 3-bullet narrative.
- `remediator-agent` → string-templated pre-conditions/rollback/comms.
- `reviewer-agent` → no-op approval (logged).
- `compliance-agent` → tag dictionary check, no LLM.

The interface is identical, so the rest of the system doesn't notice. The dashboard shows a "Deterministic mode" badge so the demo viewer knows.
