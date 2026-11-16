import pytest

from eduagent.kb.peek import PIECE_PAGES, PeekInfo, peek, plan_pdf
from eduagent.kb.types import IngestError
from kb_fixtures import (
    break_zip_member, make_docx, make_empty_pptx, make_encrypted_pdf, make_image_only_pdf, make_pdf, make_pptx,
)

NO_TEXT = (
    "This PDF has no text layer (it looks like a scan). Scanned documents aren't supported; "
    "if you have the original slides or a text PDF, upload that instead."
)


def test_plan_pdf_layout_and_pieces(tmp_path):
    assert PIECE_PAGES == 25
    slides = make_pdf(tmp_path / "s.pdf", ["Slide one\nwords here"] * 3, landscape=True)
    assert plan_pdf(slides) == ("slides", 3, [(1, 3)])
    book = make_pdf(tmp_path / "b.pdf", [f"Page {i}\nsome real text on the page" for i in range(60)])
    assert plan_pdf(book) == ("document", 60, [(1, 25), (26, 50), (51, 60)])


def test_image_only_pdf_fails_plain(tmp_path):
    path = make_image_only_pdf(tmp_path / "scan.pdf")
    with pytest.raises(IngestError) as e:
        plan_pdf(path)
    assert e.value.user_message == NO_TEXT
    with pytest.raises(IngestError) as e:
        peek(path, "pdf")
    assert e.value.user_message == NO_TEXT


def test_encrypted_pdf_plain_reason(tmp_path):
    path = make_encrypted_pdf(tmp_path / "locked.pdf")
    expected = "This PDF is password-protected. Remove the password (or print it to a new PDF) and upload it again."
    for call in (lambda: plan_pdf(path), lambda: peek(path, "pdf")):
        with pytest.raises(IngestError) as e:
            call()
        assert e.value.user_message == expected


def test_not_really_a_pdf(tmp_path):
    path = tmp_path / "page.pdf"
    path.write_bytes(b"<html><body>Not a pdf</body></html>")
    expected = "This file isn't a readable PDF. Try opening and re-saving it, then upload it again."
    for call in (lambda: plan_pdf(path), lambda: peek(path, "pdf")):
        with pytest.raises(IngestError) as e:
            call()
        assert e.value.user_message == expected


def test_peek_title_slide(tmp_path):
    path = make_pptx(tmp_path / "three.pptx", [("Module 3: Decision Trees", "Splitting and impurity", "")] * 3)
    info = peek(path, "pptx")
    assert isinstance(info, PeekInfo)
    assert info.text.startswith("Module 3: Decision Trees")
    assert info.pages == 3 and info.landscape is True


def test_peek_limits_words(tmp_path):
    path = tmp_path / "long.txt"
    path.write_text("word " * 1000)
    info = peek(path, "txt")
    assert len(info.text.split()) == 300 and info.pages is None and info.landscape is None


def test_peek_docx_and_pdf(tmp_path):
    docx = make_docx(tmp_path / "n.docx", [(1, "Ensembles"), (0, "Models combine.")])
    assert peek(docx, "docx").text.startswith("Ensembles")
    pdf = make_pdf(tmp_path / "b.pdf", ["Chapter one\nreal words"] * 2)
    info = peek(pdf, "pdf")
    assert info.text.startswith("Chapter one") and info.pages == 2 and info.landscape is False


def fails_with(call, message):
    with pytest.raises(IngestError) as e:
        call()
    assert e.value.user_message == message


EMPTY = "This file is empty."
BAD_PPTX = "This file isn't a readable PowerPoint presentation. Try opening and re-saving it as .pptx, then upload it again."
BAD_DOCX = "This file isn't a readable Word document. Try opening and re-saving it as .docx, then upload it again."


@pytest.mark.parametrize("kind", ["pptx", "docx", "pdf", "txt"])
def test_empty_file_is_rejected(tmp_path, kind):
    path = tmp_path / f"empty.{kind}"
    path.write_bytes(b"")
    fails_with(lambda: peek(path, kind), EMPTY)


@pytest.mark.parametrize("kind,message", [("pptx", BAD_PPTX), ("docx", BAD_DOCX)])
def test_not_really_office_file(tmp_path, kind, message):
    path = tmp_path / f"fake.{kind}"
    path.write_bytes(b"<html>nope</html>")
    fails_with(lambda: peek(path, kind), message)


def test_truncated_docx_xml(tmp_path):
    path = break_zip_member(make_docx(tmp_path / "d.docx", [(1, "Title"), (0, "Some body text here.")]), "word/document.xml")
    fails_with(lambda: peek(path, "docx"), BAD_DOCX)


def test_truncated_pptx_xml(tmp_path):
    path = break_zip_member(make_pptx(tmp_path / "p.pptx", [("Title", "Body words", "")]), "ppt/slides/slide1.xml")
    fails_with(lambda: peek(path, "pptx"), BAD_PPTX)


def test_pptx_with_no_slides(tmp_path):
    fails_with(lambda: peek(make_empty_pptx(tmp_path / "none.pptx"), "pptx"), "This presentation has no slides.")
