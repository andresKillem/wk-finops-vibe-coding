"""Runtime configuration. Loaded from environment via pydantic-settings.

The single source of truth for every tunable. Modules import `settings` from here;
they do not read os.environ directly. This makes test overrides trivial and keeps
the surface area for misconfiguration small.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Project-wide runtime settings. Backed by .env at PROJECT_ROOT."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Anthropic ──
    anthropic_api_key: str = Field(default="", description="If empty, sub-agents fall back to deterministic templates")
    anthropic_orchestrator_model: str = "claude-opus-4-7"
    anthropic_worker_model: str = "claude-haiku-4-5"

    # ── Webhook simulator ──
    webhook_url: str = "http://localhost:8765/alert-sink"

    # ── Risk thresholds ──
    risk_threshold: int = 70
    severity_weight_low: int = 1
    severity_weight_medium: int = 3
    severity_weight_high: int = 8

    # ── Database ──
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'finops.db'}"

    # ── Servers ──
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    dashboard_port: int = 8501
    mcp_http_port: int = 8765

    @property
    def llm_enabled(self) -> bool:
        """True if we have an API key — sub-agents will use real Claude calls."""
        return bool(self.anthropic_api_key.strip())

    @property
    def severity_weight(self) -> dict[str, int]:
        return {
            "LOW": self.severity_weight_low,
            "MEDIUM": self.severity_weight_medium,
            "HIGH": self.severity_weight_high,
        }


settings = Settings()


SeverityLevel = Literal["LOW", "MEDIUM", "HIGH"]
ResourceType = Literal["ebs", "ec2", "eip", "nat", "rds", "elb", "s3", "other"]
RemediationFormat = Literal["aws_cli", "boto3", "terraform_import"]
