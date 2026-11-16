"""The common shapes every parser and the chunker share, so the chunker never sees a file format."""

from dataclasses import dataclass
from typing import Literal

from eduagent.db.chunks import LocKind

WHAT_IT_DOES = "Defines the plain pieces (blocks, chunk drafts, ingest errors) that every file reader hands to the chunker."

BlockKind = Literal["heading", "text", "table", "code", "formula", "notes"]


@dataclass(frozen=True)
class Block:
    text: str
    kind: BlockKind
    level: int = 0  # heading level (1 = top)
    loc: int | None = None  # page / slide / line number, 1-based
    loc_end: int | None = None


@dataclass(frozen=True)
class ChunkDraft:
    seq: int
    text: str
    heading_path: str
    loc_kind: LocKind
    loc_start: int | None
    loc_end: int | None
    word_count: int


class IngestError(Exception):
    """A failure with a plain-English message that the Library shows to the user."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message
