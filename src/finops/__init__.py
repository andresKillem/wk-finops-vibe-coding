"""FinOps Cloud Cost Optimizer & Remediation Engine.

Wolters Kluwer 2026 Vibe Coding Challenge — Project 1.

Modules:
    api          — FastAPI REST surface
    agents       — Anthropic sub-agent orchestration
    db           — SQLModel data layer (SQLite)
    detection    — Rules engine + risk scoring
    ingestion    — AWS CUR / Azure billing parsers
    remediation  — Multi-format plan generator + safety gates
    mcp_server   — MCP protocol exposure
    dashboard    — Streamlit UI
    utils        — shared utilities
"""

__version__ = "0.1.0"
