"""Alert simulator endpoints.

`POST /alerts/webhook-test` fires a test payload at the configured WEBHOOK_URL.
`POST /alerts/alert-sink` is the self-loopback target — echoes whatever it
receives so the demo is self-contained (no external services).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from finops.api.schemas import AlertEcho, WebhookResult
from finops.api.webhooks import WebhookEmitter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook-test", response_model=WebhookResult, summary="Fire a test webhook")
async def webhook_test() -> WebhookResult:
    payload: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "message": "FinOps webhook smoke test",
    }
    result = await WebhookEmitter().send("test", payload)
    return WebhookResult(**result)


@router.post("/alert-sink", response_model=AlertEcho, summary="Self-loopback echo")
async def alert_sink(request: Request) -> AlertEcho:
    """Receives webhook payloads and echoes them. Default `WEBHOOK_URL` targets here."""
    body = await request.json()
    logger.info("alert sink received: %s", body)
    return AlertEcho(
        received=True,
        event_type=body.get("event_type"),
        payload=body.get("payload") or body,
    )
