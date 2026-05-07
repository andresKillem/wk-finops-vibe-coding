# Configuration Reference — `.claude/settings.json` & `.env`

Two files configure this project's agentic surface. Each has a different scope.

## `.claude/settings.json` — checked into git

Tells **any** Claude Code instance opening this repo: "here's what you're allowed to do, here's the runtime hooks, here's the model preference."

### Sections

| Key | Purpose |
|---|---|
| `permissions.allow` | Pre-authorized tool calls. The architect doesn't get prompt-fatigue confirming `uv run` 50 times. |
| `permissions.deny` | Hard denial — no override prompt. Destructive AWS/Terraform commands and editing `.env` / `data/` are denied. |
| `hooks` | Lifecycle scripts (PreToolUse, UserPromptSubmit, Stop). See `HOOKS.md`. |
| `statusLine` | Custom status line script (`hooks/status_line.sh`). |
| `model` | Default model for the session. Sub-agents override per-agent. |
| `env` | Environment variables injected into every tool call. |

### Customization

To allow another tool (say, `bq` for BigQuery), append to `permissions.allow`:
```json
"Bash(bq:*)"
```

To make a path read-only instead of editable, remove its glob from `permissions.allow` and add to `permissions.deny`.

## `.env` — gitignored, copy from `.env.example`

Per-environment secrets and overrides. The repo ships `.env.example` listing every variable; never commit `.env`.

| Variable | Purpose | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Enables real sub-agent calls | unset → deterministic fallback |
| `ANTHROPIC_ORCHESTRATOR_MODEL` | Override Opus model name | `claude-opus-4-7` |
| `ANTHROPIC_WORKER_MODEL` | Override Haiku model name | `claude-haiku-4-5` |
| `WEBHOOK_URL` | Where alert simulator POSTs | `http://localhost:8765/alert-sink` |
| `RISK_THRESHOLD` | overall_risk above this triggers webhook | `70` |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./data/finops.db` |
| `API_PORT`, `DASHBOARD_PORT`, `MCP_HTTP_PORT` | Service ports | `8000`, `8501`, `8765` |

## How the two interact

Claude Code reads `settings.json` to determine *what's permitted*. The Python application reads `.env` to determine *runtime behavior*. They're independent surfaces — settings.json doesn't expose secrets, and `.env` doesn't grant tool permissions.
