"""AWS Cost & Usage Report (CUR) parser.

Tolerant by design: we accept any CSV that has the three minimum columns
(``lineItem/UsageStartDate``, ``lineItem/ResourceId``, ``lineItem/UnblendedCost``)
and use additional columns when present. We never fail the whole file because
of one bad row — bad rows go to ``IngestSummary.skipped`` with their line number
and the parser keeps moving.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from sqlmodel import select

from finops.db.models import BillingRecord, Resource
from finops.db.session import get_session, init_db
from finops.ingestion.utils import (
    IngestSummary,
    infer_resource_type_aws,
    parse_iso_date,
)

CUR_REQUIRED_COLS = (
    "lineItem/UsageStartDate",
    "lineItem/ResourceId",
    "lineItem/UnblendedCost",
)


def is_cur_csv(headers: list[str]) -> bool:
    """Heuristic: CUR CSVs have at least one ``lineItem/*`` column."""
    if not headers:
        return False
    return any(h.startswith("lineItem/") for h in headers)


def _extract_tags(row: dict[str, str]) -> dict[str, str]:
    """All ``resourceTags/user:Foo`` columns become ``{"Foo": value}``."""
    tags: dict[str, str] = {}
    for k, v in row.items():
        if not v:
            continue
        if k.startswith("resourceTags/user:"):
            tags[k.removeprefix("resourceTags/user:")] = v
        elif k.startswith("resourceTags/"):
            tags[k.removeprefix("resourceTags/")] = v
    return tags


def parse_cur_csv(path: Path) -> IngestSummary:
    """Parse an AWS CUR CSV file. Inserts BillingRecords; upserts Resources.

    Returns an IngestSummary capturing rows parsed, rows skipped (with reasons),
    resources upserted, observed period range, and any errors.
    """
    init_db()  # idempotent
    summary = IngestSummary(file=str(path), provider="aws")
    records: list[BillingRecord] = []
    resources_seen: dict[str, dict[str, Any]] = {}

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            summary.errors.append("empty CSV (no header row)")
            return summary
        if not is_cur_csv(list(reader.fieldnames)):
            summary.errors.append(
                f"not a CUR CSV (no lineItem/* columns); first headers: {reader.fieldnames[:4]}"
            )
            return summary

        for line_no, row in enumerate(reader, start=2):
            try:
                resource_id = (row.get("lineItem/ResourceId") or "").strip()
                if not resource_id:
                    summary.skipped += 1
                    continue

                cost = float(row.get("lineItem/UnblendedCost") or 0)
                usage_amount = float(row.get("lineItem/UsageAmount") or 0)

                start = parse_iso_date(row.get("lineItem/UsageStartDate"))
                end = parse_iso_date(row.get("lineItem/UsageEndDate")) or start
                if start is None:
                    summary.skipped += 1
                    summary.errors.append(f"line {line_no}: unparseable UsageStartDate")
                    continue

                product = (row.get("product/ProductName") or "").strip()
                usage_type = (row.get("lineItem/UsageType") or "").strip()
                region = (row.get("product/region") or "").strip()
                az = (row.get("lineItem/AvailabilityZone") or "").strip()
                if not region and az and len(az) > 1:
                    # us-east-1a -> us-east-1
                    region = az[:-1] if az[-1].isalpha() else az

                account_id = (
                    (row.get("lineItem/UsageAccountId") or "").strip()
                    or (row.get("bill/PayerAccountId") or "").strip()
                )

                records.append(
                    BillingRecord(
                        cloud_provider="aws",
                        account_id=account_id,
                        service=product,
                        resource_id=resource_id,
                        region=region or None,
                        usage_amount=usage_amount,
                        cost=cost,
                        period_start=start,
                        period_end=end,
                        raw_record=dict(row),
                    )
                )
                summary.rows_parsed += 1
                if summary.period_start is None or start < summary.period_start:
                    summary.period_start = start
                if summary.period_end is None or end > summary.period_end:
                    summary.period_end = end

                # Aggregate per-resource view
                rt = infer_resource_type_aws(resource_id, product, usage_type)
                tags = _extract_tags(row)
                instance_type = (row.get("product/instanceType") or "").strip()

                rprev = resources_seen.get(resource_id)
                if rprev is None:
                    resources_seen[resource_id] = {
                        "resource_id": resource_id,
                        "type": rt,
                        "region": region or None,
                        "account_id": account_id or None,
                        "monthly_cost": cost,
                        "last_seen": end,
                        "attrs": {
                            "product_name": product,
                            "instance_type": instance_type,
                            "availability_zone": az,
                            "usage_types": [usage_type] if usage_type else [],
                            "tags": tags,
                        },
                    }
                else:
                    rprev["monthly_cost"] = round(rprev["monthly_cost"] + cost, 6)
                    if end > rprev["last_seen"]:
                        rprev["last_seen"] = end
                    if usage_type and usage_type not in rprev["attrs"]["usage_types"]:
                        rprev["attrs"]["usage_types"].append(usage_type)
                    rprev["attrs"]["tags"].update(tags)
                    if instance_type and not rprev["attrs"].get("instance_type"):
                        rprev["attrs"]["instance_type"] = instance_type

            except Exception as e:  # noqa: BLE001 — tolerate any row-level error
                summary.skipped += 1
                summary.errors.append(f"line {line_no}: {type(e).__name__}: {e}")

    if not records:
        return summary

    # Persist
    with get_session() as session:
        session.add_all(records)
        for rid, info in resources_seen.items():
            existing = session.exec(select(Resource).where(Resource.resource_id == rid)).first()
            if existing:
                existing.monthly_cost = round(existing.monthly_cost + info["monthly_cost"], 6)
                if info["last_seen"] > existing.last_seen:
                    existing.last_seen = info["last_seen"]
                # Merge attrs (shallow)
                merged = {**existing.attrs, **info["attrs"]}
                # Merge tags deeply
                if "tags" in existing.attrs and "tags" in info["attrs"]:
                    merged["tags"] = {**existing.attrs["tags"], **info["attrs"]["tags"]}
                # Merge usage_types as union
                if "usage_types" in existing.attrs and "usage_types" in info["attrs"]:
                    merged["usage_types"] = sorted(
                        set(existing.attrs["usage_types"]) | set(info["attrs"]["usage_types"])
                    )
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
                        cloud_provider="aws",
                        last_seen=info["last_seen"],
                        monthly_cost=info["monthly_cost"],
                        attrs=info["attrs"],
                    )
                )
        summary.resources_upserted = len(resources_seen)

    return summary
