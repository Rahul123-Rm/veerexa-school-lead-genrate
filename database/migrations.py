"""
database/migrations.py — Create all tables on first run.

Call `initialise_database()` at application startup to ensure
all tables exist. This is idempotent — it uses CREATE TABLE IF NOT EXISTS
via SQLAlchemy's metadata.create_all().
"""

from __future__ import annotations

from database.connection import engine
from models.school import Base


def initialise_database() -> None:
    """Create all ORM tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)
