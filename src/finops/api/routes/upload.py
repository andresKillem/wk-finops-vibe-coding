"""POST /upload — multipart upload of a CSV (AWS CUR) or JSON (Azure) billing export."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from finops.api.schemas import IngestSummaryOut
from finops.ingestion.router import ingest_file

router = APIRouter()


@router.post("", response_model=IngestSummaryOut, summary="Upload a billing export")
async def upload(file: UploadFile = File(..., description="CSV (AWS CUR) or JSON (Azure)")) -> IngestSummaryOut:
    if not file.filename:
        raise HTTPException(400, "filename missing from upload")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".csv", ".json"}:
        raise HTTPException(400, f"unsupported file type {suffix!r}; expected .csv or .json")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        summary = ingest_file(tmp_path)
        return IngestSummaryOut(
            file=file.filename,
            provider=summary.provider,
            rows_parsed=summary.rows_parsed,
            skipped=summary.skipped,
            resources_upserted=summary.resources_upserted,
            period_start=summary.period_start.isoformat() if summary.period_start else None,
            period_end=summary.period_end.isoformat() if summary.period_end else None,
            errors=summary.errors,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
