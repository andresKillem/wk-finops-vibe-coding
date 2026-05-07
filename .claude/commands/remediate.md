---
description: Generate a safe remediation plan for one finding, in all three formats (aws_cli, boto3, terraform_import).
argument-hint: <finding_id> [format]
---

Use the `remediation-planner` skill (`.claude/skills/remediation-planner/SKILL.md`).

1. Look up the finding by `id`. If not found, list available finding IDs.
2. Run `uv run finops plan --finding-id <id> --format aws_cli`.
3. Run `uv run finops plan --finding-id <id> --format boto3`.
4. Run `uv run finops plan --finding-id <id> --format terraform_import`.
5. Render all three outputs in distinct fenced blocks with clear labels.
6. **Validate** each output via `safety_gate.validate(plan)`. If any fails, do not show that plan; show the violation reason instead.
7. Append the Slack-ready stakeholder communication block.

**Critical:** If `blast_radius == "high"`, prefix the output with a HIGH BLAST RADIUS warning and require user confirmation before they execute. Do not auto-execute, ever.

## Reference

- Skill: `remediation-planner/SKILL.md`
- Module: `src/finops/remediation/generator.py`
