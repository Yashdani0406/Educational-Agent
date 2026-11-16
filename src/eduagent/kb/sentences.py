"""Splits text into sentences without cutting at abbreviations, decimals or initials."""

import re

WHAT_IT_DOES = "Cuts text into sentences, taking care not to break at things like 'e.g.', 'Fig.' or '0.93'."

ABBREVIATIONS = {"e.g.", "i.e.", "etc.", "vs.", "fig.", "eq.", "dr.", "al.", "approx."}

_CLOSERS = "\"')]}”’"
_OPENERS = "([{\"'“‘"

# A sentence end (. ? !, optional closing quotes/brackets, then whitespace), a blank line, or a newline before a list marker.
_BOUNDARY = re.compile(
    r"""(?P<end>[.?!]+["')\]”’]*)(?=\s)
      | (?P<blank>\n[ \t]*\n\s*)
      | (?P<item>\n(?=[ \t]*(?:[-*•]|\d+[.)])[ \t]))""",
    re.VERBOSE,
)
# Accepted trade-off: a sentence that really ends in one capital letter ("...model B. Then") will not split.
_INITIAL = re.compile(r"[A-Z]\.")
_LIST_NUMBER = re.compile(r"\d+\.")  # "1." opening a list line


def _is_protected(text: str, end: int) -> bool:
    """True if the full stop ending at `end` belongs to an abbreviation, an initial or a list number."""
    line = text[text.rfind("\n", 0, end) + 1 : end]
    token = line.split()[-1].lstrip(_OPENERS)
    if _LIST_NUMBER.fullmatch(line.strip()):
        return True
    return token.lower() in ABBREVIATIONS or bool(_INITIAL.fullmatch(token))


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
            cut = m.start()
        pieces.append(text[start:cut])
        start = m.end() if m.group("blank") else cut
    pieces.append(text[start:])
    return [p.strip() for p in pieces if p.strip()]


def word_count(text: str) -> int:
    return len(text.split())
