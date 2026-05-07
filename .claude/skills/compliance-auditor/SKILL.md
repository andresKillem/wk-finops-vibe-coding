---
name: compliance-auditor
description: Use when checking AWS resource tag compliance, ownership lineage, or environment classification before recommending remediation. Bonus skill — turns FinOps recommendations into governance-aware actions.
when_to_use: When the user asks "who owns this?", "is this prod?", "do we have a tag policy?", or before any plan generation when the resource has missing/inconsistent tags.
---

# Compliance Auditor

Bonus skill. The other three skills focus on cost waste; this one focuses on **governance hygiene** that gates whether we should act on the cost waste at all.

## When to invoke

- Before generating a remediation plan, if the resource has incomplete tags.
- When a user asks "who owns X" and we have access to billing tags.
- When the report shows >10% of resources untagged — this is itself a finding.

## Procedure

1. Inspect `Resource.metadata` for tags.
2. Check against the **standard tag baseline** (configurable, defaults below):
   - `Owner` — required, email or team handle
   - `Environment` — required, in {prod, staging, dev, sandbox}
   - `CostCenter` — required, alphanumeric
   - `Lifecycle` — optional, in {persistent, ephemeral, archive, expired}
3. Emit one Finding per violation (rule `R-TAG-*`).
4. **Critically**: if a HIGH-cost remediation target (e.g., RDS) has `Environment=prod`, downgrade the recommendation from "decommission" to "investigate ownership and confirm".

## Tag policies (configurable)

`config/tag_policy.yaml` (not yet implemented; placeholder for future):

```yaml
required_keys: [Owner, Environment, CostCenter]
allowed_environment_values: [prod, staging, dev, sandbox]
violation_severity: MEDIUM
unowned_prod_severity: HIGH  # special case
```

## Output

```json
{
  "tag_compliance_score": 0.73,
  "violations_by_resource": {...},
  "ownership_gaps": [...],
  "blocking_for_remediation": [<finding_ids that should not auto-proceed>]
}
```

## Why this matters in FinOps

A common failure mode: the Cost Analyzer recommends decommissioning an idle RDS, the engineer executes, and 48h later a quarterly batch job fails because that RDS *was* used — just not in the 7d window we measured. Tag compliance is how mature FinOps avoids this — `Lifecycle=ephemeral` resources can be auto-decommissioned; `Lifecycle=persistent` requires owner sign-off, period.
