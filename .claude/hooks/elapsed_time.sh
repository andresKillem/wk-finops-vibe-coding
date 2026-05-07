#!/usr/bin/env bash
# Stop hook. Computes elapsed time since session start (from .session_meta.json) and prints to stderr.
# Claude Code surfaces stderr at end of turn. This is the mechanism for "Report Elapsed Time at end of every response".
# Documentation: see .claude/hooks/README.md

set -euo pipefail

if [ "${FINOPS_REPORT_ELAPSED:-true}" != "true" ]; then
  exit 0
fi

META_FILE=".session_meta.json"
if [ ! -f "$META_FILE" ]; then
  exit 0
fi

START_UTC=""
if command -v jq >/dev/null 2>&1; then
  START_UTC="$(jq -r '.session_started_at_utc' "$META_FILE")"
else
  START_UTC="$(grep -oE '"session_started_at_utc":[[:space:]]*"[^"]*"' "$META_FILE" | sed 's/.*"\([^"]*\)"$/\1/')"
fi

if [ -z "$START_UTC" ]; then
  exit 0
fi

# Compute elapsed in seconds (cross-platform: try GNU date, fall back to Python)
NOW_EPOCH="$(date +%s)"
START_EPOCH="$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$START_UTC" +%s 2>/dev/null || python3 -c "import datetime as d,sys; print(int(d.datetime.fromisoformat(sys.argv[1].replace('Z','+00:00')).timestamp()))" "$START_UTC")"

ELAPSED=$((NOW_EPOCH - START_EPOCH))
H=$((ELAPSED / 3600))
M=$(((ELAPSED % 3600) / 60))
S=$((ELAPSED % 60))

echo "Elapsed Time: ${H}h ${M}m ${S}s" >&2
exit 0
