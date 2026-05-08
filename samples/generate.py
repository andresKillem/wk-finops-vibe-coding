"""Generate the realistic sample billing files.

Deterministic given a seed. Re-run after editing this generator to refresh
``aws_cur_sample.csv`` and ``azure_billing_sample.json``.

Usage:
    uv run python samples/generate.py [--seed=42]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# AWS CUR header set we emit. Real CUR has ~150+ columns; this is the meaningful subset.
AWS_HEADERS = [
    "bill/PayerAccountId",
    "bill/BillingPeriodStartDate",
    "bill/BillingPeriodEndDate",
    "lineItem/UsageAccountId",
    "lineItem/LineItemType",
    "lineItem/UsageStartDate",
    "lineItem/UsageEndDate",
    "lineItem/ProductCode",
    "lineItem/UsageType",
    "lineItem/Operation",
    "lineItem/AvailabilityZone",
    "lineItem/ResourceId",
    "lineItem/UsageAmount",
    "lineItem/UnblendedCost",
    "product/ProductName",
    "product/region",
    "product/instanceType",
    "resourceTags/user:Name",
    "resourceTags/user:Environment",
    "resourceTags/user:Owner",
    "resourceTags/user:Lifecycle",
]

ACCOUNT_ID = "123456789012"
PERIOD_START = datetime(2026, 4, 1)
PERIOD_END = datetime(2026, 4, 30, 23, 59, 59)

# 17 AWS resources covering the spec mix:
#   5 EBS (3 attached, 2 orphaned), 4 EC2 (2 active, 1 idle, 1 stopped 30d),
#   2 EIP (1 attached, 1 dangling), 2 NAT (1 active, 1 idle),
#   2 RDS (1 active, 1 idle), 2 ELB (1 healthy, 1 unhealthy)
AWS_RESOURCES: list[dict] = [
    # ── EBS volumes ──
    {"rid": "vol-0a1b2c3d4e5f60001", "type": "ebs", "az": "us-east-1a", "region": "us-east-1",
     "size_gb": 100, "lifecycle": "persistent", "name": "web-app-data-01", "env": "prod",
     "owner": "team-platform@example.com", "rate_per_gb_mo": 0.10},
    {"rid": "vol-0a1b2c3d4e5f60002", "type": "ebs", "az": "us-east-1a", "region": "us-east-1",
     "size_gb": 50, "lifecycle": "persistent", "name": "api-cache-01", "env": "prod",
     "owner": "team-platform@example.com", "rate_per_gb_mo": 0.10},
    {"rid": "vol-0a1b2c3d4e5f60003", "type": "ebs", "az": "us-east-1b", "region": "us-east-1",
     "size_gb": 200, "lifecycle": "persistent", "name": "database-replica-01", "env": "prod",
     "owner": "team-data@example.com", "rate_per_gb_mo": 0.10},
    {"rid": "vol-0a1b2c3d4e5f60004", "type": "ebs", "az": "us-west-2a", "region": "us-west-2",
     "size_gb": 100, "lifecycle": "orphaned", "name": "migration-pilot-data", "env": "dev",
     "owner": "", "rate_per_gb_mo": 0.10},
    {"rid": "vol-0a1b2c3d4e5f60005", "type": "ebs", "az": "eu-west-1a", "region": "eu-west-1",
     "size_gb": 150, "lifecycle": "orphaned", "name": "", "env": "", "owner": "",
     "rate_per_gb_mo": 0.10},
    # ── EC2 instances ──
    {"rid": "i-0abc1234def567801", "type": "ec2", "az": "us-east-1a", "region": "us-east-1",
     "instance": "m5.xlarge", "lifecycle": "persistent", "name": "web-app-01", "env": "prod",
     "owner": "team-platform@example.com", "hourly_rate": 0.192, "cpu_avg": 45},
    {"rid": "i-0abc1234def567802", "type": "ec2", "az": "us-east-1b", "region": "us-east-1",
     "instance": "c5.2xlarge", "lifecycle": "persistent", "name": "worker-batch-01",
     "env": "prod", "owner": "team-data@example.com", "hourly_rate": 0.34, "cpu_avg": 62},
    {"rid": "i-0abc1234def567803", "type": "ec2", "az": "us-east-1c", "region": "us-east-1",
     "instance": "r5.large", "lifecycle": "idle", "name": "analytics-stage", "env": "stage",
     "owner": "team-data@example.com", "hourly_rate": 0.126, "cpu_avg": 3},
    {"rid": "i-0abc1234def567804", "type": "ec2", "az": "us-east-1a", "region": "us-east-1",
     "instance": "t2.medium", "lifecycle": "stopped", "name": "legacy-cron-01", "env": "dev",
     "owner": "", "hourly_rate": 0.0464, "cpu_avg": 0},
    # ── Elastic IPs ──
    {"rid": "eipalloc-0abc111222333", "type": "eip", "region": "us-east-1",
     "lifecycle": "persistent", "name": "edge-router-01", "env": "prod",
     "owner": "team-network@example.com"},
    {"rid": "eipalloc-0abc444555666", "type": "eip", "region": "us-east-1",
     "lifecycle": "orphaned", "name": "", "env": "", "owner": ""},
    # ── NAT Gateways ──
    {"rid": "nat-0a1b2c3d4e5f60001", "type": "nat", "region": "us-east-1", "az": "us-east-1a",
     "lifecycle": "persistent", "name": "vpc-prod-nat-01", "env": "prod",
     "owner": "team-network@example.com", "hourly_rate": 0.045, "gb_per_day": 8.5},
    {"rid": "nat-0a1b2c3d4e5f60002", "type": "nat", "region": "us-west-2", "az": "us-west-2a",
     "lifecycle": "idle", "name": "vpc-stage-nat-01", "env": "stage", "owner": "",
     "hourly_rate": 0.045, "gb_per_day": 0.0001},
    # ── RDS ──
    {"rid": "arn:aws:rds:us-east-1:123456789012:db:prod-postgres-01", "type": "rds",
     "region": "us-east-1", "instance": "db.r5.large", "lifecycle": "persistent",
     "name": "prod-postgres-01", "env": "prod", "owner": "team-data@example.com",
     "hourly_rate": 0.29},
    {"rid": "arn:aws:rds:us-east-1:123456789012:db:legacy-mysql-old", "type": "rds",
     "region": "us-east-1", "instance": "db.t2.medium", "lifecycle": "idle",
     "name": "legacy-mysql-old", "env": "dev", "owner": "", "hourly_rate": 0.084},
    # ── ELB ──
    {"rid": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/prod-alb-01/abc123",
     "type": "elb", "region": "us-east-1", "lifecycle": "persistent", "name": "prod-alb-01",
     "env": "prod", "owner": "team-platform@example.com", "hourly_rate": 0.0225},
    {"rid": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/stage-alb-test/def456",
     "type": "elb", "region": "us-east-1", "lifecycle": "idle", "name": "stage-alb-test",
     "env": "stage", "owner": "", "hourly_rate": 0.0225},
]


def _product_code(t: str) -> str:
    return {
        "ebs": "AmazonEC2",
        "ec2": "AmazonEC2",
        "nat": "AmazonEC2",
        "eip": "AmazonEC2",
        "rds": "AmazonRDS",
        "elb": "AWSELB",
    }.get(t, "AmazonEC2")


def _product_name(t: str) -> str:
    return {
        "ebs": "Amazon Elastic Compute Cloud",
        "ec2": "Amazon Elastic Compute Cloud",
        "nat": "Amazon Elastic Compute Cloud",
        "eip": "Amazon Elastic Compute Cloud",
        "rds": "Amazon Relational Database Service",
        "elb": "Amazon Elastic Load Balancing",
    }.get(t, "Amazon Elastic Compute Cloud")


def _emit_lines_for_resource(res: dict, rng: random.Random) -> list[dict]:
    """Produce ~12 daily aggregate line items for a resource."""
    lines: list[dict] = []
    days = sorted(rng.sample(range(30), k=12))  # 12 distinct days in April 2026
    base_row = {
        "bill/PayerAccountId": ACCOUNT_ID,
        "bill/BillingPeriodStartDate": PERIOD_START.strftime("%Y-%m-%dT00:00:00Z"),
        "bill/BillingPeriodEndDate": PERIOD_END.strftime("%Y-%m-%dT23:59:59Z"),
        "lineItem/UsageAccountId": ACCOUNT_ID,
        "lineItem/LineItemType": "Usage",
        "lineItem/ProductCode": _product_code(res["type"]),
        "lineItem/AvailabilityZone": res.get("az", ""),
        "lineItem/ResourceId": res["rid"],
        "product/ProductName": _product_name(res["type"]),
        "product/region": res.get("region", ""),
        "product/instanceType": res.get("instance", ""),
        "resourceTags/user:Name": res.get("name", ""),
        "resourceTags/user:Environment": res.get("env", ""),
        "resourceTags/user:Owner": res.get("owner", ""),
        "resourceTags/user:Lifecycle": res.get("lifecycle", ""),
    }
    for day_offset in days:
        usage_start = PERIOD_START + timedelta(days=day_offset)
        usage_end = usage_start + timedelta(hours=23, minutes=59)
        usage_amount = 0.0
        cost = 0.0
        usage_type = ""
        operation = ""

        if res["type"] == "ebs":
            usage_type = f"EBS:VolumeUsage.gp3"
            operation = "CreateVolume"
            # Daily portion of monthly per-GB cost
            usage_amount = res["size_gb"] / 30.0
            cost = res["size_gb"] * res["rate_per_gb_mo"] / 30.0
        elif res["type"] == "ec2":
            if res["lifecycle"] == "stopped":
                # Stopped instance: only EBS root volume cost (~$10/mo for 100GB gp3)
                usage_type = "EBS:VolumeUsage.gp3"
                operation = "CreateVolume"
                usage_amount = 100 / 30.0
                cost = 100 * 0.08 / 30.0
            else:
                usage_type = f"BoxUsage:{res['instance']}"
                operation = "RunInstances"
                hours = 24
                usage_amount = hours
                cost = hours * res["hourly_rate"]
        elif res["type"] == "eip":
            # Dangling EIP: $0.005/hour while not associated; persistent EIP is free when associated
            if res["lifecycle"] == "orphaned":
                usage_type = "ElasticIP:IdleAddress"
                operation = "ElasticIpIdle"
                usage_amount = 24
                cost = 24 * 0.005
            else:
                usage_type = "ElasticIP:InUseAddress"
                operation = "ElasticIpInUse"
                usage_amount = 24
                cost = 0.0
        elif res["type"] == "nat":
            usage_type = "NatGateway-Hours"
            operation = "NatGatewayUsage"
            hours = 24
            usage_amount = hours
            cost = hours * res["hourly_rate"]
            # Plus data processing — emit as a separate line via a small extra row
        elif res["type"] == "rds":
            usage_type = f"InstanceUsage:{res['instance']}"
            operation = "CreateDBInstance"
            usage_amount = 24
            cost = 24 * res["hourly_rate"]
        elif res["type"] == "elb":
            usage_type = "LoadBalancerUsage"
            operation = "ELBUsage"
            usage_amount = 24
            cost = 24 * res["hourly_rate"]

        row = dict(base_row)
        row.update(
            {
                "lineItem/UsageStartDate": usage_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lineItem/UsageEndDate": usage_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lineItem/UsageType": usage_type,
                "lineItem/Operation": operation,
                "lineItem/UsageAmount": f"{usage_amount:.4f}",
                "lineItem/UnblendedCost": f"{cost:.6f}",
            }
        )
        lines.append(row)

        # NAT extra: data processing line on the same day
        if res["type"] == "nat":
            gb = res["gb_per_day"]
            extra = dict(base_row)
            extra.update(
                {
                    "lineItem/UsageStartDate": usage_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "lineItem/UsageEndDate": usage_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "lineItem/UsageType": "NatGateway-Bytes",
                    "lineItem/Operation": "NatGatewayDataProcessed",
                    "lineItem/UsageAmount": f"{gb:.6f}",
                    "lineItem/UnblendedCost": f"{gb * 0.045:.6f}",
                }
            )
            lines.append(extra)

    return lines


def generate_aws_cur(seed: int = 42, output: Path | None = None) -> Path:
    """Write ``samples/aws_cur_sample.csv`` and return its path."""
    output = output or SCRIPT_DIR / "aws_cur_sample.csv"
    rng = random.Random(seed)

    rows: list[dict] = []
    for res in AWS_RESOURCES:
        rows.extend(_emit_lines_for_resource(res, rng))

    rng.shuffle(rows)  # interleave so a parser must handle out-of-order resources

    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AWS_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    return output


# ── Azure ──────────────────────────────────────────────────────────────────────
AZURE_RESOURCES: list[dict] = [
    # 5 managed disks
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Compute/disks/disk-web-01",
     "type": "ebs", "region": "eastus", "lifecycle": "persistent", "name": "disk-web-01",
     "size_gb": 128, "rate_per_gb_mo": 0.05},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Compute/disks/disk-api-01",
     "type": "ebs", "region": "eastus", "lifecycle": "persistent", "name": "disk-api-01",
     "size_gb": 64, "rate_per_gb_mo": 0.05},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-data/providers/Microsoft.Compute/disks/disk-db-replica",
     "type": "ebs", "region": "eastus", "lifecycle": "persistent", "name": "disk-db-replica",
     "size_gb": 256, "rate_per_gb_mo": 0.05},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-archive/providers/Microsoft.Compute/disks/disk-orphan-01",
     "type": "ebs", "region": "westus2", "lifecycle": "orphaned", "name": "disk-orphan-01",
     "size_gb": 128, "rate_per_gb_mo": 0.05},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-archive/providers/Microsoft.Compute/disks/disk-orphan-02",
     "type": "ebs", "region": "westus2", "lifecycle": "orphaned", "name": "disk-orphan-02",
     "size_gb": 200, "rate_per_gb_mo": 0.05},
    # 4 VMs
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-web-01",
     "type": "ec2", "region": "eastus", "lifecycle": "persistent", "name": "vm-web-01",
     "instance": "Standard_D4s_v5", "hourly_rate": 0.192},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-worker-01",
     "type": "ec2", "region": "eastus", "lifecycle": "persistent", "name": "vm-worker-01",
     "instance": "Standard_F8s_v2", "hourly_rate": 0.34},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-stage/providers/Microsoft.Compute/virtualMachines/vm-analytics-idle",
     "type": "ec2", "region": "westus2", "lifecycle": "idle", "name": "vm-analytics-idle",
     "instance": "Standard_E2s_v5", "hourly_rate": 0.126},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-dev/providers/Microsoft.Compute/virtualMachines/vm-legacy-stopped",
     "type": "ec2", "region": "eastus", "lifecycle": "stopped", "name": "vm-legacy-stopped",
     "instance": "Standard_B2ms", "hourly_rate": 0.0464},
    # 2 public IPs
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Network/publicIPAddresses/pip-edge-01",
     "type": "eip", "region": "eastus", "lifecycle": "persistent", "name": "pip-edge-01"},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-archive/providers/Microsoft.Network/publicIPAddresses/pip-orphan-01",
     "type": "eip", "region": "eastus", "lifecycle": "orphaned", "name": "pip-orphan-01"},
    # 2 SQL DBs
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-data/providers/Microsoft.Sql/servers/sql-prod/databases/sales",
     "type": "rds", "region": "eastus", "lifecycle": "persistent", "name": "sql-prod-sales"},
    {"rid": "/subscriptions/sub-001/resourceGroups/rg-archive/providers/Microsoft.Sql/servers/sql-legacy/databases/old-mysql",
     "type": "rds", "region": "eastus", "lifecycle": "idle", "name": "sql-legacy-old-mysql"},
]


def _azure_record(res: dict, day: datetime, rng: random.Random) -> dict:
    """One Consumption-API-style nested record."""
    if res["type"] == "ebs":
        cost = res["size_gb"] * res["rate_per_gb_mo"] / 30.0
        quantity = res["size_gb"] / 30.0
        meter = "Standard SSD Managed Disks"
        consumed = "Microsoft.Compute"
    elif res["type"] == "ec2":
        if res["lifecycle"] == "stopped":
            cost = 0.30  # only disk-attached cost
            quantity = 1
            meter = "Disks Reserved"
            consumed = "Microsoft.Compute"
        else:
            cost = 24 * res["hourly_rate"]
            quantity = 24
            meter = "Compute Hours"
            consumed = "Microsoft.Compute"
    elif res["type"] == "eip":
        cost = 24 * (0.005 if res["lifecycle"] == "orphaned" else 0.0)
        quantity = 24
        meter = "Public IP Addresses"
        consumed = "Microsoft.Network"
    elif res["type"] == "rds":
        cost = 24 * (0.084 if res["lifecycle"] == "idle" else 0.29)
        quantity = 24
        meter = "vCore Hours"
        consumed = "Microsoft.Sql"
    else:
        cost = 0.0
        quantity = 1
        meter = "Other"
        consumed = "Microsoft.Other"

    sub_id = res["rid"].split("/")[2]
    return {
        "id": f"/billing/{rng.randint(10**9, 10**10)}",
        "name": str(rng.randint(10**9, 10**10)),
        "type": "Microsoft.Consumption/usageDetails",
        "properties": {
            "billingAccountId": "billing-acct-001",
            "billingProfileId": "billing-prof-001",
            "subscriptionId": sub_id,
            "subscriptionName": "WK-Subscription-001",
            "billingPeriodStartDate": PERIOD_START.strftime("%Y-%m-%d"),
            "billingPeriodEndDate": PERIOD_END.strftime("%Y-%m-%d"),
            "date": day.strftime("%Y-%m-%d"),
            "product": meter,
            "partNumber": f"AZ-{rng.randint(1000, 9999)}",
            "meterCategory": meter,
            "meterSubCategory": res.get("instance", res["type"]),
            "quantity": round(quantity, 4),
            "effectivePrice": round(cost / quantity if quantity else 0, 6),
            "cost": round(cost, 6),
            "costInBillingCurrency": round(cost, 6),
            "billingCurrency": "USD",
            "unitOfMeasure": "1 Hour" if res["type"] != "ebs" else "1 GB/Month",
            "resourceLocation": res["region"],
            "consumedService": consumed,
            "resourceId": res["rid"],
            "resourceName": res["name"],
            "tags": {"Lifecycle": res["lifecycle"], "Environment": "prod" if "prod" in res["rid"] else "stage"},
        },
    }


def generate_azure_billing(seed: int = 42, output: Path | None = None) -> Path:
    """Write ``samples/azure_billing_sample.json`` and return its path."""
    output = output or SCRIPT_DIR / "azure_billing_sample.json"
    rng = random.Random(seed)

    records: list[dict] = []
    for res in AZURE_RESOURCES:
        days = sorted(rng.sample(range(30), k=4))  # 4 days per resource → ~52 records
        for day_offset in days:
            day = PERIOD_START + timedelta(days=day_offset)
            records.append(_azure_record(res, day, rng))

    rng.shuffle(records)
    with output.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample billing data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=SCRIPT_DIR)
    args = parser.parse_args()

    aws = generate_aws_cur(seed=args.seed, output=args.out_dir / "aws_cur_sample.csv")
    azure = generate_azure_billing(seed=args.seed, output=args.out_dir / "azure_billing_sample.json")

    aws_lines = sum(1 for _ in aws.open()) - 1  # minus header
    with azure.open() as f:
        azure_n = len(json.load(f))
    print(f"✓ {aws.name}    : {aws_lines} line items, {len(AWS_RESOURCES)} resources")
    print(f"✓ {azure.name} : {azure_n} records, {len(AZURE_RESOURCES)} resources")


if __name__ == "__main__":
    main()
