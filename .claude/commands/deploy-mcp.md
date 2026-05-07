---
description: Start the FinOps MCP server (stdio by default; HTTP optional) so any MCP-aware client can use the optimizer as a tool.
argument-hint: [--http]
---

If argument contains `--http`:
- Run `uv run python -m finops.mcp_server.server --http`
- Server binds on `MCP_HTTP_PORT` from `.env` (default 8765)
- Output the connection URL and a sample `curl` to list tools

Otherwise (stdio default):
- Run `uv run python -m finops.mcp_server.server`
- Output the JSON snippet a user pastes into Claude Desktop / Claude Code config to connect:

```json
{
  "mcpServers": {
    "finops": {
      "command": "uv",
      "args": ["run", "python", "-m", "finops.mcp_server.server"],
      "cwd": "<absolute path to this repo>"
    }
  }
}
```

Confirm the server is up by listing the registered tools (`ingest_billing`, `analyze_billing`, `propose_remediation`, `estimate_savings`).

## Reference

- Module: `src/finops/mcp_server/server.py`
- Doc: `docs/MCP_INTEGRATION.md`
