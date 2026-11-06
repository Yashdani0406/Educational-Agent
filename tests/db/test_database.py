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


def _version(db):
    with db.connect() as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def test_failed_migration_rolls_back(db, monkeypatch):
    monkeypatch.setattr(
        "eduagent.db.database._load_migrations",
        lambda: [(1, "CREATE TABLE a (x);"), (2, "CREATE TABLE b (x); THIS IS NOT SQL;")],
    )
    with pytest.raises(sqlite3.Error):
        db.migrate()
    assert _version(db) == 1
    with db.connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "a" in tables and "b" not in tables


def test_migrations_at_or_below_version_skipped(db, monkeypatch):
    monkeypatch.setattr("eduagent.db.database._load_migrations", lambda: [(1, "CREATE TABLE a (x);")])
    assert db.migrate() == 1
    monkeypatch.setattr(
        "eduagent.db.database._load_migrations",
        lambda: [(1, "THIS WOULD FAIL;"), (2, "CREATE TABLE b (x);")],
    )
    assert db.migrate() == 2
