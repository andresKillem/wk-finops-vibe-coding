# Remediation Patterns

Every `Finding` produces a `RemediationPlan` in **three formats**. The user picks based on their team's tooling. None of these auto-execute — they are artifacts a human approves and runs.

## Format selection guide

| Format | When to use | Audit trail |
|---|---|---|
| `aws_cli` | One-off cleanups, on-call playbooks, breakglass | Logged in CloudTrail |
| `boto3` | Programmatic jobs, scheduled cleanup, multi-region loops | Logged in CloudTrail + your script logs |
| `terraform_import` | Resource is *managed* by IaC and we need to import-then-destroy through pipeline | Logged in IaC repo + Terraform Cloud |

## Universal safe defaults

Regardless of format, every plan must:

1. **Pre-check:** verify the resource still matches the criteria *right now*. Cost/state may have changed since the last billing export.
2. **Snapshot first** for any stateful resource (EBS volume, RDS instance, S3 bucket).
3. **Dry-run first.** AWS CLI `--dry-run`, boto3 `DryRun=True` where supported.
4. **Idempotent.** Re-running the plan after partial success must not corrupt state.
5. **Rollback notes.** Every plan ships with a "how to undo this within 24h" section.
6. **Blast radius scoring** in the plan header: `low` (single resource), `medium` (resource + dependents), `high` (resource + dependents + downstream consumers).

## Forbidden patterns

The `safety_gate` validator rejects any generated plan containing:

- `--force` (any AWS CLI subcommand)
- `--skip-final-snapshot` (RDS)
- `rm -rf` (any path)
- `kubectl delete --all`
- `terraform destroy -auto-approve`

If these are genuinely required, the user must override via `--unsafe-confirm` flag and the override is logged in `prompts.md`.

## Example — orphaned EBS volume

```bash
# aws_cli format
# pre-check
aws ec2 describe-volumes --volume-ids vol-0abc --query 'Volumes[0].State'
# expected: "available"

# snapshot
aws ec2 create-snapshot --volume-id vol-0abc \
  --description "Pre-decommission snapshot via finops-optimizer $(date -u +%Y-%m-%dT%H:%M:%SZ)"
# wait for snapshot completed before proceeding

# delete (dry-run first)
aws ec2 delete-volume --volume-id vol-0abc --dry-run
aws ec2 delete-volume --volume-id vol-0abc
```

```python
# boto3 format
import boto3, logging
ec2 = boto3.client("ec2")
v = ec2.describe_volumes(VolumeIds=["vol-0abc"])["Volumes"][0]
assert v["State"] == "available", "Volume no longer orphaned"
snap = ec2.create_snapshot(VolumeId="vol-0abc", Description="pre-decommission")
ec2.get_waiter("snapshot_completed").wait(SnapshotIds=[snap["SnapshotId"]])
ec2.delete_volume(VolumeId="vol-0abc")
logging.info("Decommissioned vol-0abc; snapshot retained: %s", snap["SnapshotId"])
```

```hcl
# terraform_import format — for IaC-managed accounts
# 1. import existing into state
# terraform import aws_ebs_volume.orphan_0abc vol-0abc
resource "aws_ebs_volume" "orphan_0abc" {
  availability_zone = "us-east-1a"
  size              = 100
  # mark for destroy in next plan/apply
  lifecycle {
    prevent_destroy = false
  }
}
# 2. remove the resource block
# 3. terraform plan + apply -- pipeline-gated
```

## Communication template

Every plan ships with a Slack-ready stakeholder message. Example:

> :warning: FinOps action required — orphaned EBS `vol-0abc` (us-east-1a, 100GB gp3, $80/mo)
> **Plan:** snapshot → delete via aws_cli
> **Blast radius:** low — no attached instances detected for 12 days
> **Approval:** :+1: from infra-on-call · ETA execute: 24h after approval
> **Rollback:** restore from snapshot `snap-xxxxx` (retained 30d)
