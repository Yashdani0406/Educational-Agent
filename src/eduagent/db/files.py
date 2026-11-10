"""Uploaded files. One row per file also serves as its ingestion job: queue order, status, checkpoints."""

import json
import sqlite3
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from eduagent.db.database import Database

WHAT_IT_DOES = (
    "Keeps the list of uploaded files, their place in the reading queue and their progress, so reading can resume after a restart."
)

Origin = Literal["module", "reference"]
FileKind = Literal["pdf", "pptx", "docx", "txt", "md", "paste", "web"]
FileStatus = Literal["queued", "reading", "chunking", "embedding", "tagging", "done", "failed", "skipped"]
Layout = Literal["slides", "document", "docx", "text", "markdown", "web"]
TopicsState = Literal["none", "pending", "reviewed", "failed"]  # none = book / not tagged yet
ACTIVE = ("queued", "reading", "chunking", "embedding", "tagging")
_ACTIVE_SQL = ", ".join(f"'{s}'" for s in ACTIVE)


@dataclass(frozen=True)
class FileRecord:
    id: int
    course_id: int
    module_id: int | None
    origin: Origin
    kind: FileKind
    title: str
    source_name: str
    stored_path: str | None
    content_hash: str | None
    layout: Layout | None
    status: FileStatus
    error: str | None
    queue_pos: int
    pages_total: int | None
    pieces_total: int | None
    pieces_done: int
    uploaded_at: str
    uploaded_week: int
    topics_state: TopicsState
    replaces_file_id: int | None
    trace_id: str | None


@dataclass(frozen=True)
class Piece:
    file_id: int
    piece: int
    first_page: int | None
    last_page: int | None
    done: bool


_COLUMNS = (
    "id, course_id, module_id, origin, kind, title, source_name, stored_path, content_hash, layout, "
    "status, error, queue_pos, pages_total, pieces_total, pieces_done, uploaded_at, uploaded_week, "
    "topics_state, replaces_file_id, trace_id"
)
_NEXT_POS = "(SELECT COALESCE(MAX(queue_pos), 0) + 1 FROM files)"


def _record(row: sqlite3.Row) -> FileRecord:
    return FileRecord(**dict(row))


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


