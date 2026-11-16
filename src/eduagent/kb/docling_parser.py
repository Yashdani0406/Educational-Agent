"""Reads PDF, PowerPoint and Word files with Docling into blocks for the chunker."""

import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from docling_core.types.doc.document import (
    CodeItem,
    ContentLayer,
    DoclingDocument,
    FormulaItem,
    SectionHeaderItem,
    TableItem,
    TextItem,
    TitleItem,
)

from eduagent.config import Settings
from eduagent.db.files import FileKind
from eduagent.kb.models_dir import configure_model_dirs
from eduagent.kb.types import Block, IngestError

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Turns PDFs, PowerPoint decks and Word files into headings, text, tables, code, formulas and speaker notes, reading text inside pictures but not re-reading pages that already have text."

FORMULA_MARKER = "[formula, see {where} {n}]"
_NOT_DECODED = "<!-- formula-not-decoded -->"
_MODELS_READY = ".ready"
_RAPIDOCR_SPEC = "onnxruntime:en"
_UNREADABLE = "This file couldn't be read. Try opening and re-saving it, then upload it again."


_DOCX_MARKER = "[formula, see the original document]"
_DOWNLOAD_FAILED = "Couldn't download the PDF reading models. Check the internet connection and retry this file."


def _pages(item) -> tuple[int | None, int | None]:
    """First and last page an item touches (an item can span pages)."""
    numbers = [p.page_no for p in item.prov]
    return (min(numbers), max(numbers)) if numbers else (None, None)


def docling_blocks(doc: DoclingDocument, *, where: Literal["page", "slide", "document"]) -> list[Block]:
    """Convert a Docling document, in reading order, into blocks (speaker notes included)."""
    blocks: list[Block] = []
    layers = {ContentLayer.BODY, ContentLayer.NOTES}
    for item, _ in doc.iterate_items(included_content_layers=layers, traverse_pictures=True):
        loc, loc_end = _pages(item)
        text = ""
        kind: Literal["heading", "text", "table", "code", "formula", "notes"] = "text"
        level = 0
        if isinstance(item, TableItem):
            text, kind = item.export_to_markdown(doc).strip(), "table"
        elif isinstance(item, TextItem):
            text = item.text.strip()
            if item.content_layer == ContentLayer.NOTES:
                kind = "notes"
            elif isinstance(item, TitleItem):
                kind, level = "heading", 1
            elif isinstance(item, SectionHeaderItem):
                kind, level = "heading", item.level
            elif isinstance(item, CodeItem):
                kind = "code"
            elif isinstance(item, FormulaItem):
                kind = "formula"
                if not text or text == _NOT_DECODED:
                    if where == "document":  # Word files have no page or slide numbers
                        text = _DOCX_MARKER
                    else:
                        text = FORMULA_MARKER.format(where=where, n=loc if loc is not None else "?")
        if text:
            blocks.append(Block(text, kind, level=level, loc=loc, loc_end=loc_end))
    return blocks


class DoclingParser:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._converter: "DocumentConverter | None" = None
        self._lock = threading.Lock()

    def _models_dir(self) -> Path:
        return self._settings.models_dir / "docling"

    def _ensure_models(self) -> None:
        """Fetch the PDF models once; the marker records what was fetched so a later setting change fetches the rest."""
        folder = self._models_dir()
        marker = folder / _MODELS_READY
        try:
            have = set(json.loads(marker.read_text()))
        except (OSError, ValueError, TypeError):
            have = set()
        want = {"base"} | ({"formula"} if self._settings.formula_enrichment else set())
        if want <= have:
            return
        from docling.utils.model_downloader import download_models

        log.info("Downloading Docling models into %s (%s)", folder, ", ".join(sorted(want - have)))
        folder.mkdir(parents=True, exist_ok=True)
        base = "base" not in have
        try:
            download_models(
                folder,
                with_layout=base,
                with_tableformer=base,
                with_rapidocr=base,
                rapidocr_models=[_RAPIDOCR_SPEC] if base else None,
                with_picture_classifier=False,
                with_code_formula="formula" in want - have,
            )
        except Exception as e:  # network, Hugging Face or disk errors; the type is enough for the log
            log.warning("Docling model download failed: %s", type(e).__name__)
            raise IngestError(_DOWNLOAD_FAILED) from e
        marker.write_text(json.dumps(sorted(have | want)))

    def _build(self) -> "DocumentConverter":
        self._models_dir().mkdir(parents=True, exist_ok=True)  # Docling insists the folder exists
        import torch
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import OcrMode, PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        threads = self._settings.ingest_threads
        torch.set_num_threads(threads)
        options = PdfPipelineOptions(
            artifacts_path=self._models_dir(),
            do_ocr=True,
            # only pictures and bitmaps are OCR'd; regions that already carry PDF text are skipped
            ocr_options=RapidOcrOptions(lang=["en"], mode=OcrMode.PDF_AWARE_LAYOUT_REGIONS),
            do_table_structure=True,
            do_formula_enrichment=self._settings.formula_enrichment,
            accelerator_options=AcceleratorOptions(num_threads=threads, device="cpu"),
        )
        return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})

    def convert(self, path: Path, kind: FileKind, page_range: tuple[int, int] | None = None) -> list[Block]:
        """Parse one file (or pages `page_range`, 1-based inclusive, of a PDF) into blocks."""
        from docling.datamodel.base_models import ConversionStatus
        from docling.exceptions import ConversionError

        with self._lock:
            configure_model_dirs(self._settings)  # before any model library is imported
            if kind == "pdf":
                self._ensure_models()
            if self._converter is None:
                self._converter = self._build()
            try:
                if page_range is not None:
                    result = self._converter.convert(path, page_range=page_range)
                else:
                    result = self._converter.convert(path)
            except (ConversionError, RuntimeError) as e:  # Docling wraps most pipeline failures in RuntimeError
                log.warning("Docling could not read %s (%s)", path.name, type(e).__name__)
                raise IngestError(_UNREADABLE) from e
        if result.status != ConversionStatus.SUCCESS:
            log.warning("Docling read %s only partly (%s, %d errors)", path.name, result.status.value, len(result.errors))
        where = {"pdf": "page", "pptx": "slide"}.get(kind, "document")
        return docling_blocks(result.document, where=where)
