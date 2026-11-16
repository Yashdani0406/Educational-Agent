"""Quick looks at a file (first words, page count, orientation) that fail fast before the slow parser runs."""

import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from eduagent.db.files import FileKind, Layout
from eduagent.kb.types import IngestError

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Takes a quick first look at an uploaded file (opening words, page count, slide or portrait shape) and rejects empty, locked or fake files with a plain reason."

PIECE_PAGES = 25
PEEK_WORDS = 300
_SAMPLE_PAGES = 5
_MIN_TEXT_CHARS = 20

_NO_TEXT = (
    "This PDF has no text layer (it looks like a scan). Scanned documents aren't supported; "
    "if you have the original slides or a text PDF, upload that instead."
)
_LOCKED = "This PDF is password-protected. Remove the password (or print it to a new PDF) and upload it again."
_BAD_PDF = "This file isn't a readable PDF. Try opening and re-saving it, then upload it again."
_BAD_OFFICE = {
    "pptx": "This file isn't a readable PowerPoint presentation. Try opening and re-saving it as .pptx, then upload it again.",
    "docx": "This file isn't a readable Word document. Try opening and re-saving it as .docx, then upload it again.",
}
_EMPTY = "This file is empty."


@dataclass(frozen=True)
class PeekInfo:
    text: str  # first ~300 words
    pages: int | None  # pages or slides; None for plain text
    landscape: bool | None  # None when the type has no page shape


def _first_words(text: str) -> str:
    return " ".join(text.split()[:PEEK_WORDS])


def _open_pdf(path: Path) -> pdfium.PdfDocument:
    try:
        return pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as e:
        if e.err_code == pdfium_c.FPDF_ERR_PASSWORD:
            raise IngestError(_LOCKED) from e
        raise IngestError(_BAD_PDF) from e


def _pdf_scan(path: Path) -> tuple[int, bool, str]:
    """Return (page count, most pages landscape, text of the first pages); fail on no text layer."""
    pdf = _open_pdf(path)
    try:
        count = len(pdf)
        if count == 0:
            raise IngestError(_BAD_PDF)
        wide = sum(1 for i in range(count) if pdf[i].get_size()[0] > pdf[i].get_size()[1])
        text = ""
        for i in range(count):
            text += pdf[i].get_textpage().get_text_range() + "\n"
            if i + 1 >= _SAMPLE_PAGES and len(text.split()) >= PEEK_WORDS:
                break
            if i + 1 >= _SAMPLE_PAGES and len("".join(text.split())) <= _MIN_TEXT_CHARS:
                break
        if len("".join(text.split())) <= _MIN_TEXT_CHARS:
            raise IngestError(_NO_TEXT)
        return count, wide * 2 > count, text
    except pdfium.PdfiumError as e:
        raise IngestError(_BAD_PDF) from e
    finally:
        pdf.close()


def plan_pdf(path: Path) -> tuple[Layout, int, list[tuple[int, int]]]:
    """Layout, page count and 25-page ranges, using only pypdfium2."""
    count, landscape, _ = _pdf_scan(path)
    pieces = [(start, min(start + PIECE_PAGES - 1, count)) for start in range(1, count + 1, PIECE_PAGES)]
    return ("slides" if landscape else "document"), count, pieces


def _peek_pptx(path: Path) -> PeekInfo:
    from pptx import Presentation
    from pptx.exc import PackageNotFoundError

    try:
        prs = Presentation(str(path))
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError, etree.LxmlError, SyntaxError) as e:
        raise IngestError(_BAD_OFFICE["pptx"]) from e
    if len(prs.slides) == 0:
        raise IngestError("This presentation has no slides.")
    parts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
        if len(" ".join(parts).split()) >= PEEK_WORDS:
            break
    text = _first_words(" ".join(parts))
    if not text:
        raise IngestError("This presentation has no text on its slides.")
    return PeekInfo(text, len(prs.slides), prs.slide_width > prs.slide_height)


def _peek_docx(path: Path) -> PeekInfo:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    try:
        doc = Document(str(path))
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError, etree.LxmlError, SyntaxError) as e:
        raise IngestError(_BAD_OFFICE["docx"]) from e
    text = _first_words(" ".join(p.text for p in doc.paragraphs))
    if not text:
        raise IngestError("This document has no text.")
    section = doc.sections[0] if doc.sections else None
    landscape = bool(section and section.page_width and section.page_height and section.page_width > section.page_height)
    return PeekInfo(text, None, landscape)


def peek(path: Path, kind: FileKind) -> PeekInfo:
    """First ~300 words plus page count and shape; IngestError for empty, locked or fake files."""
    if path.stat().st_size == 0:
        raise IngestError(_EMPTY)
    if kind == "pdf":
        count, landscape, text = _pdf_scan(path)
        return PeekInfo(_first_words(text), count, landscape)
    if kind in ("pptx", "docx"):
        try:
            return _peek_pptx(path) if kind == "pptx" else _peek_docx(path)
        except (etree.LxmlError, SyntaxError) as e:  # parts are parsed lazily, so a broken slide shows up here
            raise IngestError(_BAD_OFFICE[kind]) from e
    text = _first_words(path.read_text(encoding="utf-8", errors="replace"))
    if not text:
        raise IngestError(_EMPTY)
    return PeekInfo(text, None, None)
