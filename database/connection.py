"""
database/connection.py — SQLAlchemy engine and session factory.

The SQLite database is stored at `veerexa_leads.db` in the project root.
All modules import `get_session` and use it as a context manager.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ── Database path ─────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = _PROJECT_ROOT / "veerexa_leads.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for Streamlit
    echo=False,
)

# ── Session factory ────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Session:  # type: ignore[misc]
    """Context manager that yields a database session and handles commit/rollback."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_size_mb() -> float:
    """Return database file size in megabytes."""
    if DB_PATH.exists():
        return round(DB_PATH.stat().st_size / (1024 * 1024), 2)
    return 0.0
