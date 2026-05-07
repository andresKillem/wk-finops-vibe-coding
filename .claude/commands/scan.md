---
description: Run the detection rules engine against the current ingested data. Outputs findings table + aggregate risk score.
---

Run `uv run finops scan` and present:
- Rich table of findings (resource, type, severity, monthly_savings, risk_score)
- Aggregate metrics: total monthly waste, overall risk score, calibration label
- Count of findings per rule_id
- Top 3 findings highlighted

If no findings: state explicitly "no waste detected — account hygiene is good" rather than printing an empty table.

## Reference

- Module: `src/finops/detection/engine.py`
- Skill: `finops-architect/references/detection-rules.md`
