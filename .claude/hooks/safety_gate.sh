#!/usr/bin/env bash
# PreToolUse hook for Bash. Reads JSON tool input on stdin, blocks dangerous patterns.
# Exit codes:
#   0 — allow
#   2 — block (Claude Code surfaces this as denial)
# Documentation: see .claude/hooks/README.md

set -euo pipefail

# Read stdin if present (JSON from Claude Code)
INPUT=""
if [ ! -t 0 ]; then
  INPUT="$(cat)"
fi

# Extract command from JSON; tolerate missing jq by falling back to grep
extract_command() {
  if command -v jq >/dev/null 2>&1; then
    echo "$INPUT" | jq -r '.tool_input.command // empty'
  else
    echo "$INPUT" | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*:[[:space:]]*"\(.*\)"/\1/'
  fi
}

CMD="$(extract_command)"

# If no command found, allow (we don't know what we're inspecting)
if [ -z "$CMD" ]; then
  exit 0
fi

# Dangerous patterns. Exit 2 with stderr message if matched.
declare -a PATTERNS=(
  'rm[[:space:]]+-rf'
  'aws[[:space:]]+ec2[[:space:]]+terminate-instances'
  'aws[[:space:]]+ec2[[:space:]]+delete-volume'
  'aws[[:space:]]+rds[[:space:]]+delete-db-instance'
  'aws[[:space:]]+s3[[:space:]]+rb'
  'aws[[:space:]]+iam[[:space:]]+delete-user'
  'terraform[[:space:]]+destroy[[:space:]]+.*-auto-approve'
  'terraform[[:space:]]+apply[[:space:]]+.*-auto-approve'
  'kubectl[[:space:]]+delete[[:space:]]+--all'
  '--skip-final-snapshot'
  '--force[[:space:]]'
  ':(){ :|:& };:'  # fork bomb
)

for pattern in "${PATTERNS[@]}"; do
  if [[ "$CMD" =~ $pattern ]]; then
    echo "[safety_gate] BLOCKED: command matches dangerous pattern '$pattern'" >&2
    echo "[safety_gate] command: $CMD" >&2
    echo "[safety_gate] If genuinely required, the architect must override via prompts.md ADR." >&2
    exit 2
  fi
done

# Allow
exit 0
