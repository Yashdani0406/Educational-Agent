"""Turns parsed blocks into search-sized chunks that keep their exact location, following design section 3.4."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from eduagent.db.chunks import LocKind
from eduagent.db.files import Layout
from eduagent.kb.embed import DOCUMENT_PREFIX, MAX_EMBED_TOKENS
from eduagent.kb.sentences import split_sentences, word_count
from eduagent.kb.types import Block, ChunkDraft

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Cuts a file's text into search-sized pieces along its slides, headings and sentences, remembering where each came from."

SLIDE_MIN_WORDS = 25
SECTION_TARGET = (450, 550)
SECTION_MAX = 800
SECTION_OVERLAP_SENTENCES = 2
TEXT_TARGET = (400, 500)
TEXT_OVERLAP = 0.15
_OVERLAP_MAX_WORDS = 90  # a whole-sentence overlap never grows past this, so windows share about 15%
_ATOMIC = ("table", "code", "formula")  # never split unless over the cap or the hard maximum
_LOC_KIND: dict[str, LocKind] = {
    "slides": "slide", "document": "page", "docx": "heading", "text": "line", "markdown": "line", "web": "heading"}


def embedding_body(file_title: str, chunk: ChunkDraft) -> str:
    """What the embedder is given before it adds its own document prefix."""
    return _body(file_title, chunk.heading_path, chunk.text)


def embedding_text(file_title: str, chunk: ChunkDraft) -> str:
    return DOCUMENT_PREFIX + embedding_body(file_title, chunk)


def _body(title: str, heading_path: str, text: str) -> str:
    return f"{title} > {heading_path}\n\n{text}" if heading_path else f"{title}\n\n{text}"


class _Piece(NamedTuple):
    text: str
    heading_path: str
    loc_start: int | None
    loc_end: int | None


@dataclass(frozen=True)
class _Atom:
    """One sentence, one atomic block (or a forced piece of either): the smallest thing a chunk is built from."""

    text: str
    sep: str  # what joined it to the atom before it in the source
    loc: int | None
    loc_end: int | None
    words: int


def _overlap_sentences(chunk: list[_Atom]) -> list[_Atom]:
    k = min(SECTION_OVERLAP_SENTENCES, len(chunk) - 1)
    return chunk[-k:] if k > 0 else []


def _overlap_fraction(chunk: list[_Atom]) -> list[_Atom]:
    target = TEXT_OVERLAP * sum(a.words for a in chunk)
    kept: list[_Atom] = []
    total = 0
    for a in reversed(chunk[1:]):  # never the whole chunk
        if total >= target:
            break
        kept.insert(0, a)
        total += a.words
    while total > _OVERLAP_MAX_WORDS and kept:
        total -= kept.pop(0).words
    return kept


def _no_overlap(chunk: list[_Atom]) -> list[_Atom]:
    return []


@dataclass(frozen=True)
class _Rules:
    lo: int  # cut once a chunk reaches this many words
    hi: int  # do not add a sentence that would pass this
    hard: int  # a single long sentence may carry a chunk this far
    overlap: Callable[[list[_Atom]], list[_Atom]]


_RULES = {
    "slides": _Rules(*SECTION_TARGET, SECTION_MAX, _no_overlap),
    "document": _Rules(*SECTION_TARGET, SECTION_MAX, _overlap_sentences),
    "docx": _Rules(*SECTION_TARGET, SECTION_MAX, _no_overlap),
    "text": _Rules(*TEXT_TARGET, TEXT_TARGET[1], _overlap_fraction),
    "markdown": _Rules(*TEXT_TARGET, TEXT_TARGET[1], _overlap_fraction),
    "web": _Rules(*TEXT_TARGET, TEXT_TARGET[1], _overlap_fraction),
}


def _largest_prefix(n: int, ok: Callable[[int], bool]) -> int:
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ok(mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


def _split_to_fit(text: str, ok: Callable[[str], bool], level: int) -> list[str]:
    """Forced cut: by lines (level 0), then whitespace (1), then characters (2), until every piece satisfies `ok`."""
    if ok(text):
        return [text]
    if level == 2:
        out = []
        while text:
            k = _largest_prefix(len(text), lambda n: ok(text[:n])) or 1
            out.append(text[:k])
            text = text[k:]
        return out
    parts = text.split("\n") if level == 0 else text.split()
    glue = "\n" if level == 0 else " "
    out, i = [], 0
    while i < len(parts):
        k = _largest_prefix(len(parts) - i, lambda n: ok(glue.join(parts[i : i + n])))
        if k == 0:
            out.extend(_split_to_fit(parts[i], ok, level + 1))
            i += 1
        else:
            out.append(glue.join(parts[i : i + k]))
            i += k
    return [p for p in out if p.strip()]


def _join(atoms: list[_Atom]) -> str:
    return atoms[0].text + "".join(a.sep + a.text for a in atoms[1:])


def _span(items: Sequence[Block | _Atom]) -> tuple[int | None, int | None]:
    locs = [x for i in items for x in (i.loc, i.loc_end) if x is not None]
    return (min(locs), max(locs)) if locs else (None, None)


def _path(stack: list[tuple[int, str]]) -> str:
    return " > ".join(t for _, t in stack)


class _Chunker:
    def __init__(self, layout: Layout, title: str, count_tokens: Callable[[str], int]):
        self.layout, self.title, self.count, self.rules = layout, title, count_tokens, _RULES[layout]

    def cap_ok(self, text: str, heading_path: str) -> bool:
        return self.count(DOCUMENT_PREFIX + _body(self.title, heading_path, text)) <= MAX_EMBED_TOKENS

    def _oversize(self, text: str, hp: str) -> bool:
        return word_count(text) > self.rules.hard or not self.cap_ok(text, hp)

    def _piece_ok(self, hp: str) -> Callable[[str], bool]:
        return lambda t: word_count(t) <= self.rules.hi and self.cap_ok(t, hp)

    # ---- sentences and atoms ----

    def _sentences(self, b: Block):
        """(sentence, separator before it, first line, last line); lines are counted only for text and markdown."""
        text, pos = b.text, 0
        count_lines = self.layout in ("text", "markdown") and b.loc is not None
        line = b.loc
        for k, s in enumerate(split_sentences(text)):
            i = text.find(s, pos)
            i = pos if i < 0 else i
            gap = text[pos:i]
            sep = "\n\n" if k == 0 or gap.count("\n") > 1 else "\n" if "\n" in gap else " "
            if count_lines:
                first = line + text.count("\n", pos, i)
                line = first + s.count("\n")
                last = min(line, b.loc_end) if b.loc_end is not None else line
                yield s, sep, first, max(first, last)
            else:
                yield s, sep, b.loc, b.loc_end
            pos = i + len(s)

    def atoms(self, blocks: list[Block], hp: str) -> list[_Atom]:
        out: list[_Atom] = []
        ok = self._piece_ok(hp)
        for b in blocks:
            if b.kind == "heading" or not b.text.strip():
                continue
            if b.kind in _ATOMIC:
                text = b.text.strip()
                parts = _split_to_fit(text, ok, 0) if self._oversize(text, hp) else [text]
                out += [_Atom(p, "\n\n" if i == 0 else "\n", b.loc, b.loc_end, word_count(p)) for i, p in enumerate(parts)]
                continue
            for s, sep, lo, hi in self._sentences(b):
                parts = _split_to_fit(s, ok, 1) if self._oversize(s, hp) else [s]
                out += [_Atom(p, sep if i == 0 else " ", lo, hi, word_count(p)) for i, p in enumerate(parts)]
        return out

    # ---- packing ----

    def pack(self, atoms: list[_Atom], hp: str) -> list[list[_Atom]]:
        r = self.rules
        fits = lambda group: self.cap_ok(_join(group), hp)  # noqa: E731
        chunks: list[list[_Atom]] = []
        cur: list[_Atom] = []
        fresh = 0  # atoms in `cur` that are not overlap
        for a in atoms:
            if fresh and (sum(x.words for x in cur) + a.words > r.hi or not fits(cur + [a])):
                chunks.append(cur)
                cur, fresh = r.overlap(cur), 0
            if cur and not fresh and (sum(x.words for x in cur) + a.words > r.hard or not fits(cur + [a])):
                cur = []  # the overlap would not fit next to this sentence: drop it
            cur.append(a)
            fresh += 1
            if sum(x.words for x in cur) >= r.lo:
                chunks.append(cur)
                cur, fresh = r.overlap(cur), 0
        if fresh:
            chunks.append(cur)
        return chunks

    def _piece(self, atoms: list[_Atom], hp: str) -> _Piece:
        return _Piece(_join(atoms), hp, *_span(atoms))

    def section(self, blocks: list[Block], hp: str) -> list[_Piece]:
        atoms = self.atoms(blocks, hp)
        if not atoms:
            return []
        if self.layout == "docx" and sum(a.words for a in atoms) <= self.rules.hard and self.cap_ok(_join(atoms), hp):
            return [self._piece(atoms, hp)]
        return [self._piece(g, hp) for g in self.pack(atoms, hp)]

    # ---- layouts ----

    def sections(self, blocks: list[Block], carry: Sequence[Sequence]) -> tuple[list[_Piece], list[tuple[int, str]]]:
        stack = [(int(level), str(text)) for level, text in carry]
        sections: list[tuple[str, list[Block]]] = []
        hp, pending = _path(stack), []
        for b in blocks:
            if b.kind != "heading":
                pending.append(b)
            elif b.text.strip():
                sections.append((hp, pending))
                pending = []
                level = max(b.level, 1)
                stack = [e for e in stack if e[0] < level] + [(level, b.text.strip())]
                hp = _path(stack)
        sections.append((hp, pending))
        if self.layout == "docx" and (whole := self._whole_docx(blocks)):
            return [whole], stack
        return [p for sec_hp, sec_blocks in sections for p in self.section(sec_blocks, sec_hp)], stack

    def _whole_docx(self, blocks: list[Block]) -> _Piece | None:
        body = [b for b in blocks if b.kind != "heading"]
        if sum(word_count(b.text) for b in body) >= SECTION_MAX:
            return None
        atoms = self.atoms(body, "")
        if atoms and self.cap_ok(_join(atoms), ""):
            return self._piece(atoms, "")
        return None

    def slides(self, blocks: list[Block]) -> list[_Piece]:
        groups: list[list[Block]] = []
        for b in blocks:
            if groups and (b.loc is None or b.loc == groups[-1][-1].loc):
                groups[-1].append(b)
            else:
                groups.append([b])
        units = [self._slide(g) for g in groups]
        merged: list[_Piece] = []
        acc: _Piece | None = None
        for u in units:
            if acc is None:
                acc = u
            elif word_count(acc.text) < SLIDE_MIN_WORDS and self._can_merge(acc, u):
                acc = _merge(acc, u)
            else:
                merged.append(acc)
                acc = u
        if acc is not None:
            if merged and word_count(acc.text) < SLIDE_MIN_WORDS and self._can_merge(merged[-1], acc):
                merged[-1] = _merge(merged[-1], acc)
            else:
                merged.append(acc)
        out: list[_Piece] = []
        for u in merged:
            if not u.text.strip():
                continue
            if self._oversize(u.text, u.heading_path):
                out += [u._replace(text=t) for t in _split_to_fit(u.text, self._piece_ok(u.heading_path), 0)]
            else:
                out.append(u)
        return out

    def _slide(self, blocks: list[Block]) -> _Piece:
        hp = next((b.text.strip() for b in blocks if b.kind == "heading" and b.text.strip()), "")
        body = "\n\n".join(b.text.strip() for b in blocks if b.kind not in ("heading", "notes") and b.text.strip())
        notes = "\n\n".join(b.text.strip() for b in blocks if b.kind == "notes" and b.text.strip())
        text = body + ("\n\nSpeaker notes: " + notes if notes and body else "Speaker notes: " + notes if notes else "")
        return _Piece(text, hp, *_span(blocks))

    def _can_merge(self, a: _Piece, b: _Piece) -> bool:
        m = _merge(a, b)
        return word_count(m.text) <= self.rules.hard and self.cap_ok(m.text, m.heading_path)


def _merge(a: _Piece, b: _Piece) -> _Piece:
    locs = [x for x in (a.loc_start, a.loc_end, b.loc_start, b.loc_end) if x is not None]
    text = "\n\n".join(t for t in (a.text, b.text) if t)
    return _Piece(text, a.heading_path or b.heading_path, min(locs, default=None), max(locs, default=None))


def chunk_blocks(
    blocks: list[Block],
    layout: Layout,
    *,
    file_title: str,
    count_tokens: Callable[[str], int],
    carry_headings: Sequence[tuple[int, str]] = (),
    first_seq: int = 0,
) -> tuple[list[ChunkDraft], list[tuple[int, str]]]:
    """Chunks for one piece of a file, plus the heading path (level, text) still open at its end.

    `carry_headings` is the open path returned for the previous piece (2-item lists from JSON are fine)."""
    chunker = _Chunker(layout, file_title, count_tokens)
    if layout == "slides":
        pieces, open_path = chunker.slides(blocks), []
    else:
        pieces, open_path = chunker.sections(blocks, carry_headings)
    kind = _LOC_KIND[layout]
    drafts = [
        ChunkDraft(first_seq + i, p.text, p.heading_path, kind, p.loc_start, p.loc_end, word_count(p.text))
        for i, p in enumerate(pieces)
    ]
    log.debug("chunked %d blocks (%s) into %d chunks", len(blocks), layout, len(drafts))
    return drafts, open_path
