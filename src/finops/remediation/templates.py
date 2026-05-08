"""Jinja2 templates for every (resource_type, format) pair.

The matrix is 6 types × 3 formats = 18 templates. We keep them inline (rather
than as separate files) so review and diff stay focused — every template is
visible in this single file.

Conventions enforced by every template:
- aws_cli   : starts with a pre-check, ends with a commented-out execute line
              the operator must uncomment after approval. Dry-run before live.
- boto3     : uses the SDK's DryRun / waiter primitives, logs every step,
              never auto-confirms anything destructive.
- terraform_import : import command + resource block + REMOVE-AND-APPLY notes;
              never includes -auto-approve on apply, never destroys directly.

NEVER include: --force, --skip-final-snapshot, rm -rf, terraform destroy, ...
The SafetyGate validator checks every rendered output against this list.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined

# Loader-less environment for in-memory templates. StrictUndefined surfaces
# missing context as an error during render, not a silent empty string.
_env = Environment(loader=BaseLoader(), undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)


def short_id(resource_id: str, max_len: int = 28) -> str:
    """Terraform-safe identifier derived from a long ARN/resource_id."""
    base = re.sub(r"[^a-zA-Z0-9]+", "_", resource_id).strip("_").lower()
    if len(base) > max_len:
        digest = hashlib.sha256(resource_id.encode()).hexdigest()[:6]
        base = base[: max_len - 7] + "_" + digest
    return base


# ─── EBS ──────────────────────────────────────────────────────────────────────
EBS_TEMPLATES = {
    "aws_cli": """\
# Pre-check: confirm the volume is still 'available' (orphaned)
aws ec2 describe-volumes --volume-ids {{ resource_id }} \\
  --region {{ region }} --query 'Volumes[0].State' --output text
# Expected: available

# Pre-decommission snapshot (retained 30 days; restorable)
SNAP_ID=$(aws ec2 create-snapshot \\
  --volume-id {{ resource_id }} --region {{ region }} \\
  --description "Pre-decommission via finops-optimizer ($(date -u +%FT%TZ))" \\
  --query 'SnapshotId' --output text)
echo "snapshot id: $SNAP_ID"

# Wait for snapshot to complete (do not delete volume before this returns)
aws ec2 wait snapshot-completed --snapshot-ids $SNAP_ID --region {{ region }}

# Dry-run the delete (verifies permissions + state without destruction)
aws ec2 delete-volume --volume-id {{ resource_id }} --region {{ region }} --dry-run

# Execute (uncomment ONLY after stakeholder approval):
# aws ec2 delete-volume --volume-id {{ resource_id }} --region {{ region }}

# Verify deletion
# aws ec2 describe-volumes --volume-ids {{ resource_id }} --region {{ region }} 2>&1 | grep -q 'InvalidVolume.NotFound' && echo OK
""",
    "boto3": """\
\"\"\"Decommission orphaned EBS volume {{ resource_id }} ({{ region }}).
Idempotent: snapshot first, then dry-run-then-live delete. No force flag, ever.
\"\"\"
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
ec2 = boto3.client("ec2", region_name="{{ region }}")

# Pre-check: confirm still orphaned
v = ec2.describe_volumes(VolumeIds=["{{ resource_id }}"])["Volumes"][0]
if v["State"] != "available":
    raise SystemExit(f"Aborting: {{ resource_id }} state is {v['State']}, not 'available'")
logger.info("pre-check OK: %s state=available", "{{ resource_id }}")

# Snapshot first (retained 30 days; restorable)
snap = ec2.create_snapshot(
    VolumeId="{{ resource_id }}",
    Description="Pre-decommission via finops-optimizer",
)
ec2.get_waiter("snapshot_completed").wait(SnapshotIds=[snap["SnapshotId"]])
logger.info("snapshot complete: %s", snap["SnapshotId"])

# Dry-run delete (raises DryRunOperation on success)
try:
    ec2.delete_volume(VolumeId="{{ resource_id }}", DryRun=True)
except ClientError as e:
    if "DryRunOperation" not in str(e):
        raise

# Live delete — require explicit env confirm (CONFIRM_DELETE=yes)
import os
if os.environ.get("CONFIRM_DELETE") != "yes":
    raise SystemExit("Set CONFIRM_DELETE=yes to execute the live deletion.")

