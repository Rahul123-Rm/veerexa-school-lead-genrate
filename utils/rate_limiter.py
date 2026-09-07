"""
rate_limiter.py — Daily API request counter backed by SQLite.

Tracks how many Places API requests have been made today and enforces
a configurable daily limit to protect billing.
"""

from __future__ import annotations

import os
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


class RateLimiter:
    """Manages daily API request counts stored in the api_usage table."""

    def __init__(self, session: Session):
        self.session = session
        self._daily_limit: int = int(os.getenv("DAILY_REQUEST_LIMIT", "500"))

    @property
    def daily_limit(self) -> int:
        return self._daily_limit

    def _today_str(self) -> str:
        return date.today().isoformat()

    def get_used_today(self) -> int:
        """Return number of API requests already made today."""
        today = self._today_str()
        row = self.session.execute(
            text("SELECT request_count FROM api_usage WHERE usage_date = :d"),
            {"d": today},
        ).fetchone()
        return row[0] if row else 0

    def remaining_today(self) -> int:
        used = self.get_used_today()
        return max(0, self._daily_limit - used)

    def can_make_request(self, count: int = 1) -> bool:
        return self.remaining_today() >= count

    def record_requests(self, count: int = 1) -> None:
        """Increment today's request count by `count`."""
        today = self._today_str()
        existing = self.session.execute(
            text("SELECT id FROM api_usage WHERE usage_date = :d"),
            {"d": today},
        ).fetchone()

        if existing:
            self.session.execute(
                text(
                    "UPDATE api_usage SET request_count = request_count + :c, "
                    "last_updated = :ts WHERE usage_date = :d"
                ),
                {"c": count, "ts": datetime.utcnow().isoformat(), "d": today},
            )
        else:
            self.session.execute(
                text(
                    "INSERT INTO api_usage (usage_date, request_count, last_updated) "
                    "VALUES (:d, :c, :ts)"
                ),
                {"d": today, "c": count, "ts": datetime.utcnow().isoformat()},
            )
        self.session.commit()

    def get_usage_history(self, days: int = 7) -> list[dict]:
        """Return usage for the last N days."""
        rows = self.session.execute(
            text(
                "SELECT usage_date, request_count FROM api_usage "
                "ORDER BY usage_date DESC LIMIT :n"
            ),
            {"n": days},
        ).fetchall()
        return [{"date": r[0], "count": r[1]} for r in rows]
