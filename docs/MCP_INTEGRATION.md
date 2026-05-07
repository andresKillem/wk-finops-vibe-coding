# MCP Integration Guide

The optimizer ships with an [MCP](https://modelcontextprotocol.io/) server that exposes its capabilities as universal tools. Any MCP-aware client (Claude Desktop, Claude Code, Cursor, custom agents) can plug in.

## Connecting from Claude Desktop / Claude Code

Add this block to your MCP config (location varies by client; for Claude Desktop on macOS it's `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "finops": {
      "command": "uv",
      "args": ["run", "python", "-m", "finops.mcp_server.server"],
      "cwd": "/absolute/path/to/wk-finops-vibe-coding",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Restart the client. The four tools below should appear in the tool picker.

## Tools exposed

| Tool | Input | Output | When to use |
|---|---|---|---|
| `ingest_billing` | `file_path: str` | `{rows, date_range, resources}` | Load a billing export into the local DB |
| `analyze_billing` | none | `{findings, overall_risk, narrative}` | Run scan + sub-agents and get an executive readout |
| `propose_remediation` | `finding_id: int`, `format: "aws_cli"|"boto3"|"terraform_import"` | rendered plan as text | Generate a single safe remediation plan |
| `estimate_savings` | none | `{monthly, annual, by_category}` | Quick savings projection |

## Resources exposed

- `finops://findings` — current findings as JSON. Useful when an LLM client wants to reason over the raw data.

## Prompts exposed

- `finops_audit` — pre-templated prompt that takes `(file_path, audience)` and renders an audit-style request the orchestrator can act on.

## HTTP transport (for inspection)

If you'd rather poke at the server with `curl`:

```bash
make run-mcp-http   # binds :8765
curl http://localhost:8765/tools | jq .
```

The HTTP transport mirrors the stdio one — same tool set, same shapes — but is easier to debug.

## Why MCP and not "just an HTTP API"

We *also* ship a FastAPI HTTP API. MCP is additive — it lets the same engine be a **first-class tool inside an AI client**, with proper schema introspection, streaming, and auth — without writing client-specific glue code.

Same engine, two doors: humans through HTTP, agents through MCP.
