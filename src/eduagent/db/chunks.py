"""Chunk text, locations and topic links, plus the SQLite FTS5 keyword index kept in step with them."""

import logging
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from eduagent.db.database import Database
from eduagent.db.files import Origin

WHAT_IT_DOES = (
    "Stores the text of every study chunk with where it came from, finds chunks by keyword, and remembers which chunks were removed."
)

log = logging.getLogger(__name__)

LocKind = Literal["slide", "page", "line", "heading"]
ChunkKind = Literal["source", "web"]

_COLUMNS = "id, file_id, course_id, module_id, origin, kind, seq, text, heading_path, loc_kind, loc_start, loc_end, word_count"
_C_COLUMNS = ", ".join(f"c.{name.strip()}" for name in _COLUMNS.split(","))
_BATCH = 500  # stays far below SQLite's bound-parameter limit
_TOKEN = re.compile(r"\w+")  # what the FTS tokenizer treats as a word: letters, digits and '_'


@dataclass(frozen=True)
class StoredChunk:
    id: str
    file_id: int
    course_id: int
    module_id: int | None
    origin: Origin
    kind: ChunkKind
    seq: int
    text: str
    heading_path: str
    loc_kind: LocKind
    loc_start: int | None
    loc_end: int | None
    word_count: int


@dataclass(frozen=True)
class RemovedChunk:
    chunk_id: str
    file_id: int
    file_title: str
    reason: str
    removed_at: str


@dataclass(frozen=True)
class KeywordFilters:
    module_id: int | None = None
    topic_id: int | None = None
    file_id: int | None = None
    kind: ChunkKind | None = None


def chunk_id(file_id: int, piece: int, n: int) -> str:
    return f"f{file_id}-{piece:04d}-{n:03d}"


def fts_query(text: str) -> str | None:
    """Word tokens only, each quoted (so FTS operators in user text are inert) and OR-ed."""
    tokens = dict.fromkeys(_TOKEN.findall(text))
    return " OR ".join(f'"{t}"' for t in tokens) or None


def _chunk(row: sqlite3.Row) -> StoredChunk:
    values = dict(row)
    values["heading_path"] = values["heading_path"] or ""
    return StoredChunk(**values)


