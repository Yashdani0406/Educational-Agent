"""Local counter for the Gemini free-tier daily request quota."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from eduagent.db.database import Database

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Counts today's Gemini free-tier requests so the app can show how many are left "
    "and switch to the local model when the daily quota is gone."
)

QUOTA_TZ = ZoneInfo("America/Los_Angeles")


class QuotaTracker:
    def __init__(
        self,
        db: Database,
        daily_limit: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        if daily_limit < 0:
            raise ValueError("daily_limit must be >= 0")
        self._db = db
        self._limit = daily_limit
        self._clock = clock

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now

    def _today(self) -> str:
        return self._now().astimezone(QUOTA_TZ).date().isoformat()

    def record_request(self) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "INSERT INTO gemini_usage(day, requests) VALUES (?, 1) "
                "ON CONFLICT(day) DO UPDATE SET requests = requests + 1",
                (self._today(),),
            )

    def mark_exhausted(self) -> None:
        day = self._today()
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT exhausted FROM gemini_usage WHERE day = ?", (day,)
            ).fetchone()
            already = bool(row and row["exhausted"])
            conn.execute(
                "INSERT INTO gemini_usage(day, requests, exhausted) VALUES (?, 0, 1) "
                "ON CONFLICT(day) DO UPDATE SET exhausted = 1",
                (day,),
            )
        if not already:
            log.warning(
                "Gemini quota exhausted; resets at %s", self.resets_at().isoformat()
            )

    def remaining(self) -> int:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT requests, exhausted FROM gemini_usage WHERE day = ?",
                (self._today(),),
            ).fetchone()
        if row is None:
            return self._limit
        if row["exhausted"]:
            return 0
        return max(0, self._limit - row["requests"])

    def is_available(self) -> bool:
        return self.remaining() > 0

    def resets_at(self) -> datetime:
        tomorrow = self._now().astimezone(QUOTA_TZ).date() + timedelta(days=1)
        return datetime.combine(tomorrow, time(0), tzinfo=QUOTA_TZ).astimezone(UTC)
