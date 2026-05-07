# Hooks — Lifecycle Scripts

These shell scripts are invoked by Claude Code at lifecycle points configured in `../settings.json`. Each is intentionally small, idempotent, and tolerant of missing input.

## `safety_gate.sh` — PreToolUse on Bash

**Purpose.** Refuse to even execute Bash commands matching destructive patterns (`rm -rf`, `aws ec2 terminate-instances`, `terraform destroy -auto-approve`, fork bombs, etc.). Defense-in-depth on top of the deny list in `settings.json`.

**Invocation.** Claude Code calls this for every Bash tool use, with the JSON tool input piped to stdin. Exit code 2 blocks execution; exit code 0 allows.

**Test.**
```bash
echo '{"tool_input":{"command":"rm -rf /tmp/x"}}' | .claude/hooks/safety_gate.sh
# expect: exit 2 + stderr "BLOCKED"

echo '{"tool_input":{"command":"ls -la"}}' | .claude/hooks/safety_gate.sh
# expect: exit 0
```

## `prompt_logger.sh` — UserPromptSubmit

**Purpose.** Append every user prompt to `prompts.md` automatically, deduplicated by content hash. Means the architect cannot accidentally forget to log a prompt.

**Invocation.** Claude Code calls this on every prompt submission with `{"prompt": "..."}` on stdin.

**Toggle.** `FINOPS_LOG_PROMPTS=false` disables (for example, while the architect is testing the pipeline locally).

**Note.** Initial prompts (#001, #002) were authored manually with rich annotations; the auto-logger handles all subsequent prompts unobtrusively.

## `elapsed_time.sh` — Stop

**Purpose.** Compute and emit `Elapsed Time: Xh Ym Zs` to stderr at end of every Claude turn. Claude Code surfaces stderr to the user, satisfying the doc's "Report Elapsed Time at the end of every response" rule **automatically and reliably**, without depending on the AI to remember.

**Invocation.** Claude Code calls on the Stop event (when the AI's response is complete).

## `status_line.sh` — Custom statusLine

**Purpose.** Persistent status line: findings count, prompts logged, elapsed time. Visible during interactive sessions.

## Why bash and not Python?

These hooks must run on every prompt and every Bash tool use. Latency matters. Bash with `jq` (or its grep fallback) starts in <50ms; a Python interpreter with imports is 10-50x slower. Same logic, lower overhead.

## Cross-platform notes

The scripts work on macOS (BSD `date`) and Linux (GNU `date`). The Linux fallback for `date -j` uses Python's `datetime` module, which is universally available.

## Failure mode

If a hook script crashes (syntax error, missing file), Claude Code logs the error but **does not block the user's turn**. This is by design — hooks are belt-and-suspenders, not load-bearing.