ec2.delete_volume(VolumeId="{{ resource_id }}")
logger.info("deleted volume %s; snapshot retained: %s", "{{ resource_id }}", snap["SnapshotId"])
""",
    "terraform_import": """\
# Step 1 — import existing volume into Terraform state:
terraform import aws_ebs_volume.{{ tf_id }} {{ resource_id }}

# Step 2 — add this resource block to your module so state has a definition:
resource "aws_ebs_volume" "{{ tf_id }}" {
  availability_zone = "{{ az }}"
  size              = {{ size_gb | default(100) }}
  type              = "gp3"
  tags = {
    Name        = "{{ tf_id }}"
    DecommissionPlan = "finops-optimizer-orphaned-ebs"
  }
  lifecycle {
    prevent_destroy = false
  }
}

# Step 3 — remove the resource block above; then run (pipeline-gated):
#   terraform plan
#   terraform apply
# The next plan will show a destroy for {{ tf_id }}; apply removes the orphan
# the same way as any other Terraform-managed resource. NEVER auto-approve.
""",
}


# ─── EC2 ──────────────────────────────────────────────────────────────────────
EC2_TEMPLATES = {
    "aws_cli": """\
# Pre-check: instance type, state, last activity
aws ec2 describe-instances --instance-ids {{ resource_id }} \\
  --region {{ region }} \\
  --query 'Reservations[0].Instances[0].[InstanceType,State.Name,LaunchTime]' \\
  --output table

# Capture an AMI (so we can restore the running instance if needed)
AMI_ID=$(aws ec2 create-image \\
  --instance-id {{ resource_id }} --region {{ region }} \\
  --name "finops-{{ tf_id }}-$(date -u +%Y%m%d%H%M%S)" \\
  --description "Pre-decommission AMI" \\
  --no-reboot --query 'ImageId' --output text)
echo "AMI id: $AMI_ID"

# Stop first (recoverable for 24h before we terminate)
aws ec2 stop-instances --instance-ids {{ resource_id }} --region {{ region }}
aws ec2 wait instance-stopped --instance-ids {{ resource_id }} --region {{ region }}

# Dry-run the terminate
aws ec2 terminate-instances --instance-ids {{ resource_id }} --region {{ region }} --dry-run

# Execute terminate (uncomment ONLY after 24h soak + approval):
# aws ec2 terminate-instances --instance-ids {{ resource_id }} --region {{ region }}
""",
    "boto3": """\
\"\"\"Decommission idle/legacy EC2 {{ resource_id }} ({{ region }}).
Captures AMI before stop; live terminate requires CONFIRM_TERMINATE=yes.
\"\"\"
import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
ec2 = boto3.client("ec2", region_name="{{ region }}")

inst = ec2.describe_instances(InstanceIds=["{{ resource_id }}"])["Reservations"][0]["Instances"][0]
logger.info("pre-check: state=%s type=%s", inst["State"]["Name"], inst["InstanceType"])

ami = ec2.create_image(
    InstanceId="{{ resource_id }}",
    Name="finops-{{ tf_id }}-pre-decommission",
    Description="Pre-decommission AMI via finops-optimizer",
    NoReboot=True,
)
logger.info("AMI created: %s", ami["ImageId"])

if inst["State"]["Name"] not in ("stopped",):
    ec2.stop_instances(InstanceIds=["{{ resource_id }}"])
    ec2.get_waiter("instance_stopped").wait(InstanceIds=["{{ resource_id }}"])
    logger.info("instance stopped")

try:
    ec2.terminate_instances(InstanceIds=["{{ resource_id }}"], DryRun=True)
except ClientError as e:
    if "DryRunOperation" not in str(e):
        raise

if os.environ.get("CONFIRM_TERMINATE") != "yes":
    raise SystemExit("Set CONFIRM_TERMINATE=yes to execute live termination.")

ec2.terminate_instances(InstanceIds=["{{ resource_id }}"])
logger.info("terminated %s; AMI retained: %s", "{{ resource_id }}", ami["ImageId"])
""",
    "terraform_import": """\
# Step 1 — import:
terraform import aws_instance.{{ tf_id }} {{ resource_id }}

# Step 2 — resource block (Terraform will populate attributes from the import):
resource "aws_instance" "{{ tf_id }}" {
  # All attributes come from the imported state. After import, run:
  #   terraform plan
  # to see the inferred config; copy it here, then proceed.
  lifecycle {
    prevent_destroy = false
  }
}

