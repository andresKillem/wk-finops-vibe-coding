# `.claude/` — Agentic Surface

This directory is the **agentic operating manual** for the project. Loading this repo into Claude Code (or any agent that understands the format) gives the AI immediate access to:

| Surface | Files | What it enables |
|---|---|---|
| **Permissions & guardrails** | `settings.json` | Pre-authorized tool allowlist; deny list for destructive ops; runtime hooks. |
| **Skills** | `skills/*/SKILL.md` | Reusable procedural knowledge — how the AI should approach a class of task. |
| **Slash commands** | `commands/*.md` | One-line shortcuts that invoke real CLI flows (`/audit`, `/scan`, `/remediate`). |
| **Sub-agents** | `agents/*.md` | Personas with explicit tool budgets and handoff protocols. |
| **Hooks** | `hooks/*.sh` | Lifecycle scripts (PreToolUse safety gate, UserPromptSubmit logger, Stop elapsed-time reporter). |
| **Internal docs** | `docs/*.md` | Hand-off documentation explaining how each surface piece works. |

## Why this is "two steps ahead" in vibe coding

Most vibe-coding projects ship a `README.md` and call it a day. This project treats the AI's working environment as **a deliverable**. A future engineer cloning this repo can:

1. Open it in Claude Code.
2. Type `/audit` and immediately run a FinOps audit on a billing file.
3. Read `skills/finops-architect/SKILL.md` to learn the methodology.
4. Inspect `agents/analyzer-agent.md` to understand the sub-agent's tool budget and personality.
5. Trust that `hooks/safety_gate.sh` will block destructive `aws ec2 terminate` calls before they ever execute.

This is the difference between *vibing* and *engineering with AI*.

## Running the hooks locally

The hooks are bash scripts and are invoked by Claude Code automatically when this repo is loaded. To test a hook in isolation:

```bash
echo '{"tool_input":{"command":"rm -rf /tmp/test"}}' | .claude/hooks/safety_gate.sh
# expected: exit 2, "Blocked: dangerous pattern"
```

## See also

- `docs/AGENTIC_SURFACE.md` — narrative explanation for the deck.
- `BITACORA.md` ADR-004 — why every file in here is functional, not decorative.
