#!/usr/bin/env bash
# StatusLine hook. Reads stdin JSON (Claude Code session state) and prints a one-line status.
# The output appears as the persistent status line during interactive sessions.

set -euo pipefail

# Findings count (best effort — DB may not exist yet)
FINDINGS_COUNT="?"
if [ -f "data/finops.db" ] && command -v sqlite3 >/dev/null 2>&1; then
  FINDINGS_COUNT="$(sqlite3 data/finops.db 'SELECT COUNT(*) FROM finding' 2>/dev/null || echo "?")"
fi

# Prompts logged
PROMPTS_COUNT=0
if [ -f "prompts.md" ]; then
  PROMPTS_COUNT="$(grep -cE '^## #[0-9]+ ' prompts.md 2>/dev/null || echo 0)"
fi

# Elapsed
ELAPSED_LABEL="?"
if [ -f ".session_meta.json" ]; then
  START_UTC="$(grep -oE '"session_started_at_utc":[[:space:]]*"[^"]*"' .session_meta.json | sed 's/.*"\([^"]*\)"$/\1/')"
  if [ -n "$START_UTC" ]; then
    NOW_EPOCH="$(date +%s)"
    START_EPOCH="$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$START_UTC" +%s 2>/dev/null || python3 -c "import datetime as d,sys; print(int(d.datetime.fromisoformat(sys.argv[1].replace('Z','+00:00')).timestamp()))" "$START_UTC" 2>/dev/null || echo "$NOW_EPOCH")"
    ELAPSED=$((NOW_EPOCH - START_EPOCH))
    H=$((ELAPSED / 3600))
    M=$(((ELAPSED % 3600) / 60))
    ELAPSED_LABEL="${H}h${M}m"
  fi
fi

echo "FinOps · findings:${FINDINGS_COUNT} · prompts:${PROMPTS_COUNT} · elapsed:${ELAPSED_LABEL}"
