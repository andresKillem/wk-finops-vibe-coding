"""Ingestion-shared utilities.

Imported by both ``aws_cur`` and ``azure_billing`` parsers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class IngestSummary:
    """The shape every parser returns. Renderable as both rich-string and dict."""

    file: str
    provider: str = "unknown"
    rows_parsed: int = 0
    skipped: int = 0
    resources_upserted: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    errors: list[str] = field(default_factory=list)

    def __rich_console__(self, console, options):  # rich protocol
        from rich.panel import Panel
        from rich.table import Table

        t = Table(show_header=False, expand=False, box=None)
        t.add_column(style="bold cyan")
        t.add_column()
        t.add_row("file", self.file)
        t.add_row("provider", self.provider)
        t.add_row("rows parsed", f"[green]{self.rows_parsed}[/]")
        t.add_row("rows skipped", f"[yellow]{self.skipped}[/]" if self.skipped else "0")
        t.add_row("resources upserted", f"[green]{self.resources_upserted}[/]")
        if self.period_start and self.period_end:
            t.add_row("date range", f"{self.period_start.date()} → {self.period_end.date()}")
        if self.errors:
            errs = "\n".join(f"• {e}" for e in self.errors[:5])
            t.add_row("errors", f"[red]{len(self.errors)}[/]\n{errs}")
        else:
            t.add_row("errors", "0")
        yield Panel(t, title="Ingest Summary", border_style="cyan")

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "provider": self.provider,
            "rows_parsed": self.rows_parsed,
            "skipped": self.skipped,
            "resources_upserted": self.resources_upserted,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "errors": self.errors,
        }


_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
)


def parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    """Parse a wide variety of date strings into a **naive UTC** datetime.

    SQLite does not preserve timezone info on roundtrip, so we normalise to
    naive-UTC throughout the system to keep comparisons consistent. All times
    are conceptually UTC — the absent tzinfo is the convention, not an error.

    Returns None for empty / unparseable inputs.
    """
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    # Fallback: Python 3.11 fromisoformat handles many shapes incl. trailing Z.
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def infer_resource_type_aws(resource_id: str, product: str = "", usage_type: str = "") -> str:
    """Infer resource type from AWS resource ID + supplemental hints.

    Returns one of: ebs|ec2|eip|nat|rds|elb|s3|eni|snapshot|other
    """
    rid = (resource_id or "").lower()
    p = (product or "").lower()
    u = (usage_type or "").lower()

    # ID-prefix matches (most reliable)
    if rid.startswith("vol-"):
        return "ebs"
    if rid.startswith("i-"):
        return "ec2"
    if rid.startswith("nat-"):
        return "nat"
    if rid.startswith("eipalloc-"):
        return "eip"
    if rid.startswith("eni-"):
        return "eni"
    if rid.startswith("snap-"):
        return "snapshot"

    # ARN matches
    if "elasticloadbalancing" in rid or rid.startswith("arn:aws:elasticloadbalancing"):
        return "elb"
    if rid.startswith("arn:aws:rds"):
        return "rds"
    if rid.startswith("arn:aws:s3"):
        return "s3"

    # IPv4 literal — Elastic IP billed by IP address
    parts = resource_id.split(".") if resource_id else []
    if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
        return "eip"

    # Product / usage_type fallbacks (least reliable)
    if "natgateway" in u:
        return "nat"
    if "loadbalancer" in u:
        return "elb"
    if "rds" in p or "database" in u:
        return "rds"
    if "s3" in p or "storage" in u:
        return "s3"
    if "ec2" in p and ("ebs" in u or "volume" in u):
        return "ebs"
    if "ec2" in p:
        return "ec2"

    return "other"


def infer_resource_type_azure(resource_id: str) -> str:
    """Infer resource type from Azure resource ID path.

    Returns same vocabulary as the AWS inference for cross-cloud rules to share rules.
    """
    rid = (resource_id or "").lower()
    if "/disks/" in rid or "/snapshots/" in rid:
        return "ebs"
    if "/virtualmachines/" in rid or "/virtualmachinescalesets/" in rid:
        return "ec2"
    if "/publicipaddresses/" in rid:
        return "eip"
    if "/loadbalancers/" in rid or "/applicationgateways/" in rid:
        return "elb"
    if "/natgateways/" in rid:
        return "nat"
    if "microsoft.sql" in rid or "/databaseaccounts/" in rid or "/servers/" in rid:
        return "rds"
    if "/storageaccounts/" in rid:
        return "s3"
    return "other"