# Step 3 — remove the block above; pipeline-gated apply will destroy:
#   terraform plan
#   terraform apply        # never auto-approve
""",
}


# ─── EIP ──────────────────────────────────────────────────────────────────────
EIP_TEMPLATES = {
    "aws_cli": """\
# Pre-check: confirm not associated
aws ec2 describe-addresses --allocation-ids {{ resource_id }} \\
  --region {{ region }} \\
  --query 'Addresses[0].[AssociationId,PublicIp]' --output table
# Expected: AssociationId is null

# Release the EIP (idempotent and safe — no data loss possible)
aws ec2 release-address --allocation-id {{ resource_id }} --region {{ region }} --dry-run

# Execute (uncomment after confirming AssociationId is null):
# aws ec2 release-address --allocation-id {{ resource_id }} --region {{ region }}
""",
    "boto3": """\
\"\"\"Release dangling Elastic IP {{ resource_id }} ({{ region }}).\"\"\"
import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
ec2 = boto3.client("ec2", region_name="{{ region }}")

addr = ec2.describe_addresses(AllocationIds=["{{ resource_id }}"])["Addresses"][0]
if addr.get("AssociationId"):
    raise SystemExit(f"EIP {{ resource_id }} is associated to {addr['AssociationId']}; not releasing.")
logger.info("pre-check OK: EIP %s is unassociated", addr.get("PublicIp"))

try:
    ec2.release_address(AllocationId="{{ resource_id }}", DryRun=True)
except ClientError as e:
    if "DryRunOperation" not in str(e):
        raise

if os.environ.get("CONFIRM_RELEASE") != "yes":
    raise SystemExit("Set CONFIRM_RELEASE=yes to release.")

ec2.release_address(AllocationId="{{ resource_id }}")
logger.info("released EIP %s", "{{ resource_id }}")
""",
    "terraform_import": """\
# Step 1 — import:
terraform import aws_eip.{{ tf_id }} {{ resource_id }}

# Step 2 — resource block:
resource "aws_eip" "{{ tf_id }}" {
  domain = "vpc"
  lifecycle {
    prevent_destroy = false
  }
}

# Step 3 — remove block; pipeline-gated apply releases the address:
#   terraform plan
#   terraform apply        # never auto-approve
""",
}


# ─── NAT Gateway ──────────────────────────────────────────────────────────────
NAT_TEMPLATES = {
    "aws_cli": """\
# Pre-check: state + recent traffic
aws ec2 describe-nat-gateways --nat-gateway-ids {{ resource_id }} \\
  --region {{ region }} --query 'NatGateways[0].[State,VpcId,SubnetId]' \\
  --output table

# Capture route tables that reference this NAT (you must update them BEFORE delete)
aws ec2 describe-route-tables --region {{ region }} \\
  --filters "Name=route.nat-gateway-id,Values={{ resource_id }}" \\
  --query 'RouteTables[].[RouteTableId]' --output text > /tmp/finops_nat_rts.txt
echo "Route tables to update:" && cat /tmp/finops_nat_rts.txt

# Manual step — update each route table to point its 0.0.0.0/0 elsewhere
# (e.g., to an Internet Gateway for public subnets, or remove the route).
# DO NOT proceed past this comment until route tables are updated.

# Dry-run delete
aws ec2 delete-nat-gateway --nat-gateway-id {{ resource_id }} --region {{ region }} --dry-run

# Execute (uncomment AFTER route tables are updated):
# aws ec2 delete-nat-gateway --nat-gateway-id {{ resource_id }} --region {{ region }}
""",
    "boto3": """\
\"\"\"Delete idle NAT Gateway {{ resource_id }} ({{ region }}).
Lists referencing route tables for the operator to update FIRST.
\"\"\"
import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
ec2 = boto3.client("ec2", region_name="{{ region }}")

ng = ec2.describe_nat_gateways(NatGatewayIds=["{{ resource_id }}"])["NatGateways"][0]
logger.info("NAT %s state=%s vpc=%s", "{{ resource_id }}", ng["State"], ng["VpcId"])

