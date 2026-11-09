"""Makes model-written Mermaid diagrams safe to render."""

import re

WHAT_IT_DOES = (
    "Fixes the most common mistake small models make in Mermaid diagrams, an unquoted "
    "label containing brackets, so the diagram draws instead of showing a syntax error."
)

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*(\w*)")
_SKIP_LINE = re.compile(r"^\s*(?:%%|style\b|classDef\b|class\b|linkStyle\b|click\b)")
# Edge labels are matched first so their text is never mistaken for a node; otherwise
# a node is `ID` directly followed by [ ( or {.
_TOKEN = re.compile(
    r"(?P<edge>\|[^|\n]*\||(?:--|==|-\.)\s.*?\s(?:-->|---|==>|===|\.->))"
    r"|(?P<id>\w+)(?P<open>[\[({])"
)
_CLOSE = {"[": "]", "(": ")", "{": "}"}
_MULTI_CHAR_SHAPE = "([{/\\"  # ((  [(  {{  [[  ([  [/  [\  - left alone
_BRACKETS = "()[]{}"


def _quote_line(line: str) -> str:
    out: list[str] = []
    pos = 0
    while m := _TOKEN.search(line, pos):
        if m.group("edge"):
            out.append(line[pos : m.end()])
            pos = m.end()
            continue
        start, opener = m.end(), m.group("open")
        closer, depth, end = _CLOSE[opener], 1, None
        if line[start : start + 1] not in _MULTI_CHAR_SHAPE:
            for i in range(start, len(line)):
                depth += (line[i] == opener) - (line[i] == closer)
                if depth == 0:
                    end = i
                    break
        if end is None:  # unterminated or multi-character shape: leave untouched
            out.append(line[pos:start])
            pos = start
            continue
        label = line[start:end]
        stripped = label.strip()
        quoted = len(stripped) >= 2 and stripped[0] == stripped[-1] == '"'
        if not quoted and any(c in label for c in _BRACKETS):
            label = f'"{label.replace(chr(34), "#quot;")}"'
        out.append(line[pos:start] + label + closer)
        pos = end + 1
    out.append(line[pos:])
    return "".join(out)


def _quote_block(lines: list[str]) -> list[str]:
    first = next((ln for ln in lines if ln.strip() and not ln.lstrip().startswith("%%")), "")
    if not first.strip().startswith(("graph", "flowchart")):
        return lines  # other diagram types use brackets differently
    result = []
    for ln in lines:
        body = ln.rstrip("\r\n")
        result.append(ln if _SKIP_LINE.match(body) else _quote_line(body) + ln[len(body):])
    return result


def quote_mermaid_labels(markdown: str) -> str:
    """Quote flowchart node labels containing brackets, inside ```mermaid fences only."""
    out: list[str] = []
    block: list[str] | None = None  # lines of the mermaid block being collected
    fence: str | None = None  # opening fence of the current code block, if any
    for line in markdown.splitlines(keepends=True):
        m = _FENCE.match(line)
        if fence is None:
            out.append(line)
            if m:
                fence = m.group(1)
                block = [] if m.group(2) == "mermaid" else None
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2) \
                and line.strip() == m.group(1):
            if block is not None:
                out.extend(_quote_block(block))
            out.append(line)
            fence, block = None, None
        elif block is not None:
            block.append(line)
        else:
            out.append(line)
    if block:  # unterminated fence: still a mermaid block
        out.extend(_quote_block(block))
    return "".join(out)
