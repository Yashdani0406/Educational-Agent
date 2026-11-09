import logging
from datetime import UTC, datetime

import pytest

from eduagent.db.database import Database
from eduagent.models.quota import QuotaTracker


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class Clock:
    def __init__(self, now: str):
        self.now = utc(now)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "study.db")
    d.migrate()
    return d


def make(db, limit, now="2026-11-06T12:00Z"):
    clock = Clock(now)
    return QuotaTracker(db, limit, clock), clock


def test_remaining_counts_down(db):
    q, _ = make(db, 3)
    q.record_request()
    q.record_request()
    assert q.remaining() == 1


def test_never_negative(db):
    q, _ = make(db, 1)
    for _ in range(3):
        q.record_request()
    assert q.remaining() == 0
    assert q.is_available() is False


def test_mark_exhausted(db):
    q, _ = make(db, 100)
    q.mark_exhausted()
    assert q.remaining() == 0
    assert q.is_available() is False


def test_resets_at_pacific_midnight(db):
    q, clock = make(db, 5, "2026-11-06T07:59Z")
    q.record_request()
    q.mark_exhausted()
    assert q.remaining() == 0
    clock.now = utc("2026-11-06T08:01Z")
    assert q.remaining() == 5
    assert q.is_available() is True


def test_resets_at_value(db):
    q, _ = make(db, 5)
    assert q.resets_at() == datetime(2026, 11, 7, 8, 0, tzinfo=UTC)


def test_resets_at_dst(db):
    q, _ = make(db, 5, "2026-03-08T12:00Z")
    assert q.resets_at() == datetime(2026, 3, 9, 7, 0, tzinfo=UTC)


def test_naive_clock_rejected(db):
    q = QuotaTracker(db, 5, lambda: datetime(2026, 11, 6, 12, 0))
    with pytest.raises(ValueError):
        q.record_request()


def test_zero_limit(db):
    q, _ = make(db, 0)
    assert q.remaining() == 0
    assert q.is_available() is False


def test_negative_limit_rejected(db):
    with pytest.raises(ValueError):
        QuotaTracker(db, -1)


def test_mark_exhausted_logs_once(db, caplog):
    q, _ = make(db, 5)
    with caplog.at_level(logging.WARNING, logger="eduagent.models.quota"):
        q.mark_exhausted()
        q.mark_exhausted()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "2026-11-07" in warnings[0].getMessage()