rts = ec2.describe_route_tables(
    Filters=[{"Name": "route.nat-gateway-id", "Values": ["{{ resource_id }}"]}]
)["RouteTables"]
referencing_rts = [rt["RouteTableId"] for rt in rts]
if referencing_rts:
    logger.warning("NAT is referenced by %d route table(s): %s", len(referencing_rts), referencing_rts)
    if os.environ.get("ACK_ROUTE_TABLES_UPDATED") != "yes":
        raise SystemExit(
            "Update the listed route tables to no longer reference this NAT, "
            "then re-run with ACK_ROUTE_TABLES_UPDATED=yes."
        )

try:
    ec2.delete_nat_gateway(NatGatewayId="{{ resource_id }}", DryRun=True)
except ClientError as e:
    if "DryRunOperation" not in str(e):
        raise

if os.environ.get("CONFIRM_DELETE") != "yes":
    raise SystemExit("Set CONFIRM_DELETE=yes to execute.")

ec2.delete_nat_gateway(NatGatewayId="{{ resource_id }}")
logger.info("delete initiated for NAT %s", "{{ resource_id }}")
""",
    "terraform_import": """\
# Step 1 — import:
terraform import aws_nat_gateway.{{ tf_id }} {{ resource_id }}

# Step 2 — resource block:
resource "aws_nat_gateway" "{{ tf_id }}" {
  # Inferred from import — run `terraform plan` to see attributes.
  lifecycle {
    prevent_destroy = false
  }
}

# Step 3 — UPDATE referencing route tables FIRST, then remove block, then:
#   terraform plan
#   terraform apply        # never auto-approve
""",
}


# ─── RDS ──────────────────────────────────────────────────────────────────────
RDS_TEMPLATES = {
    "aws_cli": """\
# Pre-check: instance class + endpoint + status
aws rds describe-db-instances --db-instance-identifier {{ rds_id }} \\
  --region {{ region }} \\
  --query 'DBInstances[0].[DBInstanceStatus,DBInstanceClass,Endpoint.Address]' \\
  --output table

# Take a final snapshot (THIS IS REQUIRED — never delete RDS without one)
SNAP_NAME=finops-{{ rds_id }}-final-$(date -u +%Y%m%d%H%M%S)
aws rds create-db-snapshot --db-instance-identifier {{ rds_id }} \\
  --db-snapshot-identifier $SNAP_NAME --region {{ region }}

# Wait for snapshot to complete
aws rds wait db-snapshot-completed \\
  --db-snapshot-identifier $SNAP_NAME --region {{ region }}

# Delete WITH a FinalSnapshotIdentifier; final snapshot is mandatory.
# Execute (uncomment after stakeholder approval):
# aws rds delete-db-instance --db-instance-identifier {{ rds_id }} \\
#   --final-db-snapshot-identifier ${SNAP_NAME}-delete-final \\
#   --region {{ region }}
""",
    "boto3": """\
\"\"\"Delete idle RDS {{ rds_id }} ({{ region }}). Always with final snapshot.\"\"\"
import os
import logging
import boto3

logger = logging.getLogger(__name__)
rds = boto3.client("rds", region_name="{{ region }}")

inst = rds.describe_db_instances(DBInstanceIdentifier="{{ rds_id }}")["DBInstances"][0]
logger.info("RDS %s status=%s class=%s", "{{ rds_id }}", inst["DBInstanceStatus"], inst["DBInstanceClass"])

import datetime as _dt
snap_id = f"finops-{{ rds_id }}-final-{_dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

rds.create_db_snapshot(DBInstanceIdentifier="{{ rds_id }}", DBSnapshotIdentifier=snap_id)
rds.get_waiter("db_snapshot_completed").wait(DBSnapshotIdentifier=snap_id)
logger.info("final snapshot complete: %s", snap_id)

if os.environ.get("CONFIRM_DELETE_RDS") != "yes":
    raise SystemExit("Set CONFIRM_DELETE_RDS=yes to delete (final snapshot retained).")

# Note: FinalDBSnapshotIdentifier is mandatory — final snapshot retained on delete.
rds.delete_db_instance(
    DBInstanceIdentifier="{{ rds_id }}",
    FinalDBSnapshotIdentifier=f"{snap_id}-final",
)
logger.info("delete initiated; final snapshot will be: %s-final", snap_id)
""",
    "terraform_import": """\
# Step 1 — import:
terraform import aws_db_instance.{{ tf_id }} {{ rds_id }}

