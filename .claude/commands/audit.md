---
description: End-to-end FinOps audit — ingest a billing file, scan for orphaned/idle resources, run sub-agents for prioritization, output executive readout. Single command, full pipeline.
argument-hint: [billing_file_path] (default: samples/aws_cur_sample.csv)
---

You are running the `/audit` slash command. Execute this exact pipeline:

1. **Determine billing file.** Default `samples/aws_cur_sample.csv` if no argument provided. If argument is a directory, pick the most recent `.csv` or `.json` inside.
2. **Reset and ingest.** `make reset && uv run finops ingest <file>`.
3. **Scan.** `uv run finops scan` — capture the rich-table output.
4. **Analyze with sub-agents.** `uv run finops analyze` — capture the JSON output.
5. **Generate plans for top 3 findings.** Loop: `uv run finops plan --finding-id N --format aws_cli` for the top 3 by `risk_score`.
6. **Render executive readout.** Output a markdown block with:
   - Total monthly waste in $
   - Overall risk score (with calibration label per `references/risk-scoring.md`)
   - Top 5 findings as a table
   - The 3-bullet executive narrative from the Analyzer
   - Links to the 3 generated plans
7. **Append to `prompts.md`.** Add this audit invocation as a new entry with timestamp and outcome.
8. **Report Elapsed Time.**

If any step fails, **stop the pipeline** — do not proceed with downstream steps on stale data. Report the failure and which step failed.

## Reference

- Skill: `finops-architect/SKILL.md`
- Reference: `finops-architect/references/risk-scoring.md`
