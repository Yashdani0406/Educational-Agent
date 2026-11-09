"""Saved chat threads (the messages themselves live in the ADK session store)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from eduagent.db.database import Database


WHAT_IT_DOES = (
    "Keeps the list of saved chat threads per course so conversations can be reopened."
)

@dataclass(frozen=True)
class Thread:
    id: str
    course_id: int | None
    title: str
    last_agent: str | None
    updated_at: str


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _thread(r) -> Thread:
    return Thread(r["id"], r["course_id"], r["title"], r["last_agent"], r["updated_at"])


class ThreadsRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, course_id: int | None, title: str = "New chat") -> Thread:
        thread = Thread(uuid.uuid4().hex, course_id, title, None, _now())
        with self._db.connect() as conn:
            conn.execute(
                "INSERT INTO threads(id, course_id, title, last_agent, created_at, updated_at) "
                "VALUES (?, ?, ?, NULL, ?, ?)",
                (thread.id, course_id, title, thread.updated_at, thread.updated_at),
            )
        return thread

    def get(self, thread_id: str) -> Thread:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if row is None:
            raise KeyError(thread_id)
        return _thread(row)

    def list(self, course_id: int | None) -> list[Thread]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM threads WHERE course_id IS ? ORDER BY updated_at DESC, rowid DESC",
                (course_id,),
            ).fetchall()
        return [_thread(r) for r in rows]

    def rename(self, thread_id: str, title: str) -> None:
        with self._db.connect() as conn:
            conn.execute("UPDATE threads SET title = ? WHERE id = ?", (title, thread_id))

    def touch(self, thread_id: str, last_agent: str | None) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE threads SET last_agent = ?, updated_at = ? WHERE id = ?",
                (last_agent, _now(), thread_id),
            )
