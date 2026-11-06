"""Courses, modules and topics. Topics are course-level and linked to modules."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from eduagent.db.database import Database


@dataclass(frozen=True)
class Course:
    id: int
    name: str


@dataclass(frozen=True)
class TopicNode:
    id: int
    name: str
    mastery: float | None


@dataclass(frozen=True)
class ModuleNode:
    id: int
    name: str
    topics: list[TopicNode]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class CoursesRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_course(self, name: str) -> Course:
        name = name.strip()
        if not name:
            raise ValueError("course name must not be blank")
        with self._db.connect() as conn:
            try:
                cur = conn.execute("INSERT INTO courses(name, created_at) VALUES (?, ?)", (name, _now()))
            except sqlite3.IntegrityError as e:
                raise ValueError(f"course already exists: {name}") from e
            return Course(cur.lastrowid, name)

    def list_courses(self) -> list[Course]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT id, name FROM courses ORDER BY id").fetchall()
        return [Course(r["id"], r["name"]) for r in rows]

    def _get_or_create(self, table: str, course_id: int, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("name must not be blank")
        with self._db.connect() as conn:
            row = conn.execute(
                f"SELECT id FROM {table} WHERE course_id = ? AND name = ?", (course_id, name)
            ).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                f"INSERT INTO {table}(course_id, name, created_at) VALUES (?, ?, ?)",
                (course_id, name, _now()),
            )
            return cur.lastrowid

    def add_module(self, course_id: int, name: str) -> int:
        return self._get_or_create("modules", course_id, name)

    def add_topic(self, course_id: int, name: str) -> int:
        return self._get_or_create("topics", course_id, name)

    def link_topic(self, module_id: int, topic_id: int) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO module_topics(module_id, topic_id) VALUES (?, ?)",
                (module_id, topic_id),
            )

    def course_map(self, course_id: int) -> list[ModuleNode]:
        with self._db.connect() as conn:
            modules = conn.execute(
                "SELECT id, name FROM modules WHERE course_id = ? ORDER BY id", (course_id,)
            ).fetchall()
            result = []
            for m in modules:
                topics = conn.execute(
                    "SELECT t.id, t.name FROM topics t JOIN module_topics mt ON mt.topic_id = t.id "
                    "WHERE mt.module_id = ? ORDER BY t.name COLLATE NOCASE, t.id",
                    (m["id"],),
                ).fetchall()
                result.append(
                    ModuleNode(m["id"], m["name"], [TopicNode(t["id"], t["name"], None) for t in topics])
                )
        return result
