"""Abstract base for sub-agents.

Every agent inherits the same lifecycle: receive input dict, produce
``AgentResponse``, persist an ``AgentRun`` audit row. Subclasses choose
their model and prompts; the base handles plumbing.
"""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from finops.config import settings
from finops.db.models import AgentRun
from finops.db.session import get_session, init_db

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Uniform shape every agent returns. JSON-serialisable; safe to put on the wire."""

    agent_name: str
    model: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    cost_estimate: float = 0.0
    fallback_mode: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "model": self.model,
            "success": self.success,
            "output": self.output,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "duration_ms": self.duration_ms,
            "cost_estimate": self.cost_estimate,
            "fallback_mode": self.fallback_mode,
            "error": self.error,
        }


# Per-million-token rates (USD), May 2026 published pricing.
MODEL_RATES: dict[str, tuple[float, float]] = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "deterministic-fallback": (0.0, 0.0),
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """USD cost estimate for a single call. Looks up the family prefix."""
    base = next((k for k in MODEL_RATES if model.startswith(k)), "deterministic-fallback")
    rate_in, rate_out = MODEL_RATES[base]
    return round((tokens_in * rate_in + tokens_out * rate_out) / 1_000_000.0, 6)


def extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first balanced ``{...}`` JSON object out of free-form text.

    Anthropic returns prose-then-JSON sometimes; this is the robust extraction.
    Returns ``{}`` if nothing parseable. Never raises.
    """
    if not text:
        return {}
    text = text.strip()
    # Strip markdown code fence if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        pass
    # Walk for first balanced object
    start = text.find("{")
    while start >= 0:
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        result = json.loads(candidate)
                        return result if isinstance(result, dict) else {}
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return {}


class BaseAgent(ABC):
    """Subclasses set ``name`` and ``model``; implement ``_run_llm`` and ``_run_fallback``."""

    name: str = "base"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or "deterministic-fallback"
        self._client = None

    @property
    def client(self):  # lazy import — avoids loading anthropic when fallback-only
        if self._client is None and settings.llm_enabled:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    @abstractmethod
    async def _run_llm(self, input_dict: dict[str, Any]) -> AgentResponse:
        """Live Anthropic call. Only invoked when settings.llm_enabled is True."""

    @abstractmethod
    def _run_fallback(self, input_dict: dict[str, Any]) -> AgentResponse:
        """Deterministic path. Same return shape as _run_llm. No network."""

    async def run(self, input_dict: dict[str, Any]) -> AgentResponse:
        """Public entrypoint. Routes to LLM or fallback, persists AgentRun."""
        init_db()
        start = time.perf_counter()
        try:
            if settings.llm_enabled and self.client is not None:
                resp = await self._run_llm(input_dict)
            else:
                resp = self._run_fallback(input_dict)
                resp.fallback_mode = True
        except Exception as e:  # noqa: BLE001 — agents must not bubble; degrade gracefully
            logger.exception("agent %s crashed; degrading to fallback", self.name)
            resp = self._run_fallback(input_dict)
            resp.fallback_mode = True
            resp.error = f"{type(e).__name__}: {e}"

        if resp.duration_ms == 0:
            resp.duration_ms = int((time.perf_counter() - start) * 1000)

        self._persist_run(resp, prompt_summary=json.dumps(input_dict)[:4000])
        return resp

    def _persist_run(self, resp: AgentResponse, prompt_summary: str = "") -> None:
        """Best-effort audit persist; never fails the agent's actual call."""
        try:
            with get_session() as s:
                s.add(
                    AgentRun(
                        agent_name=resp.agent_name,
                        model=resp.model,
                        prompt=prompt_summary[:5000],
                        response=resp.raw_response[:10000] if resp.raw_response else json.dumps(resp.output)[:10000],
                        tokens_in=resp.tokens_in,
                        tokens_out=resp.tokens_out,
                        duration_ms=resp.duration_ms,
                        cost_estimate=resp.cost_estimate,
                    )
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("AgentRun persist failed for %s: %s", resp.agent_name, e)
