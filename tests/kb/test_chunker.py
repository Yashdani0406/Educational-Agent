import pytest

from eduagent.kb.chunker import chunk_blocks, embedding_body, embedding_text
from eduagent.kb.embed import DOCUMENT_PREFIX, MAX_EMBED_TOKENS
from eduagent.kb.sentences import split_sentences, word_count
from eduagent.kb.types import Block, ChunkDraft

by_words = lambda s: len(s.split())  # noqa: E731
by_chars = lambda s: len(s) // 3  # noqa: E731  (a code-like counter: characters cost tokens)

LAYOUTS = ["slides", "document", "docx", "text", "markdown", "web"]


def gen(start: int, n: int, per: int = 14) -> str:
    """n unique words (w<start>...), a full stop after every `per` words and at the end."""
    words = []
    for i in range(n):
        w = f"w{start + i}"
        if (i + 1) % per == 0 or i == n - 1:
            w += "."
        words.append(w)
    return " ".join(words)


def run(blocks, layout="document", counter=by_words, **kw):
    return chunk_blocks(blocks, layout, file_title="Trees.pdf", count_tokens=counter, **kw)


def slide(n, title, words, notes=None, start=0):
    blocks = [Block(title, "heading", 1, loc=n), Block(gen(start, words, 10), "text", loc=n)]
    if notes:
        blocks.append(Block(notes, "notes", loc=n))
    return blocks


# ---------- slides ----------

def test_one_chunk_per_slide_with_notes():
    blocks = slide(1, "Gini", 30) + slide(2, "Entropy", 40, notes="Say this slowly.", start=100)
    chunks, open_path = run(blocks, "slides")
    assert [(c.heading_path, c.loc_kind, c.loc_start, c.loc_end) for c in chunks] == [
        ("Gini", "slide", 1, 1), ("Entropy", "slide", 2, 2)]
    assert chunks[1].text.endswith("\n\nSpeaker notes: Say this slowly.")
    assert "Speaker notes" not in chunks[0].text
    assert chunks[1].word_count == 40 + 3  # notes words count, the "Speaker notes:" label does not
    assert open_path == []


def test_slide_heading_is_first_heading_without_stack_or_carry():
    blocks = [Block("Top", "heading", 1, loc=1), Block("Sub", "heading", 2, loc=1), Block(gen(0, 30), "text", loc=1)]
    chunks, open_path = run(blocks, "slides", carry_headings=[(1, "Ignored")])
    assert chunks[0].heading_path == "Top"
    assert open_path == []


def test_short_slides_merge_into_next():
    blocks = slide(1, "A", 30) + slide(2, "B", 30, start=50) + slide(3, "C", 8, start=100) + slide(4, "D", 30, start=200)
    chunks, _ = run(blocks, "slides")
    assert [(c.loc_start, c.loc_end) for c in chunks] == [(1, 1), (2, 2), (3, 4)]
    assert chunks[2].heading_path == "C"
    assert "w100" in chunks[2].text and "w200" in chunks[2].text


def test_short_slides_keep_merging_until_25_words():
    blocks = sum((slide(n, f"S{n}", 6, start=n * 10) for n in range(1, 6)), []) + slide(6, "S6", 40, start=500)
    chunks, _ = run(blocks, "slides")
    # titles of merged slides stay in the text: 6, 13, 20 words are all under 25, so slide 4 joins too (27)
    assert [(c.loc_start, c.loc_end) for c in chunks] == [(1, 4), (5, 6)]


def test_last_short_slide_merges_into_previous():
    blocks = slide(1, "A", 30) + slide(2, "B", 30, start=50) + slide(3, "C", 5, start=100)
    chunks, _ = run(blocks, "slides")
    assert [(c.loc_start, c.loc_end) for c in chunks] == [(1, 1), (2, 3)]
    assert chunks[1].heading_path == "B"


def test_slide_merge_skipped_when_it_would_pass_the_cap():
    blocks = slide(1, "A", 1, start=0) + slide(2, "B", 1, start=10)  # two 1-word slides
    chunks, _ = run(blocks, "slides", counter=lambda s: 800 * s.count("w"))  # one slide fits, both together do not
    assert [(c.loc_start, c.loc_end) for c in chunks] == [(1, 1), (2, 2)]


def test_slide_over_the_cap_is_split_and_keeps_its_number():
    table = "\n".join(f"row{i} | " + "x" * 200 for i in range(100))
    blocks = [Block("Big", "heading", 1, loc=7), Block(table, "table", loc=7)]
    chunks, _ = run(blocks, "slides", counter=by_chars)
    assert len(chunks) > 1
    assert all((c.loc_start, c.loc_end, c.heading_path) == (7, 7, "Big") for c in chunks)
    assert "\n".join(c.text for c in chunks) == table


