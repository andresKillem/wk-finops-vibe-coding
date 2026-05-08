"""Ingestion layer tests.

Coverage:
- AWS CUR happy path against the real generated sample.
- Azure JSON happy path against the real generated sample.
- Format detection heuristics.
- Edge cases: empty file, malformed CSV, malformed JSON, unsupported extension.
- Idempotency: re-ingest does not duplicate Resource rows.
- Resource-type inference for AWS and Azure.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import select

from finops.db.models import Resource
from finops.db.session import get_session
from finops.ingestion.aws_cur import is_cur_csv
from finops.ingestion.router import ingest_file
from finops.ingestion.utils import (
    infer_resource_type_aws,
    infer_resource_type_azure,
    parse_iso_date,
)


# ─── AWS CUR happy path ──────────────────────────────────────────────────────
def test_aws_cur_sample(samples_dir: Path) -> None:
    summary = ingest_file(samples_dir / "aws_cur_sample.csv")
    assert summary.provider == "aws"
    assert summary.rows_parsed > 100, f"expected ≥100 rows, got {summary.rows_parsed}"
    assert summary.resources_upserted == 17, f"expected 17 distinct AWS resources, got {summary.resources_upserted}"
    assert summary.errors == [], summary.errors
    assert summary.period_start is not None and summary.period_end is not None

    with get_session() as s:
        # Spot-check a few resources are present and typed correctly
        ebs = s.exec(select(Resource).where(Resource.type == "ebs")).all()
        ec2 = s.exec(select(Resource).where(Resource.type == "ec2")).all()
        rds = s.exec(select(Resource).where(Resource.type == "rds")).all()
        elb = s.exec(select(Resource).where(Resource.type == "elb")).all()
        assert len(ebs) == 5
        assert len(ec2) == 4
        assert len(rds) == 2
        assert len(elb) == 2

        # Lifecycle tag plumbed through to attrs
        orphan = s.exec(select(Resource).where(Resource.resource_id == "vol-0a1b2c3d4e5f60004")).first()
        assert orphan is not None
        assert orphan.attrs["tags"].get("Lifecycle") == "orphaned"


# ─── Azure JSON happy path ───────────────────────────────────────────────────
def test_azure_billing_sample(samples_dir: Path) -> None:
    summary = ingest_file(samples_dir / "azure_billing_sample.json")
    assert summary.provider == "azure"
    assert summary.rows_parsed > 0
    assert summary.resources_upserted == 13, f"expected 13 distinct Azure resources, got {summary.resources_upserted}"
    assert summary.errors == []

    with get_session() as s:
        all_resources = s.exec(select(Resource)).all()
        assert all(r.cloud_provider == "azure" for r in all_resources)


# ─── Format detection ────────────────────────────────────────────────────────
def test_is_cur_csv_positive() -> None:
    assert is_cur_csv(["lineItem/UsageStartDate", "lineItem/ResourceId", "other"])


def test_is_cur_csv_negative() -> None:
    assert not is_cur_csv(["foo", "bar", "baz"])
    assert not is_cur_csv([])


# ─── Edge cases ──────────────────────────────────────────────────────────────
def test_empty_csv(tmp_path: Path) -> None:
    f = tmp_path / "empty.csv"
    f.write_text("")
    summary = ingest_file(f)
    assert summary.rows_parsed == 0
    assert summary.errors  # should report empty


def test_unrecognized_csv(tmp_path: Path) -> None:
    f = tmp_path / "bad.csv"
    f.write_text("name,size,status\nfoo,10,active\nbar,20,idle\n")
    summary = ingest_file(f)
    assert summary.rows_parsed == 0
    assert any("unrecognized" in e.lower() or "no lineItem" in e for e in summary.errors)


def test_malformed_json(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    summary = ingest_file(f)
    assert summary.rows_parsed == 0
    assert any("invalid json" in e.lower() for e in summary.errors)


def test_empty_json_list(tmp_path: Path) -> None:
    f = tmp_path / "empty.json"
    f.write_text("[]")
    summary = ingest_file(f)
    assert summary.rows_parsed == 0
    # Empty list is not an error per se
    assert summary.provider == "azure"


def test_unsupported_extension(tmp_path: Path) -> None:
    f = tmp_path / "weird.xyz"
    f.write_text("hello")
    summary = ingest_file(f)
    assert summary.errors


def test_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        ingest_file("/nonexistent/path/to/file.csv")


def test_csv_encoding_utf8_bom(tmp_path: Path) -> None:
    """UTF-8 with BOM should still parse cleanly."""
    f = tmp_path / "bom.csv"
    content = (
        "lineItem/UsageStartDate,lineItem/ResourceId,lineItem/UnblendedCost\n"
        "2026-04-01T00:00:00Z,vol-test,1.50\n"
    )
    f.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    summary = ingest_file(f)
    assert summary.rows_parsed == 1
    assert summary.errors == []


# ─── Idempotency ─────────────────────────────────────────────────────────────
def test_resource_idempotent_upsert(samples_dir: Path) -> None:
    """Re-ingesting the same file MUST NOT duplicate Resource rows."""
    s1 = ingest_file(samples_dir / "aws_cur_sample.csv")
    s2 = ingest_file(samples_dir / "aws_cur_sample.csv")
    assert s1.resources_upserted == s2.resources_upserted == 17
    with get_session() as s:
        count = len(s.exec(select(Resource)).all())
    assert count == 17


# ─── Type inference ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "rid,product,expected",
    [
        ("vol-0abc", "Amazon EC2", "ebs"),
        ("i-0abc", "Amazon EC2", "ec2"),
        ("nat-0abc", "", "nat"),
        ("eipalloc-0abc", "", "eip"),
        ("54.123.45.6", "", "eip"),
        ("arn:aws:rds:us-east-1:1:db:foo", "Amazon RDS", "rds"),
        ("arn:aws:elasticloadbalancing:us-east-1:1:loadbalancer/app/foo/bar", "", "elb"),
        ("arn:aws:s3:::my-bucket", "Amazon S3", "s3"),
        ("something-weird", "", "other"),
    ],
)
def test_infer_resource_type_aws(rid: str, product: str, expected: str) -> None:
    assert infer_resource_type_aws(rid, product) == expected


@pytest.mark.parametrize(
    "rid,expected",
    [
        ("/subscriptions/x/resourceGroups/y/providers/Microsoft.Compute/disks/d1", "ebs"),
        ("/subscriptions/x/resourceGroups/y/providers/Microsoft.Compute/virtualMachines/vm1", "ec2"),
        ("/subscriptions/x/resourceGroups/y/providers/Microsoft.Network/publicIPAddresses/pip1", "eip"),
        ("/subscriptions/x/resourceGroups/y/providers/Microsoft.Network/loadBalancers/lb1", "elb"),
        ("/subscriptions/x/resourceGroups/y/providers/Microsoft.Network/natGateways/nat1", "nat"),
        ("/subscriptions/x/resourceGroups/y/providers/Microsoft.Sql/servers/srv1/databases/db1", "rds"),
        ("/subscriptions/x/resourceGroups/y/providers/Microsoft.Storage/storageAccounts/sa1", "s3"),
        ("something-not-a-path", "other"),
    ],
)
def test_infer_resource_type_azure(rid: str, expected: str) -> None:
    assert infer_resource_type_azure(rid) == expected


# ─── parse_iso_date ──────────────────────────────────────────────────────────
def test_parse_iso_date_variants() -> None:
    assert parse_iso_date("2026-04-01T00:00:00Z") is not None
    assert parse_iso_date("2026-04-01") is not None
    assert parse_iso_date("04/01/2026") is not None
    assert parse_iso_date("") is None
    assert parse_iso_date(None) is None
    assert parse_iso_date("not a date") is None
