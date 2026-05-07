---
description: Ingest a billing file (AWS CUR CSV or Azure billing JSON) into the local SQLite database.
argument-hint: <file_path>
---

Run `uv run finops ingest <argument>` and report:
- File format detected (AWS CUR vs Azure)
- Row count parsed
- Date range (min → max billing period)
- Distinct resource count after upsert
- Any rows that failed to parse (with line numbers)

If the file does not exist or has zero parseable rows, fail loudly — do not write empty data to the DB.

## Reference

- Module: `src/finops/ingestion/router.py`
