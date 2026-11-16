import pytest
from docling_core.types.doc import BoundingBox, DocItemLabel, DoclingDocument, ProvenanceItem, TableCell, TableData
from docling_core.types.doc.document import ContentLayer

from eduagent.config import Settings
from eduagent.kb.docling_parser import FORMULA_MARKER, DoclingParser, docling_blocks
from eduagent.kb.types import Block
from fixtures import make_docx, make_pptx


@pytest.fixture(autouse=True)
def restore_model_env(monkeypatch):
    """DoclingParser points these at its models folder; put them back after each test."""
    for name in ("HF_HOME", "FASTEMBED_CACHE_PATH", "DOCLING_ARTIFACTS_PATH", "HF_HUB_DISABLE_SYMLINKS_WARNING"):
        monkeypatch.setenv(name, "")


def prov(page: int) -> ProvenanceItem:
    return ProvenanceItem(page_no=page, bbox=BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, 1))


def cell(text, r, c, header=False):
    return TableCell(
        text=text, start_row_offset_idx=r, end_row_offset_idx=r + 1,
        start_col_offset_idx=c, end_col_offset_idx=c + 1, column_header=header,
    )


def test_blocks_from_built_document():
    doc = DoclingDocument(name="t")
    doc.add_title("Intro to trees", prov=prov(1))
    doc.add_heading("Splitting", level=2, prov=prov(2))
    doc.add_text(DocItemLabel.TEXT, "A tree splits the data.", prov=prov(3))
    cells = [cell("a", 0, 0, True), cell("b", 0, 1, True), cell("1", 1, 0), cell("2", 1, 1)]
    doc.add_table(data=TableData(num_rows=2, num_cols=2, table_cells=cells), prov=prov(3))
    doc.add_code("x = 1", prov=prov(3))
    doc.add_formula("E=mc^2", prov=prov(4))
    doc.add_formula("<!-- formula-not-decoded -->", prov=prov(4))
    doc.add_formula("", prov=prov(5))
    doc.add_text(DocItemLabel.TEXT, "Remember this.", prov=prov(5), content_layer=ContentLayer.NOTES)
    blocks = docling_blocks(doc, where="page")
    assert [(b.kind, b.level, b.loc) for b in blocks] == [
        ("heading", 1, 1), ("heading", 2, 2), ("text", 0, 3), ("table", 0, 3), ("code", 0, 3),
        ("formula", 0, 4), ("formula", 0, 4), ("formula", 0, 5), ("notes", 0, 5),
    ]
    assert blocks[0].text == "Intro to trees"
    rows = [[c.strip() for c in line.strip("|").split("|")] for line in blocks[3].text.splitlines()]
    assert rows[0] == ["a", "b"] and rows[2] == ["1", "2"]
    assert blocks[5] == Block("E=mc^2", "formula", loc=4, loc_end=4)
    assert blocks[6].text == "[formula, see page 4]" == FORMULA_MARKER.format(where="page", n=4)
    assert docling_blocks(doc, where="slide")[6].text == "[formula, see slide 4]"


def test_pptx_real_docling(tmp_path):
    path = make_pptx(
        tmp_path / "deck.pptx",
        [
            ("Trees overview", "Trees split data into groups", "Mention the weather example"),
            ("Gini impurity", "Gini measures how mixed a node is", "Work one example on the board"),
            ("Pruning", "Pruning stops overfitting", "Ask about depth limits"),
        ],
    )
    blocks = DoclingParser(Settings(_env_file=None, models_dir=tmp_path / "m")).convert(path, "pptx")
    assert sorted({b.loc for b in blocks}) == [1, 2, 3]
    notes = [b for b in blocks if b.kind == "notes"]
    assert [(b.loc, b.text) for b in notes] == [
        (1, "Mention the weather example"), (2, "Work one example on the board"), (3, "Ask about depth limits"),
    ]
    assert any(b.loc == 2 and b.kind == "heading" and b.text == "Gini impurity" for b in blocks)
    assert any(b.loc == 3 and b.kind == "text" and "overfitting" in b.text for b in blocks)


def test_docx_real_docling(tmp_path):
    path = make_docx(
        tmp_path / "notes.docx",
        [(1, "Ensembles"), (0, "Ensembles combine models."), (2, "Bagging"), (0, "Bagging averages many trees.")],
    )
    blocks = DoclingParser(Settings(_env_file=None, models_dir=tmp_path / "m")).convert(path, "docx")
    assert [(b.kind, b.level, b.text) for b in blocks if b.kind == "heading"] == [
        ("heading", 1, "Ensembles"), ("heading", 2, "Bagging"),
    ]
    assert [b.text for b in blocks if b.kind == "text"] == ["Ensembles combine models.", "Bagging averages many trees."]
