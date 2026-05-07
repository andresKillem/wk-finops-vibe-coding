"""Shared pytest fixtures.

Tests in this project are categorized:
- unit (default) — fast, no external dependencies, in-memory or temp-file SQLite.
- integration — may spin up servers or write to real files.
- llm — requires ANTHROPIC_API_KEY; runs real Anthropic calls.

Run subsets:
    uv run pytest                              # all
    uv run pytest -m "not integration and not llm"   # fast only
    uv run pytest -m llm                       # paid tests
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def samples_dir(project_root: Path) -> Path:
    return project_root / "samples"


@pytest.fixture
def temp_db_url(tmp_path: Path) -> str:
    """Per-test SQLite DB at a tmp_path so tests don't pollute each other."""
    return f"sqlite:///{tmp_path / 'test.db'}"
