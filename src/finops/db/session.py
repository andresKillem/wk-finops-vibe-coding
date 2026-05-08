"""Database session management.

Single source of truth for the SQLAlchemy engine and session lifecycle.
Every other module imports ``engine``, ``get_session``, ``init_db`` from here —
never instantiates its own engine. This keeps tests' DB-override trivial: set
``DATABASE_URL`` in env before importing finops, and the whole tree honours it.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from finops.config import settings


def _ensure_data_dir() -> None:
    """Create ./data/ if missing — SQLite won't create parents on its own."""
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_data_dir()

engine = create_engine(
    settings.database_url,
    echo=False,  # flip to True for SQL debugging
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def init_db() -> None:
    """Create all tables. Idempotent — safe to call repeatedly."""
    # Import models so SQLModel.metadata sees their table definitions.
    from finops.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def reset_db() -> None:
    """Drop all tables and recreate. DESTRUCTIVE — wipes everything.

    Used by tests (per-test isolation) and by ``finops ingest --fresh``.
    Production code should not call this.
    """
    from finops.db import models  # noqa: F401

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a Session; commit on success, rollback on error, always close.

    Usage:
        with get_session() as s:
            s.add(record)
            # commit happens automatically on context exit
    """
    # expire_on_commit=False: instances retain loaded attribute values after
    # commit, which is required so callers can iterate / serialise objects
    # *outside* the with-block (e.g., FastAPI route returning Findings).
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
