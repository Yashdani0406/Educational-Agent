"""Live Docling checks on real PDFs. Downloads models into data/models/docling the first time."""

import time

import pytest
from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
from fixtures import make_image_table_pdf, make_pdf

from eduagent.config import Settings
from eduagent.kb.docling_parser import DoclingParser

pytestmark = pytest.mark.models

SENTENCE = "A decision tree splits the data into smaller groups by asking one question at a time about a feature."


@pytest.fixture(scope="module")
def parser():
    return DoclingParser(Settings(_env_file=None))


@pytest.fixture
def ocr_calls(monkeypatch):
    """Counts how many picture regions the OCR engine is asked to read."""
    calls = []
    original = RapidOcrModel._read

    def spy(self, image):
        calls.append(image.size)
        return original(self, image)

    monkeypatch.setattr(RapidOcrModel, "_read", spy)
    return calls


def test_pdf_pages_and_headings(parser, tmp_path, ocr_calls):
    pdf = make_pdf(tmp_path / "book.pdf", [f"Chapter {n}\n{SENTENCE}\n{SENTENCE}" for n in range(1, 7)])
    start = time.perf_counter()
    blocks = parser.convert(pdf, "pdf")
    per_page = (time.perf_counter() - start) / 6
    print(f"\nLIVE text PDF: {per_page:.1f} s/page (6 pages, first call includes loading the models)")
    headings = {b.text: b.loc for b in blocks if b.kind == "heading"}
    assert headings == {f"Chapter {n}": n for n in range(1, 7)}
    assert {b.loc for b in blocks if b.kind == "text"} == set(range(1, 7))
    # a second run shows the steady-state speed, and the pages being all text means no OCR at all
    start = time.perf_counter()
    parser.convert(pdf, "pdf")
    print(f"LIVE text PDF steady state: {(time.perf_counter() - start) / 6:.1f} s/page")


def test_text_page_not_ocrd(parser, tmp_path, ocr_calls):
    pdf = make_pdf(tmp_path / "text.pdf", [f"Part {n}\n{SENTENCE}" for n in range(1, 4)])
    parser.convert(pdf, "pdf")
    assert ocr_calls == []  # the OCR engine was never asked to read a region


def test_image_table_is_ocrd(parser, tmp_path, ocr_calls):
    rows = [["Measure", "Value"], ["Gini", "0.42"], ["Entropy", "0.91"]]
    pdf = make_image_table_pdf(tmp_path / "table.pdf", rows)
    blocks = parser.convert(pdf, "pdf")
    print("\nLIVE image table blocks:", [(b.kind, b.text[:80]) for b in blocks])
    assert ocr_calls, "the picture region should have been OCR'd"
    text = " ".join(b.text for b in blocks)
    for word in ("Gini", "Entropy", "0.42", "0.91"):
        assert word in text


def test_page_range_piece(parser, tmp_path):
    pdf = make_pdf(tmp_path / "long.pdf", [f"Page {n}\n{SENTENCE}" for n in range(1, 31)])
    blocks = parser.convert(pdf, "pdf", page_range=(26, 30))
    assert {b.loc for b in blocks} == set(range(26, 31))
    assert {b.text for b in blocks if b.kind == "heading"} == {f"Page {n}" for n in range(26, 31)}


def test_formula_page_timing(parser, tmp_path):
    pdf = make_pdf(
        tmp_path / "math.pdf",
        ["Impurity\nThe Gini impurity of a node is given by the formula below.\n\nG = 1 - sum_i (p_i)^2\n\nWhere p_i is the share of class i in the node."],
    )
    start = time.perf_counter()
    blocks = parser.convert(pdf, "pdf")
    print(f"\nLIVE formula page: {time.perf_counter() - start:.1f} s")
    print("LIVE formula page blocks:", [(b.kind, b.text[:80]) for b in blocks])
    assert blocks
