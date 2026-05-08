"""Shared pytest fixtures.

CRITICAL: this file points the database at a temp location BEFORE any
``finops`` import happens, so tests never touch the project's ``data/finops.db``.

Tests in this project are categorised:
- unit (default) — fast, in-memory or temp-file SQLite, no external services.
- integration — may spin up servers or write to real files.
- llm — requires ANTHROPIC_API_KEY; runs real Anthropic calls.

Run subsets:
    uv run pytest                                     # all
    uv run pytest -m "not integration and not llm"   # fast only
    uv run pytest -m llm                              # paid tests
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# ─── Set test DB BEFORE any finops import ──────────────────────────────────────
_TEST_DIR = Path(tempfile.mkdtemp(prefix="finops_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'test.db'}"
# ───────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def samples_dir(project_root: Path) -> Path:
    return project_root / "samples"


@pytest.fixture(autouse=True)
def fresh_db():
    """Wipe the test DB before every test for isolation."""
    from finops.db.session import reset_db

    reset_db()
    yield
