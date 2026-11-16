"""Builders for the small test files (decks, documents, PDFs); all text is written for the tests."""

import textwrap
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from reportlab.lib.pagesizes import A4
from reportlab.lib.pagesizes import landscape as to_landscape
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.pdfgen import canvas


def make_pptx(path: Path, slides: list[tuple[str, str, str]]) -> Path:
    """Each slide is (title, body, speaker notes); an empty notes string adds none."""
    prs = Presentation()
    for title, body, notes in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = body
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
    prs.save(str(path))
    return path


def make_docx(path: Path, paragraphs: list[tuple[int, str]]) -> Path:
    """Each item is (heading level, text); level 0 is a normal paragraph."""
    doc = Document()
    for level, text in paragraphs:
        if level:
            doc.add_heading(text, level=level)
        else:
            doc.add_paragraph(text)
    doc.save(str(path))
    return path


def make_pdf(path: Path, pages: list[str], landscape: bool = False) -> Path:
    """One page per string; the first line of each page is drawn large as a heading."""
    size = to_landscape(A4) if landscape else A4
    c = canvas.Canvas(str(path), pagesize=size)
    for text in pages:
        _draw_page(c, size, text)
        c.showPage()
    c.save()
    return path


def _draw_page(c: canvas.Canvas, size: tuple[float, float], text: str) -> None:
    y = size[1] - 70
    first, *rest = text.split("\n")
    c.setFont("Helvetica-Bold", 20)
    c.drawString(60, y, first)
    c.setFont("Helvetica", 11)
    for line in rest:
        for part in textwrap.wrap(line, 90) or [""]:
            y -= 16
            c.drawString(60, y, part)


def make_encrypted_pdf(path: Path, password: str = "secret") -> Path:
    c = canvas.Canvas(str(path), pagesize=A4, encrypt=StandardEncryption(password, canPrint=0))
    _draw_page(c, A4, "Locked\nThis page needs a password to open.")
    c.showPage()
    c.save()
    return path


def make_image_only_pdf(path: Path) -> Path:
    """A page that is one picture of text, so the PDF has no text layer."""
    img = Image.new("RGB", (800, 600), "white")
    ImageDraw.Draw(img).text((40, 40), "This is only pixels", fill="black", font=ImageFont.load_default(size=40))
    img.save(str(path), "PDF")
    return path


def make_image_table_pdf(path: Path, rows: list[list[str]]) -> Path:
    """One page: a real text heading and sentence, then a table drawn as a picture."""
    img = Image.new("RGB", (1400, 140 * len(rows) + 80), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=44)
    for r, row in enumerate(rows):
        for col, cell in enumerate(row):
            x, y = 40 + col * 440, 40 + r * 140
            draw.rectangle([x, y, x + 440, y + 140], outline="black", width=3)
            draw.text((x + 20, y + 45), cell, fill="black", font=font)
    png = path.with_suffix(".png")
    img.save(png)
    c = canvas.Canvas(str(path), pagesize=A4)
    _draw_page(c, A4, "Results\nThe table below was pasted in as a picture.")
    c.drawImage(str(png), 40, 300, width=500, height=500 * img.height / img.width)
    c.showPage()
    c.save()
    png.unlink()
    return path
