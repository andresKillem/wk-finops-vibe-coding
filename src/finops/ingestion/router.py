"""Format detection + dispatch.

Public entrypoint: ``ingest_file(path)`` — detects format from extension and
header content, calls the right parser, returns an IngestSummary.

Convention: the function never raises for content errors (those land in
``summary.errors``). It only raises for filesystem-level problems
(``FileNotFoundError``).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Union

from finops.ingestion.aws_cur import is_cur_csv, parse_cur_csv
from finops.ingestion.azure_billing import parse_azure_json
from finops.ingestion.utils import IngestSummary


def ingest_file(path: Union[Path, str]) -> IngestSummary:
    """Detect a billing file's format and dispatch to the matching parser."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    suffix = p.suffix.lower()

    if suffix == ".csv":
        # Sniff first row to confirm it's a CUR
        try:
            with p.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
        except Exception as e:  # noqa: BLE001
            s = IngestSummary(file=str(p))
            s.errors.append(f"could not read CSV header: {type(e).__name__}: {e}")
            return s

        if not headers:
            s = IngestSummary(file=str(p), provider="aws")
            s.errors.append("empty CSV (no header row)")
            return s

        if is_cur_csv(headers):
            return parse_cur_csv(p)

        s = IngestSummary(file=str(p))
        s.errors.append(
            f"unrecognized CSV format (no lineItem/* columns); first headers: {headers[:4]}"
        )
        return s

    if suffix == ".json":
        return parse_azure_json(p)

    s = IngestSummary(file=str(p))
    s.errors.append(f"unsupported file extension: {suffix!r} — expected .csv or .json")
    return s
