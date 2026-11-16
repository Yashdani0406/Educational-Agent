"""Splits text into sentences without cutting at abbreviations, decimals or initials."""

import re

WHAT_IT_DOES = "Cuts text into sentences, taking care not to break at things like 'e.g.', 'Fig.' or '0.93'."

ABBREVIATIONS = {"e.g.", "i.e.", "etc.", "vs.", "fig.", "eq.", "dr.", "al.", "approx."}

_CLOSERS = "\"')]}”’"
_OPENERS = "([{\"'“‘"

# A sentence end (. ? !, optional closing quotes/brackets, then whitespace), a blank line (CRLF-safe), or a newline before
# a list marker. The possessive quantifiers and the lookbehind keep long punctuation runs linear.
_BOUNDARY = re.compile(
    r"""(?<![.?!])(?P<end>[.?!]++["')\]”’]*+)(?=\s)
      | (?P<blank>\n[^\S\n]*\n\s*)
      | (?P<bullet>\n(?=[^\S\n]*[-*•][ \t]))
      | (?P<num>\n(?=[^\S\n]*\d{1,2}[.)][ \t]))""",
    re.VERBOSE,
)
# Accepted trade-off: a sentence that really ends in one capital letter ("...model B. Then") will not split.
_INITIAL = re.compile(r"[A-Z]\.")
_LIST_NUMBER_START = re.compile(r"\n[^\S\n]*\d{1,2}\.\Z")  # "1." opening a line (1-2 digits; years are not list numbers)
_LIST_LINE = re.compile(r"[^\S\n]*(?:[-*•]|\d{1,2}[.)])[ \t]")
_WINDOW = 40  # how far back we look; keeps splitting linear on very long lines


def _is_protected(text: str, end: int) -> bool:
    """True if the full stop ending at `end` belongs to an abbreviation, an initial or a line-leading list number."""
    lo = max(0, end - _WINDOW)
    window = text[lo:end]
    if _LIST_NUMBER_START.search(window if lo else "\n" + window):
        return True
    token = window.split()[-1].lstrip(_OPENERS)
    return token.lower() in ABBREVIATIONS or bool(_INITIAL.fullmatch(token))


def _numbered_line_starts_item(text: str, newline: int) -> bool:
    """A newline before "N." is a boundary only after a finished sentence, a colon, or another list line.

    Hard-wrapped text that merely has a number at the start of a line ("published in\\n1986. Later") must not be cut;
    under-splitting is safe."""
    prev = text[text.rfind("\n", 0, newline) + 1 : newline].rstrip()
    if _LIST_LINE.match(prev):
        return True
    return prev.rstrip(_CLOSERS).endswith((".", "?", "!")) or prev.endswith(":")


def split_sentences(text: str) -> list[str]:
    """Stripped substrings of `text`, in order; nothing is added, rewritten or lost apart from whitespace."""
    pieces, start = [], 0
    for m in _BOUNDARY.finditer(text):
        if m.group("end"):
            core = m.group("end").rstrip(_CLOSERS)
            if core == "." and _is_protected(text, m.start() + 1):
                continue
            cut = m.end()
        else:
            if m.group("num") and not _numbered_line_starts_item(text, m.start()):
                continue
            cut = m.start()
        pieces.append(text[start:cut])
        start = m.end() if m.group("blank") else cut
    pieces.append(text[start:])
    return [p.strip() for p in pieces if p.strip()]


def word_count(text: str) -> int:
    return len(text.split())
