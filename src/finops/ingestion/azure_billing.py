"""Azure billing / Consumption API JSON parser.

Supports two shapes:

1. **Nested** — Azure Consumption API response:
   ``[{"id": ..., "name": ..., "properties": {"resourceId": ..., "cost": ...}}, ...]``

2. **Flat** — simplified exports (CSV-converted-to-JSON style):
   ``[{"resourceId": ..., "cost": ..., "date": ..., "subscriptionId": ...}, ...]``

The parser auto-detects shape per record; mixed files are tolerated.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from sqlmodel import select

from finops.db.models import BillingRecord, Resource
from finops.db.session import get_session, init_db
from finops.ingestion.utils import (
    IngestSummary,
    infer_resource_type_azure,
    parse_iso_date,
)


def _normalize_record(rec: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Fold a nested-or-flat Azure record into our common shape."""
    if not isinstance(rec, dict):
        return None
    if "properties" in rec and isinstance(rec["properties"], dict):
        p = rec["properties"]
        return {
            "resource_id": p.get("resourceId") or "",
            "service": p.get("consumedService") or p.get("product") or "",
            "region": p.get("resourceLocation") or "",
            "cost": p.get("cost") or p.get("costInBillingCurrency") or 0,
            "usage_amount": p.get("quantity") or 0,
            "period_start": p.get("billingPeriodStartDate") or p.get("date"),
            "period_end": p.get("billingPeriodEndDate") or p.get("date"),
            "account_id": p.get("subscriptionId") or "",
            "instance_type": p.get("meterCategory") or p.get("meterSubCategory") or "",
            "tags": p.get("tags") or {},
            "raw": rec,
        }
    # Flat shape
    return {
        "resource_id": rec.get("resourceId") or rec.get("resource_id") or "",
        "service": rec.get("service") or rec.get("product") or rec.get("consumedService") or "",
        "region": rec.get("region") or rec.get("resourceLocation") or rec.get("location") or "",
        "cost": rec.get("cost") or rec.get("costInBillingCurrency") or 0,
        "usage_amount": rec.get("quantity") or rec.get("usage_amount") or 0,
        "period_start": rec.get("date") or rec.get("usageStart") or rec.get("billingPeriodStartDate"),
        "period_end": rec.get("date") or rec.get("usageEnd") or rec.get("billingPeriodEndDate"),
        "account_id": rec.get("subscriptionId") or rec.get("account_id") or "",
        "instance_type": rec.get("meterCategory") or rec.get("meterSubCategory") or "",
        "tags": rec.get("tags") or {},
        "raw": rec,
    }


def parse_azure_json(path: Path) -> IngestSummary:
    """Parse an Azure billing JSON file. Inserts BillingRecords; upserts Resources."""
    init_db()
    summary = IngestSummary(file=str(path), provider="azure")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        summary.errors.append(f"invalid JSON: {e.msg} (line {e.lineno})")
        return summary

    if isinstance(raw, dict) and "value" in raw and isinstance(raw["value"], list):
        # Azure paginated wrapper: {"value": [...], "nextLink": ...}
        records_raw = raw["value"]
    elif isinstance(raw, list):
        records_raw = raw
    else:
        summary.errors.append(
            f"unrecognized JSON shape: expected list or {{'value':[...]}}; got {type(raw).__name__}"
        )
        return summary

    records: list[BillingRecord] = []
    resources_seen: dict[str, dict[str, Any]] = {}

    for idx, rec in enumerate(records_raw):
        try:
            n = _normalize_record(rec)
            if n is None:
                summary.skipped += 1
                summary.errors.append(f"item {idx}: not a dict")
                continue

            rid = (n["resource_id"] or "").strip()
            if not rid:
                summary.skipped += 1
                continue

            cost = float(n["cost"] or 0)
            usage_amount = float(n["usage_amount"] or 0)
            start = parse_iso_date(n["period_start"])
            end = parse_iso_date(n["period_end"]) or start
            if start is None:
                summary.skipped += 1
                summary.errors.append(f"item {idx}: unparseable date")
                continue

            records.append(
                BillingRecord(
                    cloud_provider="azure",
                    account_id=n["account_id"],
                    service=n["service"],
                    resource_id=rid,
                    region=n["region"] or None,
                    usage_amount=usage_amount,
                    cost=cost,
                    period_start=start,
                    period_end=end,
                    raw_record=n["raw"],
                )
            )
            summary.rows_parsed += 1
            if summary.period_start is None or start < summary.period_start:
                summary.period_start = start
            if summary.period_end is None or end > summary.period_end:
                summary.period_end = end

            rt = infer_resource_type_azure(rid)
            rprev = resources_seen.get(rid)
            if rprev is None:
                resources_seen[rid] = {
                    "resource_id": rid,
                    "type": rt,
                    "region": n["region"] or None,
                    "account_id": n["account_id"] or None,
                    "monthly_cost": cost,
                    "last_seen": end,
                    "attrs": {
                        "service": n["service"],
                        "instance_type": n["instance_type"],
                        "tags": dict(n["tags"]) if isinstance(n["tags"], dict) else {},
                    },
                }
            else:
                rprev["monthly_cost"] = round(rprev["monthly_cost"] + cost, 6)
                if end > rprev["last_seen"]:
                    rprev["last_seen"] = end
                if isinstance(n["tags"], dict):
                    rprev["attrs"]["tags"].update(n["tags"])

        except Exception as e:  # noqa: BLE001
            summary.skipped += 1
            summary.errors.append(f"item {idx}: {type(e).__name__}: {e}")

    if not records:
        return summary

    with get_session() as session:
        session.add_all(records)
        for rid, info in resources_seen.items():
            existing = session.exec(select(Resource).where(Resource.resource_id == rid)).first()
            if existing:
                # REPLACE not add — see aws_cur.py for rationale (idempotency).
                existing.monthly_cost = round(info["monthly_cost"], 6)
                if info["last_seen"] > existing.last_seen:
                    existing.last_seen = info["last_seen"]
                merged = {**existing.attrs, **info["attrs"]}
                if "tags" in existing.attrs and "tags" in info["attrs"]:
                    merged["tags"] = {**existing.attrs["tags"], **info["attrs"]["tags"]}
                existing.attrs = merged
                if info["type"] != "other" and existing.type == "other":
                    existing.type = info["type"]
                session.add(existing)
            else:
                session.add(
                    Resource(
                        resource_id=info["resource_id"],
                        type=info["type"],
                        state="unknown",
                        region=info["region"],
                        account_id=info["account_id"],
                        cloud_provider="azure",
                        last_seen=info["last_seen"],
                        monthly_cost=info["monthly_cost"],
                        attrs=info["attrs"],
                    )
                )
        summary.resources_upserted = len(resources_seen)

    return summary