# ---------- document / sections ----------

def test_document_sections_split_with_overlap():
    paras = [Block(gen(i * 70, 70), "text", loc=3 + i // 4) for i in range(1300 // 70 + 1)]
    blocks = [Block("Ch 1", "heading", 1, loc=3)] + paras
    chunks, _ = run(blocks, "document")
    assert len(chunks) >= 3
    assert all(c.loc_kind == "page" and c.heading_path == "Ch 1" for c in chunks)
    for c in chunks[:-1]:
        assert 450 <= c.word_count <= 550
    assert all(c.word_count <= 800 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert split_sentences(nxt.text)[:2] == split_sentences(prev.text)[-2:]
        assert nxt.loc_start <= prev.loc_end
    assert chunks[0].loc_start == 3 and chunks[-1].loc_end == paras[-1].loc
    assert [c.loc_start for c in chunks] == sorted(c.loc_start for c in chunks)


def test_long_single_sentence_may_carry_a_chunk_to_800():
    blocks = [Block(gen(0, 20, 10), "text", loc=1), Block(" ".join(f"x{i}" for i in range(700)) + ".", "text", loc=1)]
    chunks, _ = run(blocks, "document")
    assert max(c.word_count for c in chunks) <= 800
    assert any(c.word_count > 550 for c in chunks)


def test_empty_section_makes_no_chunk():
    blocks = [Block("A", "heading", 1), Block("B", "heading", 1), Block(gen(0, 30), "text", loc=2)]
    chunks, open_path = run(blocks, "document")
    assert [c.heading_path for c in chunks] == ["B"]
    assert open_path == [(1, "B")]


def test_table_not_split():
    table = "\n".join(f"r{i} | " + " ".join(f"c{i}x{j}" for j in range(8)) for i in range(30))  # 300 words
    assert word_count(table) == 300
    blocks = [Block("S", "heading", 1), Block(gen(0, 100), "text", loc=1), Block(table, "table", loc=1),
              Block(gen(500, 100), "text", loc=2)]
    chunks, _ = run(blocks, "document")
    assert sum(table in c.text for c in chunks) == 1


def test_never_mid_sentence():
    for layout in ("document", "markdown", "text", "docx"):
        blocks = [Block("H", "heading", 1), Block(gen(0, 2000, 13), "text", loc=1, loc_end=1)]
        chunks, _ = run(blocks, layout)
        assert len(chunks) > 1
        assert all(c.text.rstrip().endswith(".") for c in chunks), layout


def test_never_mid_sentence_in_slides_and_around_atomic_blocks():
    """Prose ends at a full stop and atomic blocks at a whole line; only the R22 forced cuts are exempt."""
    # a slide with 20 body words and 900 words of notes in one paragraph (it is over 800 words)
    slide_blocks = [Block("Big", "heading", 1, loc=4), Block(gen(5000, 20), "text", loc=4), Block(gen(0, 900, 15), "notes", loc=4)]
    chunks, _ = run(slide_blocks, "slides")
    assert len(chunks) > 1
    assert all(c.text.rstrip().endswith(".") and (c.loc_start, c.loc_end) == (4, 4) for c in chunks)
    # a slide with a table that is over the word maximum: every cut is at a line end
    table = "\n".join(f"r{i} | " + " ".join(f"c{i}x{j}" for j in range(8)) + ";" for i in range(120))
    chunks, _ = run([Block("T", "heading", 1, loc=2), Block(gen(0, 30), "text", loc=2), Block(table, "table", loc=2)], "slides")
    assert len(chunks) > 1 and all(c.text.rstrip()[-1] in ".;" for c in chunks)
    for layout in ("document", "markdown", "text"):
        blocks = [Block(gen(0, 300, 12), "text", loc=1), Block(table, "code", loc=2, loc_end=121),
                  Block(gen(900, 300, 12), "text", loc=122)]
        chunks, _ = run(blocks, layout)
        assert all(c.text.rstrip()[-1] in ".;" for c in chunks), layout


def test_unpunctuated_transcript_is_cut_at_words_and_loses_nothing():
    text = " ".join(f"u{i}" for i in range(3000))
    chunks, _ = run([Block(text, "text", loc=1, loc_end=1)], "text")
    assert max(c.word_count for c in chunks) <= 500
    assert " ".join(c.text for c in chunks).split() == text.split()


# ---------- the embedding cap ----------

def test_embedding_text_never_exceeds_cap():
    code = "\n".join(f"{i:02d} " + "x" * 3000 for i in range(20))
    long_line = "y" * 20000  # no whitespace at all
    long_words = " ".join(f"{'abcdefghij'}{i:03d}" for i in range(1200)) + "."
    table = "\n".join(f"row{i} | " + "z" * 200 for i in range(100))
    cases = [
        ("document", [Block("H", "heading", 1), Block(code, "code", loc=1)]),
        ("document", [Block(long_line, "code", loc=1)]),
        ("document", [Block("H", "heading", 1), Block(long_words, "text", loc=1)]),
        ("slides", [Block("T", "heading", 1, loc=1), Block(table, "table", loc=1)]),
        ("text", [Block(long_words, "text", loc=1, loc_end=1)]),
        ("markdown", [Block("H", "heading", 1), Block(code, "code", loc=1, loc_end=20)]),
        ("docx", [Block("H", "heading", 1), Block(table, "table")]),
    ]
    for layout, blocks in cases:
        chunks, _ = run(blocks, layout, counter=by_chars)
        assert chunks, layout
        for c in chunks:
            assert by_chars(embedding_text("Trees.pdf", c)) <= MAX_EMBED_TOKENS, layout
    chunks, _ = run([Block("H", "heading", 1), Block(code, "code", loc=1)], "document", counter=by_chars)
    assert len(chunks) >= 20
    assert "".join(c.text for c in chunks).replace("\n", "") == code.replace("\n", "")


# ---------- docx ----------

def test_docx_small_doc_one_chunk():
    blocks = [Block("Intro", "heading", 1), Block(gen(0, 200), "text"), Block("Part", "heading", 2),
              Block(gen(300, 200), "text")]
    chunks, _ = run(blocks, "docx")
    assert len(chunks) == 1
    assert (chunks[0].heading_path, chunks[0].loc_kind, chunks[0].loc_start) == ("", "heading", None)
    assert "w0 " in chunks[0].text and "w499" in chunks[0].text


def test_docx_one_chunk_per_heading_when_large():
    blocks = []
    for k, name in enumerate("ABC"):
        blocks += [Block(name, "heading", 1), Block(gen(k * 1000, 400), "text")]
    chunks, _ = run(blocks, "docx")
    assert [c.heading_path for c in chunks] == ["A", "B", "C"]


def test_docx_section_over_800_split_without_overlap():
    blocks = [Block("A", "heading", 1), Block(gen(0, 1300), "text"), Block("B", "heading", 1), Block(gen(2000, 900), "text")]
    chunks, _ = run(blocks, "docx")
    assert len(chunks) >= 4
    seen: set[str] = set()
    for c in chunks:
        words = set(c.text.split())
        assert not words & seen
        seen |= words


# ---------- text / markdown / web ----------

def test_text_windows_overlap_15_percent():
    lines = [gen(i * 14, 14) for i in range(143)]  # one sentence per line, 2002 words
    block = Block("\n".join(lines), "text", loc=1, loc_end=143)
    chunks, _ = run([block], "text")
    assert len(chunks) >= 4
    assert all(c.loc_kind == "line" for c in chunks)
    for c in chunks[:-1]:
        assert 400 <= c.word_count <= 500
    for prev, nxt in zip(chunks, chunks[1:]):
        a, b = prev.text.split(), nxt.text.split()
        shared = len(set(a) & set(b))
        assert 50 <= shared <= 90
        assert b[:shared] == a[-shared:]
        assert nxt.loc_start <= prev.loc_end and nxt.loc_end > prev.loc_end and nxt.loc_start > prev.loc_start
    assert chunks[0].loc_start == 1 and chunks[0].loc_end < 143  # only the lines it covers
    assert chunks[-1].loc_end == 143


def test_markdown_sections_then_windows_with_line_kind():
    blocks = [Block("One", "heading", 1, loc=1), Block(gen(0, 50), "text", loc=2, loc_end=4),
              Block("Two", "heading", 1, loc=6), Block(gen(100, 50), "text", loc=7, loc_end=9)]
    chunks, _ = run(blocks, "markdown")
    assert [(c.heading_path, c.loc_kind, c.loc_start, c.loc_end) for c in chunks] == [
        ("One", "line", 2, 2), ("Two", "line", 7, 7)]


def test_web_passes_block_locations_through():
    blocks = [Block("Sec", "heading", 1, loc=3), Block(gen(0, 50), "text", loc=5, loc_end=9)]
    (c,), _ = run(blocks, "web")
    assert (c.loc_kind, c.loc_start, c.loc_end, c.heading_path) == ("heading", 5, 9, "Sec")


def test_notes_outside_slides_are_plain_text():
    chunks, _ = run([Block(gen(0, 30), "text", loc=1), Block("Remember this.", "notes", loc=2)], "document")
    assert "Speaker notes" not in chunks[0].text and "Remember this." in chunks[0].text


# ---------- headings across pieces ----------

def test_carry_headings_across_pieces():
    piece1 = [Block("Ch 3", "heading", 1, loc=1), Block("3.1 Gini", "heading", 2, loc=1), Block(gen(0, 60), "text", loc=1)]
    chunks, open_path = run(piece1)
    assert chunks[0].heading_path == "Ch 3 > 3.1 Gini"
    assert open_path == [(1, "Ch 3"), (2, "3.1 Gini")]

    piece2 = [Block(gen(100, 60), "text", loc=26), Block("3.2 Entropy", "heading", 2, loc=27), Block(gen(200, 60), "text", loc=27)]
    chunks, open_path = run(piece2, carry_headings=open_path, first_seq=len(chunks))
    assert [c.heading_path for c in chunks] == ["Ch 3 > 3.1 Gini", "Ch 3 > 3.2 Entropy"]
    assert open_path == [(1, "Ch 3"), (2, "3.2 Entropy")]


@pytest.mark.parametrize("carry", [[(1, "Ch 3"), (3, "3.1.1 Detail")], [[1, "Ch 3"], [3, "3.1.1 Detail"]]])
def test_carried_levels_may_skip(carry):
    blocks = [Block(gen(0, 40), "text", loc=1), Block("3.2 New", "heading", 2, loc=2), Block(gen(100, 40), "text", loc=2)]
    chunks, open_path = run(blocks, carry_headings=carry)
    assert [c.heading_path for c in chunks] == ["Ch 3 > 3.1.1 Detail", "Ch 3 > 3.2 New"]
    assert open_path == [(1, "Ch 3"), (2, "3.2 New")]


def test_same_level_heading_replaces_and_shallower_pops():
    blocks = [Block("A", "heading", 1), Block("A1", "heading", 2), Block("A2", "heading", 2), Block(gen(0, 30), "text"),
              Block("B", "heading", 1), Block(gen(50, 30), "text")]
    chunks, open_path = run(blocks)
    assert [c.heading_path for c in chunks] == ["A > A2", "B"]
    assert open_path == [(1, "B")]


# ---------- embedding text ----------

def test_embedding_text_format():
    c = ChunkDraft(0, "Gini is a measure.", "Ch 3 > 3.1 Gini", "page", 4, 4, 4)
    assert embedding_text("Trees.pdf", c) == "search_document: Trees.pdf > Ch 3 > 3.1 Gini\n\nGini is a measure."
    bare = ChunkDraft(0, "Body.", "", "page", 1, 1, 1)
    assert embedding_text("Trees.pdf", bare) == "search_document: Trees.pdf\n\nBody."


def test_embedding_text_is_prefix_plus_body():
    for hp in ("", "A > B"):
        c = ChunkDraft(0, "Body.", hp, "page", 1, 1, 1)
        assert embedding_text("T.pdf", c) == DOCUMENT_PREFIX + embedding_body("T.pdf", c)
        assert not embedding_body("T.pdf", c).startswith(DOCUMENT_PREFIX)


# ---------- general guarantees ----------

def test_seq_counts_from_first_seq():
    chunks, _ = run([Block(gen(0, 2000), "text", loc=1)], "text", first_seq=40)
    assert [c.seq for c in chunks] == list(range(40, 40 + len(chunks)))


@pytest.mark.parametrize("layout", LAYOUTS)
def test_no_text_lost_and_in_order(layout):
    """Every word of every block, headings included, is in a chunk's path or text, in order."""
    blocks, expected, n = [], [], 0
    for s in range(1, 5):
        blocks.append(Block(f"Head{s}x", "heading", 1, loc=s))
        expected.append(f"Head{s}x")
        if layout == "slides":  # a second heading on the slide must stay as text
            blocks.append(Block(f"Extra{s}y", "heading", 2, loc=s))
            expected.append(f"Extra{s}y")
        for kind, size in (("text", 300), ("table", 60), ("code", 40), ("formula", 3), ("text", 700), ("notes", 20)):
            text = gen(n, size)
            if kind in ("table", "code"):
                text = "\n".join(text[i:i + 60] for i in range(0, len(text), 60))
            blocks.append(Block(text, kind, loc=s, loc_end=s))
            expected += text.split()
            n += size
    chunks, _ = run(blocks, layout)
    got = " ".join(c.heading_path + " " + c.text for c in chunks).replace("Speaker notes:", "").replace(">", "").split()
    it = iter(got)
    assert all(w in it for w in expected), layout  # in-order subsequence (overlap repeats are fine)


def test_stray_headings_stay_in_the_text():
    # merged slides: later titles are text lines
    blocks = slide(1, "Alpha", 6) + slide(2, "Beta", 6, start=50) + slide(3, "Gamma", 40, start=100)
    (c,), _ = run(blocks, "slides")
    assert c.heading_path == "Alpha" and "\nBeta\n" in c.text.replace("\n\n", "\n") and "Gamma" in c.text
    assert "Alpha" not in c.text  # the path title is not repeated
    # a title-only divider slide followed by a content slide: both titles findable
    blocks = [Block("Part 2: Pruning", "heading", 1, loc=3), Block("Cost complexity", "heading", 1, loc=4),
              Block(gen(0, 30), "text", loc=4)]
    (c,), _ = run(blocks, "slides")
    assert c.heading_path == "Part 2: Pruning" and "Cost complexity" in c.text and (c.loc_start, c.loc_end) == (3, 4)
    # a second heading on one slide
    blocks = [Block("Main", "heading", 1, loc=1), Block("Side note", "heading", 2, loc=1), Block(gen(0, 40), "text", loc=1)]
    (c,), _ = run(blocks, "slides")
    assert c.heading_path == "Main" and c.text.startswith("Side note\n\n")
    # a last heading-only slide merges back and extends the range
    blocks = slide(1, "A", 30) + [Block("Questions?", "heading", 1, loc=2)]
    (c,), _ = run(blocks, "slides")
    assert (c.loc_start, c.loc_end) == (1, 2) and c.text.endswith("Questions?")


def test_single_title_only_slide_gives_one_chunk():
    (c,), _ = run([Block("Title only", "heading", 1, loc=1)], "slides")
    assert (c.text, c.heading_path, c.loc_start, c.loc_end) == ("Title only", "Title only", 1, 1)


def test_docx_whole_document_keeps_its_headings():
    blocks = [Block("Intro", "heading", 1), Block(gen(0, 20), "text"), Block("Details", "heading", 2), Block(gen(50, 20), "text")]
    (c,), _ = run(blocks, "docx")
    assert c.heading_path == "" and "Intro" in c.text and "\nDetails\n" in c.text.replace("\n\n", "\n")


@pytest.mark.parametrize("layout", ["markdown", "text", "document"])
def test_atomic_block_under_800_words_stays_whole(layout):
    code = "\n".join(" ".join(f"c{i}_{j}" for j in range(10)) for i in range(60))  # 600 words
    chunks, _ = run([Block(code, "code", loc=2, loc_end=61)], layout)
    assert len(chunks) == 1 and chunks[0].text == code


def test_atomic_block_over_800_words_is_cut_by_lines_with_own_line_numbers():
    code = "\n".join(" ".join(f"c{i}_{j}" for j in range(10)) for i in range(100))  # 1000 words on lines 11..110
    chunks, _ = run([Block(code, "code", loc=11, loc_end=110)], "markdown")
    assert len(chunks) > 1
    lines = [c.text.split("\n") for c in chunks]
    assert [x for ls in lines for x in ls] == code.split("\n")
    start = 11
    for c, ls in zip(chunks, lines):
        assert (c.loc_start, c.loc_end) == (start, start + len(ls) - 1)
        start += len(ls)


def test_unpunctuated_multiline_transcript_cites_its_own_lines():
    t = "\n".join(" ".join(f"u{i}_{j}" for j in range(10)) for i in range(300))
    chunks, _ = run([Block(t, "text", loc=1, loc_end=300)], "text")
    ranges = [(c.loc_start, c.loc_end) for c in chunks]
    assert len(set(ranges)) == len(ranges) > 1
    assert ranges[0][0] == 1 and ranges[-1][1] == 300
    assert all(a[1] < b[1] and a[0] < b[0] for a, b in zip(ranges, ranges[1:]))
    assert all(b[0] <= a[1] + 1 for a, b in zip(ranges, ranges[1:]))  # no gap between windows
    assert all("\n" in c.text for c in chunks) and max(c.word_count for c in chunks) <= 500


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_layout_stays_under_the_cap_with_prose(layout):
    blocks = [Block("H", "heading", 1, loc=1), Block(" ".join(f"abcdefghijkl{i}" for i in range(1500)) + ".", "text", loc=1)]
    chunks, _ = run(blocks, layout, counter=by_chars)
    assert all(by_chars(embedding_text("Trees.pdf", c)) <= MAX_EMBED_TOKENS for c in chunks)
    assert len(chunks) > 1
