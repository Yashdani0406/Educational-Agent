"""Reads plain text, pasted transcripts and Markdown into blocks with line ranges."""

import re

from eduagent.kb.types import Block

WHAT_IT_DOES = "Reads plain text and Markdown notes into headings, paragraphs, tables and code, remembering which lines each came from."

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

Lines = list[tuple[int, str]]  # (1-based line number, text)


def _numbered(text: str) -> Lines:
    return list(enumerate(_LINE_BREAK.split(text), start=1))


def _paragraphs(lines: Lines) -> list[Block]:
    """Group numbered lines into text blocks separated by blank lines."""
    blocks: list[Block] = []
    run: Lines = []

    def flush() -> None:
        if run:
            blocks.append(Block("\n".join(t for _, t in run).strip(), "text", loc=run[0][0], loc_end=run[-1][0]))
            run.clear()

    for n, line in lines:
        if line.strip():
            run.append((n, line))
        else:
            flush()
    flush()
    return blocks


def parse_text(text: str) -> list[Block]:
    return _paragraphs(_numbered(text))


def _fence_end(lines: Lines, i: int, marker: str) -> int:
    """Index of the closing fence line; an unclosed fence runs to the end, as in CommonMark."""
    closing = re.compile(rf" {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*")
    for j in range(i + 1, len(lines)):
        if closing.fullmatch(lines[j][1]):
            return j
    return len(lines) - 1


def parse_markdown(text: str) -> list[Block]:
    lines = _numbered(text)
    blocks: list[Block] = []
    plain: Lines = []

    def flush_plain() -> None:
        blocks.extend(_paragraphs(plain))
        plain.clear()

    i = 0
    while i < len(lines):
        n, line = lines[i]
        fence = _FENCE.match(line)
        heading = _HEADING.match(line)
        if fence:
            flush_plain()
            j = _fence_end(lines, i, fence.group(1))
            blocks.append(Block("\n".join(t for _, t in lines[i : j + 1]), "code", loc=n, loc_end=lines[j][0]))
            i = j + 1
        elif heading and heading.group(2):
            flush_plain()
            blocks.append(Block(heading.group(2), "heading", level=len(heading.group(1)), loc=n, loc_end=n))
            i += 1
        elif line.lstrip().startswith("|"):
            flush_plain()
            j = i
            while j + 1 < len(lines) and lines[j + 1][1].lstrip().startswith("|"):
                j += 1
            blocks.append(Block("\n".join(t.strip() for _, t in lines[i : j + 1]), "table", loc=n, loc_end=lines[j][0]))
            i = j + 1
        else:
            plain.append((n, line))
            i += 1
    flush_plain()
    return blocks


def normalise_text(text: str) -> str:
    """Stable form of pasted text for hashing: unify line endings, drop trailing blanks, collapse blank runs."""
    text = _LINE_BREAK.sub("\n", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
