import pytest

from eduagent.kb.text_parser import normalise_text, parse_markdown, parse_text
from eduagent.kb.types import Block, IngestError


def test_text_line_ranges():
    text = "First para\nsecond line\n\n\nSecond para\n\nThird para\nends here\n"
    assert parse_text(text) == [
        Block("First para\nsecond line", "text", loc=1, loc_end=2),
        Block("Second para", "text", loc=5, loc_end=5),
        Block("Third para\nends here", "text", loc=7, loc_end=8),
    ]


def test_text_handles_crlf():
    assert parse_text("a\r\nb\r\n\r\nc") == [Block("a\nb", "text", loc=1, loc_end=2), Block("c", "text", loc=4, loc_end=4)]


def test_markdown_structure():
    md = (
        "# Title ##\n"
        "Intro line.\n"
        "\n"
        "## Part\n"
        "```python\n"
        "# not a heading\n"
        "x = 1\n"
        "```\n"
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |\n"
        "After table.\n"
    )
    assert parse_markdown(md) == [
        Block("Title", "heading", level=1, loc=1, loc_end=1),
        Block("Intro line.", "text", loc=2, loc_end=2),
        Block("Part", "heading", level=2, loc=4, loc_end=4),
        Block("```python\n# not a heading\nx = 1\n```", "code", loc=5, loc_end=8),
        Block("| a | b |\n|---|---|\n| 1 | 2 |", "table", loc=9, loc_end=11),
        Block("After table.", "text", loc=12, loc_end=12),
    ]


def test_markdown_unclosed_fence_runs_to_end():
    assert parse_markdown("intro\n~~~\ncode\n# still code") == [
        Block("intro", "text", loc=1, loc_end=1),
        Block("~~~\ncode\n# still code", "code", loc=2, loc_end=4),
    ]


def test_markdown_hashtag_is_not_a_heading():
    assert parse_markdown("#hashtag") == [Block("#hashtag", "text", loc=1, loc_end=1)]


def test_normalise_text_hash_stable():
    a = "Line one  \r\nLine two\t\r\n\r\n\r\n\r\nLine three  \r\n"
    b = "Line one\nLine two\n\nLine three"
    assert normalise_text(a) == normalise_text(b) == b


def test_normalise_text_lone_cr():
    assert normalise_text("a\rb\r\r\r\rc") == "a\nb\n\nc"


def test_ingest_error_message():
    err = IngestError("That file could not be read.")
    assert err.user_message == str(err) == "That file could not be read."
    with pytest.raises(IngestError):
        raise err
