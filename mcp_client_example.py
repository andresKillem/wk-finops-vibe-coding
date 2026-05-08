"""Standalone MCP client example.

Connects to the finops MCP server via stdio, lists tools / resources / prompts,
and calls one cheap tool (``estimate_savings``) to demonstrate the round-trip.
Run with::

    uv run python mcp_client_example.py

This script demonstrates the value prop: the same engine that backs the
FastAPI surface is **also** a first-class tool inside any MCP-aware AI client —
without writing any client-specific glue code.
"""
from __future__ import annotations

import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "finops.mcp_server"],
    )

    print("Connecting to finops MCP server (stdio)...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("\n=== Tools ===")
            tools = await session.list_tools()
            for tool in tools.tools:
                desc = (tool.description or "").splitlines()[0][:90]
                print(f"  • {tool.name:<24} {desc}")

            print("\n=== Resources ===")
            resources = await session.list_resources()
            for r in resources.resources:
                # r.uri is an AnyUrl Pydantic type — coerce before formatting.
                uri = str(r.uri)
                print(f"  • {uri:<28} {r.name or ''}")

            print("\n=== Prompts ===")
            prompts = await session.list_prompts()
            for p in prompts.prompts:
                print(f"  • {p.name:<24} {(p.description or '').splitlines()[0][:80]}")

            print("\n=== Calling tool: estimate_savings() ===")
            result = await session.call_tool("estimate_savings", {})
            try:
                payload = json.loads(result.content[0].text)
            except (KeyError, IndexError, json.JSONDecodeError):
                payload = {"raw": str(result)}

            keys_to_show = [
                "total_monthly_waste",
                "annual_projection",
                "overall_risk",
                "calibration_label",
                "findings_count",
                "by_severity",
            ]
            for k in keys_to_show:
                if k in payload:
                    print(f"  {k}: {payload[k]}")

            print("\n=== Reading resource: finops://findings ===")
            content = await session.read_resource("finops://findings")
            try:
                findings = json.loads(content.contents[0].text)
                print(f"  total findings exposed: {len(findings)}")
                for f in findings[:3]:
                    print(
                        f"  - {f.get('rule_id'):<22} {f.get('resource_id'):<60.60} "
                        f"sev={f.get('severity'):<6} risk={f.get('risk_score'):>5.1f}"
                    )
            except Exception as e:  # noqa: BLE001
                print(f"  could not parse findings: {e}")

            print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