# Step 2 — resource block (CRITICAL: skip_final_snapshot must remain false):
resource "aws_db_instance" "{{ tf_id }}" {
  # Attributes inferred from import.
  skip_final_snapshot       = false  # final snapshot is mandatory
  final_snapshot_identifier = "finops-{{ rds_id }}-final-decommission"
  deletion_protection       = false  # only release when ready to delete

  lifecycle {
    prevent_destroy = false
  }
}

# Step 3 — pipeline-gated apply destroys with final snapshot retained:
#   terraform plan
#   terraform apply        # never auto-approve
""",
}


# ─── ELB ──────────────────────────────────────────────────────────────────────
ELB_TEMPLATES = {
    "aws_cli": """\
# Pre-check: target health
aws elbv2 describe-target-health --target-group-arn $(\\
  aws elbv2 describe-target-groups --load-balancer-arn {{ resource_id }} \\
    --region {{ region }} --query 'TargetGroups[0].TargetGroupArn' --output text\\
) --region {{ region }} --query 'TargetHealthDescriptions[*].TargetHealth.State' --output text

# Confirm DNS no longer resolves to this LB (manual DNS check)
echo "Verify DNS records pointing to {{ resource_id }} have been removed; otherwise expect customer-visible 5xx."

# Dry-run delete (elbv2 does not support DryRun; describe instead)
aws elbv2 describe-load-balancers --load-balancer-arns {{ resource_id }} \\
  --region {{ region }} --query 'LoadBalancers[0].LoadBalancerName' --output text

# Execute (uncomment after DNS verification + approval):
# aws elbv2 delete-load-balancer --load-balancer-arn {{ resource_id }} --region {{ region }}
""",
    "boto3": """\
\"\"\"Delete unused Load Balancer {{ resource_id }} ({{ region }}).\"\"\"
import os
import logging
import boto3

logger = logging.getLogger(__name__)
elb = boto3.client("elbv2", region_name="{{ region }}")

lb = elb.describe_load_balancers(LoadBalancerArns=["{{ resource_id }}"])["LoadBalancers"][0]
logger.info("LB %s state=%s scheme=%s", lb["LoadBalancerName"], lb["State"]["Code"], lb["Scheme"])

# Verify zero healthy targets
tgs = elb.describe_target_groups(LoadBalancerArn="{{ resource_id }}")["TargetGroups"]
unhealthy_only = True
for tg in tgs:
    health = elb.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])
    healthy = sum(1 for t in health["TargetHealthDescriptions"] if t["TargetHealth"]["State"] == "healthy")
    if healthy > 0:
        unhealthy_only = False
        logger.warning("TG %s has %d healthy targets; ABORT deletion", tg["TargetGroupArn"], healthy)
if not unhealthy_only:
    raise SystemExit("LB has healthy targets; not deleting.")

if os.environ.get("CONFIRM_DELETE_LB") != "yes":
    raise SystemExit("Set CONFIRM_DELETE_LB=yes; ensure DNS records pointing here are also removed.")

elb.delete_load_balancer(LoadBalancerArn="{{ resource_id }}")
logger.info("delete initiated for LB %s", "{{ resource_id }}")
""",
    "terraform_import": """\
# Step 1 — import:
terraform import aws_lb.{{ tf_id }} {{ resource_id }}

# Step 2 — resource block:
resource "aws_lb" "{{ tf_id }}" {
  # Attributes inferred from import.
  enable_deletion_protection = false  # set true while in service
  lifecycle {
    prevent_destroy = false
  }
}

# Step 3 — pipeline-gated apply removes the LB:
#   terraform plan
#   terraform apply        # never auto-approve
""",
}


TEMPLATES: dict[str, dict[str, str]] = {
    "ebs": EBS_TEMPLATES,
    "ec2": EC2_TEMPLATES,
    "eip": EIP_TEMPLATES,
    "nat": NAT_TEMPLATES,
    "rds": RDS_TEMPLATES,
    "elb": ELB_TEMPLATES,
}


def render_template(resource_type: str, fmt: str, context: dict[str, Any]) -> str:
    """Render the (resource_type, fmt) template with the given context."""
    if resource_type not in TEMPLATES:
        raise KeyError(f"no template for resource type: {resource_type!r}")
    if fmt not in TEMPLATES[resource_type]:
        raise KeyError(f"no template for ({resource_type!r}, {fmt!r})")

    template_str = TEMPLATES[resource_type][fmt]
    template = _env.from_string(template_str)
    return template.render(**context)