class FilesRepo:
    def __init__(self, db: Database, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._db = db
        self._clock = clock

    def add(
        self,
        course_id: int,
        module_id: int | None,
        origin: Origin,
        kind: FileKind,
        title: str,
        source_name: str,
        stored_path: str | None,
        content_hash: str | None,
        replaces_file_id: int | None = None,
    ) -> FileRecord:
        now = self._clock()
        upload_monday = _monday(now.astimezone().date())  # the student's local calendar date
        with self._db.connect() as conn:
            # Set once: the first upload fixes week 1 for the course, later deletes never move it.
            conn.execute(
                "UPDATE courses SET week1_monday = ? WHERE id = ? AND week1_monday IS NULL",
                (upload_monday.isoformat(), course_id),
            )
            row = conn.execute("SELECT week1_monday FROM courses WHERE id = ?", (course_id,)).fetchone()
            if row is None:
                raise KeyError(course_id)
            week = (upload_monday - date.fromisoformat(row["week1_monday"])).days // 7 + 1
            cur = conn.execute(
                "INSERT INTO files(course_id, module_id, origin, kind, title, source_name, stored_path, "
                "content_hash, status, queue_pos, uploaded_at, uploaded_week, replaces_file_id) "
                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', {_NEXT_POS}, ?, ?, ?)",
                (course_id, module_id, origin, kind, title, source_name, stored_path, content_hash,
                 now.astimezone(UTC).isoformat(), week, replaces_file_id),
            )
            return self._get(conn, cur.lastrowid)

    @staticmethod
    def _get(conn: sqlite3.Connection, file_id: int) -> FileRecord:
        row = conn.execute(f"SELECT {_COLUMNS} FROM files WHERE id = ?", (file_id,)).fetchone()
        if row is None:
            raise KeyError(file_id)
        return _record(row)

    def get(self, file_id: int) -> FileRecord:
        with self._db.connect() as conn:
            return self._get(conn, file_id)

    def list_course(self, course_id: int) -> list[FileRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM files WHERE course_id = ? ORDER BY queue_pos", (course_id,)
            ).fetchall()
        return [_record(r) for r in rows]

    def _one(self, where: str, params: tuple) -> FileRecord | None:
        with self._db.connect() as conn:
            row = conn.execute(f"SELECT {_COLUMNS} FROM files WHERE {where} LIMIT 1", params).fetchone()
        return _record(row) if row else None

    def find_by_hash(self, course_id: int, content_hash: str) -> FileRecord | None:
        return self._one("course_id = ? AND content_hash = ?", (course_id, content_hash))

    def find_same_source(
        self, course_id: int, module_id: int | None, origin: Origin, source_name: str
    ) -> FileRecord | None:
        return self._one(
            "course_id = ? AND module_id IS ? AND origin = ? AND source_name = ? COLLATE NOCASE",
            (course_id, module_id, origin, source_name),
        )

    def next_active(self, exclude: Collection[int] = ()) -> FileRecord | None:
        marks = ", ".join("?" for _ in exclude)
        skip = f" AND id NOT IN ({marks})" if exclude else ""
        with self._db.connect() as conn:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM files WHERE status IN ({_ACTIVE_SQL}){skip} "
                "ORDER BY queue_pos LIMIT 1",
                tuple(exclude),
            ).fetchone()
        return _record(row) if row else None

    def queue_position(self, file_id: int) -> int | None:
        with self._db.connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS n FROM files WHERE status IN ({_ACTIVE_SQL}) AND queue_pos <= "
                f"(SELECT queue_pos FROM files WHERE id = ? AND status IN ({_ACTIVE_SQL}))",
                (file_id,),
            ).fetchone()
        return row["n"] or None

    def _update(self, file_id: int, assignments: str, params: tuple) -> None:
        with self._db.connect() as conn:
            cur = conn.execute(f"UPDATE files SET {assignments} WHERE id = ?", (*params, file_id))
            if cur.rowcount == 0:
                raise KeyError(file_id)

    def set_status(self, file_id: int, status: FileStatus, error: str | None = None) -> None:
        self._update(file_id, "status = ?, error = ?", (status, error))

    def set_source(
        self, file_id: int, *, kind: FileKind, title: str, stored_path: str | None, content_hash: str | None
    ) -> None:
        self._update(
            file_id, "kind = ?, title = ?, stored_path = ?, content_hash = ?",
            (kind, title, stored_path, content_hash),
        )

    def set_layout(self, file_id: int, layout: Layout, pages_total: int | None) -> None:
        self._update(file_id, "layout = ?, pages_total = ?", (layout, pages_total))

    def set_module(self, file_id: int, module_id: int | None) -> None:
        self._update(file_id, "module_id = ?", (module_id,))

    def set_topics_state(self, file_id: int, state: TopicsState) -> None:
        self._update(file_id, "topics_state = ?", (state,))

    def set_trace(self, file_id: int, trace_id: str | None) -> None:
        self._update(file_id, "trace_id = ?", (trace_id,))

    def plan_pieces(self, file_id: int, ranges: list[tuple[int | None, int | None]]) -> None:
        with self._db.connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO file_pieces(file_id, piece, first_page, last_page) VALUES (?, ?, ?, ?)",
                [(file_id, i, first, last) for i, (first, last) in enumerate(ranges)],
            )
            conn.execute("UPDATE files SET pieces_total = ? WHERE id = ?", (len(ranges), file_id))

    def pieces(self, file_id: int) -> list[Piece]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT file_id, piece, first_page, last_page, done FROM file_pieces "
                "WHERE file_id = ? ORDER BY piece",
                (file_id,),
            ).fetchall()
        return [Piece(r["file_id"], r["piece"], r["first_page"], r["last_page"], bool(r["done"])) for r in rows]

    def finish_piece(self, file_id: int, piece: int, carry_headings: list[str]) -> None:
        with self._db.connect() as conn:
            cur = conn.execute(
                "UPDATE file_pieces SET done = 1, carry_json = ? WHERE file_id = ? AND piece = ?",
                (json.dumps(carry_headings), file_id, piece),
            )
            if cur.rowcount == 0:
                raise KeyError((file_id, piece))
            # Counted, not incremented, so finishing a piece twice stays correct.
            conn.execute(
                "UPDATE files SET pieces_done = (SELECT COUNT(*) FROM file_pieces WHERE file_id = ? AND done = 1) "
                "WHERE id = ?",
                (file_id, file_id),
            )

    def carry_headings(self, file_id: int, piece: int) -> list[str]:
        if piece <= 0:
            return []
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT carry_json FROM file_pieces WHERE file_id = ? AND piece = ?", (file_id, piece - 1)
            ).fetchone()
        return json.loads(row["carry_json"]) if row and row["carry_json"] else []

    def requeue(self, file_id: int) -> None:
        self._update(file_id, f"status = 'queued', error = NULL, queue_pos = {_NEXT_POS}", ())

    def delete(self, file_id: int) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
