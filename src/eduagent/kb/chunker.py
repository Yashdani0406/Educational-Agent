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
_NOTES_LABEL = "Speaker notes:"
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
    blocks: tuple = ()  # slides only: the content blocks, kept so an oversize slide can go through the sentence path


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


def _split_to_fit(text: str, ok: Callable[[str], bool], level: int = 0) -> list[tuple[str, int]]:
    """Forced cut: by lines (level 0), then whitespace (1), then characters (2), until every piece satisfies `ok`.

    Returns (piece, number of newlines before it in `text`); pieces keep their own newlines."""
    if ok(text):
        return [(text, 0)]
    if level == 2:
        out, pos = [], 0
        while pos < len(text):
            k = _largest_prefix(len(text) - pos, lambda n: ok(text[pos : pos + n])) or 1
            out.append((text[pos : pos + k], 0))
            pos += k
        return out
    parts = text.split("\n") if level == 0 else text.split()
    glue = "\n" if level == 0 else " "
    out, i = [], 0
    while i < len(parts):
        base = i if level == 0 else 0
        k = _largest_prefix(len(parts) - i, lambda n: ok(glue.join(parts[i : i + n])))
        if k == 0:
            out += [(t, base + o) for t, o in _split_to_fit(parts[i], ok, level + 1)]
            i += 1
            continue
        piece = glue.join(parts[i : i + k])
        if piece.strip():
            lead = piece[: len(piece) - len(piece.lstrip())].count("\n")
            out.append((piece.strip(), base + lead))
        i += k
    return out


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

    def _forced(self, text: str, hp: str, lo: int | None, hi: int | None, sep: str) -> list[_Atom]:
        """Forced pieces of one sentence or block; text and Markdown pieces cite only their own lines."""
        out: list[_Atom] = []
        prev_end = -1
        for i, (piece, off) in enumerate(_split_to_fit(text, self._piece_ok(hp))):
            plo, phi = lo, hi
            if self.layout in ("text", "markdown") and lo is not None:
                plo = lo + off
                phi = plo + piece.count("\n")
                if hi is not None:
                    phi = max(plo, min(phi, hi))
            joiner = sep if i == 0 else "\n" if off > prev_end else " "
            prev_end = off + piece.count("\n")
            out.append(_Atom(piece, joiner, plo, phi, word_count(piece)))
        return out

    def atoms(self, blocks: list[Block], hp: str) -> list[_Atom]:
        out: list[_Atom] = []
        for b in blocks:
            if b.kind == "heading" or not b.text.strip():
                continue
            if b.kind in _ATOMIC:
                text = b.text.strip()
                if word_count(text) > SECTION_MAX or not self.cap_ok(text, hp):
                    out += self._forced(text, hp, b.loc, b.loc_end, "\n\n")
                else:
                    out.append(_Atom(text, "\n\n", b.loc, b.loc_end, word_count(text)))
                continue
            for s, sep, lo, hi in self._sentences(b):
                if self._oversize(s, hp):
                    out += self._forced(s, hp, lo, hi, sep)
                else:
                    out.append(_Atom(s, sep, lo, hi, word_count(s)))
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
        # headings stay in the text, on their own lines, because the whole-document chunk has no heading path
        body = [Block(b.text, "text", loc=b.loc, loc_end=b.loc_end) if b.kind == "heading" else b for b in blocks]
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
            elif self.words(acc.text) < SLIDE_MIN_WORDS and self._can_merge(acc, u):
                acc = _merge(acc, u)
            else:
                merged.append(acc)
                acc = u
        if acc is not None:
            if merged and self.words(acc.text) < SLIDE_MIN_WORDS and self._can_merge(merged[-1], acc):
                merged[-1] = _merge(merged[-1], acc)
            else:
                merged.append(acc)
        out: list[_Piece] = []
        for u in merged:
            text = u.text or u.heading_path  # a title-only slide still contributes its title
            if not text.strip():
                continue
            if u.blocks and self._oversize(text, u.heading_path):
                atoms = self.atoms(list(u.blocks), u.heading_path)
                out += [_Piece(_join(g), u.heading_path, u.loc_start, u.loc_end) for g in self.pack(atoms, u.heading_path)]
            else:
                out.append(u._replace(text=text, blocks=()))
        return out

    def words(self, text: str) -> int:
        """Words in a chunk's text; the "Speaker notes:" label is ours, not the course's."""
        return word_count(text) - (2 * text.count(_NOTES_LABEL) if self.layout == "slides" else 0)

    def _slide(self, blocks: list[Block]) -> _Piece:
        """First heading = path; other headings stay as text lines; notes go last under a label."""
        hp, content, notes, seen = "", [], [], False
        for b in blocks:
            t = b.text.strip()
            if not t:
                continue
            if b.kind == "heading" and not seen:
                hp, seen = t, True
            elif b.kind == "heading":
                content.append(Block(t, "text", loc=b.loc, loc_end=b.loc_end))
            elif b.kind == "notes":
                notes.append(b)
            else:
                content.append(b)
        if notes:
            joined = _NOTES_LABEL + " " + "\n\n".join(n.text.strip() for n in notes)
            content.append(Block(joined, "text", loc=notes[0].loc, loc_end=notes[0].loc_end))
        text = "\n\n".join(b.text.strip() for b in content)
        return _Piece(text, hp, *_span(blocks), blocks=tuple(content))

    def _can_merge(self, a: _Piece, b: _Piece) -> bool:
        m = _merge(a, b)
        return self.words(m.text) <= self.rules.hard and self.cap_ok(m.text, m.heading_path)


def _merge(a: _Piece, b: _Piece) -> _Piece:
    locs = [x for x in (a.loc_start, a.loc_end, b.loc_start, b.loc_end) if x is not None]
    # a later slide's own title is not the path any more, so it stays in the text
    b_text = "\n\n".join(t for t in (b.heading_path, b.text) if t) if a.heading_path else b.text
    text = "\n\n".join(t for t in (a.text, b_text) if t)
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
        ChunkDraft(first_seq + i, p.text, p.heading_path, kind, p.loc_start, p.loc_end, chunker.words(p.text))
        for i, p in enumerate(pieces)
    ]
    log.debug("chunked %d blocks (%s) into %d chunks", len(blocks), layout, len(drafts))
    return drafts, open_path
