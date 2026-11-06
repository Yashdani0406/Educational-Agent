import sqlite3

import pytest

from eduagent.db.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "sub" / "study.db")


def test_migrate_fresh_and_idempotent(db):
    assert db.migrate() == 1
    assert db.migrate() == 1


def test_wal_and_foreign_keys(db):
    db.migrate()
    with db.connect() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO modules(course_id, name, created_at) VALUES (999, 'x', 'now')")


def test_rollback_on_error(db):
    db.migrate()
    with pytest.raises(RuntimeError):
        with db.connect() as conn:
            conn.execute("INSERT INTO courses(name, created_at) VALUES ('A', 'now')")
            raise RuntimeError
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0


def test_connection_closed_on_exit(db):
    with db.connect() as conn:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
