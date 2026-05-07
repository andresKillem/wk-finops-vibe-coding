# Hooks — High-Level Reference

This is the narrative-level overview. For implementation detail and testing, see `../hooks/README.md`.

## What hooks do for this project

| Hook | Lifecycle event | Purpose |
|---|---|---|
| `safety_gate.sh` | `PreToolUse` (Bash matcher) | Block destructive commands *before* execution. Exit 2 = denied. |
| `prompt_logger.sh` | `UserPromptSubmit` | Auto-append every prompt to `prompts.md` (deduplicated by content hash). |
| `elapsed_time.sh` | `Stop` (end of turn) | Print "Elapsed Time: Xh Ym Zs" to stderr → satisfies challenge §4 rule "Report Elapsed Time at the end of every response" automatically. |
| `status_line.sh` | (statusLine) | Persistent line: `FinOps · findings:N · prompts:N · elapsed:Xh` |

## Why hook the audit log instead of relying on the AI

The challenge requires `prompts.md` to be updated after every turn. Two failure modes if we leave it to the AI:
1. AI forgets on a long turn.
2. AI writes a paraphrase instead of the verbatim prompt.

Hooking `UserPromptSubmit` makes capture **automatic, verbatim, and deduplicated**. The architect never has to verify it happened.

## Why hook elapsed time instead of computing in-prompt

Same reasoning. The challenge requires elapsed time at end of every response. AI memory + math during long turns is a flaky source. Hooking `Stop` to a script that reads `.session_meta.json` and emits to stderr makes it deterministic.

## Defense-in-depth on safety

The `permissions.deny` array in `settings.json` already blocks dangerous commands — but only commands that *exactly match* known patterns. The `safety_gate.sh` hook adds a regex pattern layer on top, catching variants like `aws ec2 terminate-instances --instance-ids ... --force` that might slip past simpler matchers.

## Adding a new hook

1. Add the script to `.claude/hooks/your_hook.sh`. Make it executable (`chmod +x`).
2. Wire it in `.claude/settings.json` under the appropriate lifecycle key.
3. Document it in `.claude/hooks/README.md` (implementation) and here (purpose).
4. Add a test invocation snippet to the implementation README.