class ChunksRepo:
    def __init__(self, db: Database, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._db = db
        self._clock = clock

    def upsert(self, chunks: list[StoredChunk]) -> None:
        """Chunk rows and their FTS rows in one transaction; the FTS rowid is the chunk's explicit integer key (rid)."""
        with self._db.connect() as conn:
            for c in chunks:
                # ON CONFLICT DO UPDATE keeps rid, so the FTS row below stays aligned.
                cur = conn.execute(
                    "INSERT INTO chunks(id, file_id, course_id, module_id, origin, kind, seq, text, heading_path, "
                    "loc_kind, loc_start, loc_end, word_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET file_id=excluded.file_id, course_id=excluded.course_id, "
                    "module_id=excluded.module_id, origin=excluded.origin, kind=excluded.kind, seq=excluded.seq, "
                    "text=excluded.text, heading_path=excluded.heading_path, loc_kind=excluded.loc_kind, "
                    "loc_start=excluded.loc_start, loc_end=excluded.loc_end, word_count=excluded.word_count "
                    "RETURNING rid",
                    (c.id, c.file_id, c.course_id, c.module_id, c.origin, c.kind, c.seq, c.text, c.heading_path,
                     c.loc_kind, c.loc_start, c.loc_end, c.word_count),
                )
                rowid = cur.fetchone()[0]
                conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (rowid,))
                conn.execute(
                    "INSERT INTO chunks_fts(rowid, chunk_id, heading, text) VALUES (?, ?, ?, ?)",
                    (rowid, c.id, c.heading_path, c.text),
                )
        log.debug("upserted %d chunks", len(chunks))

    def for_file(self, file_id: int) -> list[StoredChunk]:
        with self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM chunks WHERE file_id = ? ORDER BY seq", (file_id,)
            ).fetchall()
        return [_chunk(r) for r in rows]

    def get_many(self, ids: list[str]) -> list[StoredChunk]:
        found: dict[str, StoredChunk] = {}
        with self._db.connect() as conn:
            for i in range(0, len(ids), _BATCH):
                batch = ids[i : i + _BATCH]
                marks = ", ".join("?" for _ in batch)
                for r in conn.execute(f"SELECT {_COLUMNS} FROM chunks WHERE id IN ({marks})", batch):
                    found[r["id"]] = _chunk(r)
        return [found[i] for i in ids if i in found]

    def delete_file(self, file_id: int, file_title: str, reason: Literal["deleted", "replaced"]) -> list[str]:
        """The one path that removes a file's chunks (FTS rows cannot cascade). Keeps the files row."""
        removed_at = self._clock().astimezone(UTC).isoformat()
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT rid, id FROM chunks WHERE file_id = ? ORDER BY seq", (file_id,)
            ).fetchall()
            conn.executemany(
                "INSERT OR REPLACE INTO removed_chunks(chunk_id, file_id, file_title, reason, removed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [(r["id"], file_id, file_title, reason, removed_at) for r in rows],
            )
            conn.executemany("DELETE FROM chunks_fts WHERE rowid = ?", [(r["rid"],) for r in rows])
            conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))  # chunk_topics cascade
        log.info("removed %d chunks of file %s (%s)", len(rows), file_id, reason)
        return [r["id"] for r in rows]

    def set_module(self, file_id: int, module_id: int | None) -> None:
        with self._db.connect() as conn:
            conn.execute("UPDATE chunks SET module_id = ? WHERE file_id = ?", (module_id, file_id))

    def keyword_search(
        self,
        query: str,
        course_id: int,
        origin: Origin,
        filters: KeywordFilters = KeywordFilters(),
        limit: int = 30,
    ) -> list[tuple[str, float]]:
        match = fts_query(query)
        if match is None:
            return []
        where = ["chunks_fts MATCH ?", "c.course_id = ?", "c.origin = ?"]
        params: list = [match, course_id, origin]
        if filters.module_id is not None:
            where.append("c.module_id = ?")
            params.append(filters.module_id)
        if filters.file_id is not None:
            where.append("c.file_id = ?")
            params.append(filters.file_id)
        if filters.kind is not None:
            where.append("c.kind = ?")
            params.append(filters.kind)
        if filters.topic_id is not None:
            where.append("EXISTS (SELECT 1 FROM chunk_topics t WHERE t.chunk_id = c.id AND t.topic_id = ?)")
            params.append(filters.topic_id)
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT c.id, -bm25(chunks_fts) AS score FROM chunks_fts JOIN chunks c ON c.rid = chunks_fts.rowid "
                f"WHERE {' AND '.join(where)} ORDER BY score DESC, c.id LIMIT ?",
                (*params, limit),
            ).fetchall()
        log.debug("keyword search %r -> %d hits", query, len(rows))
        return [(r["id"], r["score"]) for r in rows]

    def link_topics(self, links: list[tuple[str, int]]) -> None:
        with self._db.connect() as conn:
            conn.executemany("INSERT OR IGNORE INTO chunk_topics(chunk_id, topic_id) VALUES (?, ?)", links)

    def unlink_file_topics(self, file_id: int) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM chunk_topics WHERE chunk_id IN (SELECT id FROM chunks WHERE file_id = ?)", (file_id,))

    def topic_chunks(self, topic_id: int, module_id: int | None = None, course_id: int | None = None) -> list[StoredChunk]:
        where, params = ["t.topic_id = ?"], [topic_id]
        if module_id is not None:
            where.append("c.module_id = ?")
            params.append(module_id)
        if course_id is not None:
            where.append("c.course_id = ?")
            params.append(course_id)
        with self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT {_C_COLUMNS} FROM chunk_topics t JOIN chunks c ON c.id = t.chunk_id "
                f"JOIN files f ON f.id = c.file_id WHERE {' AND '.join(where)} ORDER BY f.queue_pos, c.seq",
                params,
            ).fetchall()
        return [_chunk(r) for r in rows]

    def topics_supported_in_module(self, module_id: int) -> set[int]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT t.topic_id FROM chunk_topics t JOIN chunks c ON c.id = t.chunk_id "
                "WHERE c.module_id = ?",
                (module_id,),
            ).fetchall()
        return {r["topic_id"] for r in rows}

    def removed(self, ids: list[str]) -> dict[str, RemovedChunk]:
        found: dict[str, RemovedChunk] = {}
        with self._db.connect() as conn:
            for i in range(0, len(ids), _BATCH):
                batch = ids[i : i + _BATCH]
                marks = ", ".join("?" for _ in batch)
                for r in conn.execute(
                    "SELECT chunk_id, file_id, file_title, reason, removed_at FROM removed_chunks "
                    f"WHERE chunk_id IN ({marks})",
                    batch,
                ):
                    found[r["chunk_id"]] = RemovedChunk(**dict(r))
        return found
