"""SQLite access: one short-lived connection per use, versioned SQL migrations."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

log = logging.getLogger(__name__)


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
        files = sorted(
            (int(f.name.split("_", 1)[0]), f)
            for f in resources.files("eduagent.db.migrations").iterdir()
            if f.name.endswith(".sql")
        )
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            for number, f in files:
                if number <= version:
                    continue
                script = f.read_text(encoding="utf-8")
                try:
                    conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
                except BaseException:
                    if conn.in_transaction:
                        conn.rollback()
                    raise
                version = number
                log.info("applied migration %s", f.name)
        return version
