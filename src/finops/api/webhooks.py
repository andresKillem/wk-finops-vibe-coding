"""WebhookEmitter — async POST with exponential backoff retry.

Used by the alerts endpoint and by the analyze flow when overall_risk > threshold.
The default URL points at the self-loopback `/alert-sink` so the demo runs
end-to-end without external services.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from finops.config import settings

logger = logging.getLogger(__name__)


class WebhookEmitter:
    """POST a JSON payload to a URL; retry up to N times with exponential backoff."""

    def __init__(self, url: str | None = None, max_retries: int = 3, timeout_s: float = 5.0) -> None:
        self.url = url or settings.webhook_url
        self.max_retries = max_retries
        self.timeout_s = timeout_s

    async def send(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Async POST. Returns result dict (sent, status_code, attempts, error?)."""
        body = {"event_type": event_type, "payload": payload}
        last_error: str | None = None
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = await client.post(self.url, json=body)
                    if resp.status_code < 500:
                        return {
                            "sent": resp.status_code < 400,
                            "status_code": resp.status_code,
                            "attempts": attempt,
                            "url": self.url,
                            "error": None if resp.status_code < 400 else resp.text[:200],
                        }
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                except httpx.HTTPError as e:
                    last_error = f"{type(e).__name__}: {e}"
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s
        return {
            "sent": False,
            "status_code": None,
            "attempts": self.max_retries,
            "url": self.url,
            "error": last_error or "exhausted retries",
        }
