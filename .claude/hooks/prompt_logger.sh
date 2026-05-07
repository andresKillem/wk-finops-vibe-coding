#!/usr/bin/env bash
# UserPromptSubmit hook. Reads the user's prompt from stdin JSON and appends to prompts.md.
# Idempotent: deduplicates by content hash (avoids double-logging on retries).
# Documentation: see .claude/hooks/README.md

set -euo pipefail

INPUT=""
if [ ! -t 0 ]; then
  INPUT="$(cat)"
fi

# Skip if FINOPS_LOG_PROMPTS != true
if [ "${FINOPS_LOG_PROMPTS:-true}" != "true" ]; then
  exit 0
fi

# Extract prompt from JSON
PROMPT=""
if command -v jq >/dev/null 2>&1; then
  PROMPT="$(echo "$INPUT" | jq -r '.prompt // .user_input.prompt // empty')"
fi

if [ -z "$PROMPT" ]; then
  exit 0
fi

# Deduplicate: hash + grep
HASH="$(echo -n "$PROMPT" | shasum -a 256 | cut -d' ' -f1 | head -c 12)"
if grep -q "<!-- prompt-hash:$HASH -->" prompts.md 2>/dev/null; then
  exit 0
fi

TS_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
COUNT=$(grep -cE '^## #[0-9]+ ' prompts.md 2>/dev/null || echo 0)
NEXT=$(printf "%03d" $((COUNT + 1)))

{
  echo ""
  echo "---"
  echo ""
  echo "## #${NEXT} · ${TS_UTC} · Auto-logged via UserPromptSubmit hook"
  echo ""
  echo "<!-- prompt-hash:$HASH -->"
  echo ""
  echo '```'
  echo "$PROMPT"
  echo '```'
} >> prompts.md

exit 0
