# Skills — Reading Guide

Skills are **procedural knowledge** the AI engineer can invoke when a task matches the skill's `when_to_use`. Each skill has a `SKILL.md` with a frontmatter that lets the AI auto-trigger it.

## Skill catalog

| Skill | Scope | Triggers |
|---|---|---|
| `finops-architect` | End-to-end FinOps audit methodology (the 4 gates) | "audit this billing", "find waste", `/audit` |
| `cost-analyzer` | Triage and rank existing findings; executive narrative | "what should I prioritize", "give me the headline" |
| `remediation-planner` | Generate safe multi-format remediation plans | "give me the command to fix this", `/remediate <id>` |
| `compliance-auditor` | Tag/ownership compliance gating (bonus) | "who owns this", "is this prod" |

## Reading order for a new contributor

1. `finops-architect/SKILL.md` — the methodology.
2. `finops-architect/references/detection-rules.md` — the catalog of what we look for.
3. `finops-architect/references/risk-scoring.md` — the math.
4. `finops-architect/references/remediation-patterns.md` — the output formats.
5. `cost-analyzer/SKILL.md` and `remediation-planner/SKILL.md` — the focused specialists.
6. `compliance-auditor/SKILL.md` — last, when you're ready to think about governance.

## When *not* to use a skill

- The user wants something off-pattern (e.g., "ingest a Snowflake table" — we don't have a skill for that; don't pretend a near-match works).
- The user is asking for raw data exploration — skills add structure, but pure inspection doesn't need it.
- The user is debugging an internal bug — that's a debugging task, not a FinOps task.

## Skill vs sub-agent — what's the difference?

- **Skill** = procedural knowledge written in markdown, loaded into the AI's context when triggered. The AI follows the skill's instructions but uses *its own* model and tools.
- **Sub-agent** = a separate, scoped LLM call with its own model, system prompt, and tool budget. The orchestrator dispatches sub-agents in parallel.

The two complement each other: skills shape *how* a task is done; sub-agents distribute *who* does parts of it.
