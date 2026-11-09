"""SQLite access: one short-lived connection per use, versioned SQL migrations."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

WHAT_IT_DOES = (
    "Opens the local SQLite database and applies its numbered schema migrations, so every other part of the app shares one safe storage layer."
)

log = logging.getLogger(__name__)


def _load_migrations() -> list[tuple[int, str]]:
    """Packaged migrations as (number, sql), in numeric order."""
    return sorted(
        (int(f.name.split("_", 1)[0]), f.read_text(encoding="utf-8"))
        for f in resources.files("eduagent.db.migrations").iterdir()
        if f.name.endswith(".sql")
    )


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        finally:
            conn.close()

    def migrate(self) -> int:
        """Apply pending migrations in order, each atomically with its version bump."""
        files = _load_migrations()
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            for number, script in files:
                if number <= version:
                    continue
                try:
                    conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
                except BaseException:
                    if conn.in_transaction:
                        conn.rollback()
                    raise
                version = number
                log.info("applied migration %04d", number)
        return version
