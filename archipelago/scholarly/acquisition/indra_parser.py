"""Parse permitted research PDFs with Indra while retaining page evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from archipelago.scholarly.acquisition.pdf_parser import PDFParser

MAX_OCR_PAGES = 40
OCR_THREADS = 4
MIN_PAGE_TEXT = 20


def indra_available() -> bool:
    """Report whether the local Indra package can be imported."""
    try:
        import indra_ocr  # noqa: F401
    except ImportError:
        return False
    return True


def parse_with_indra(pdf_path: str | Path, sha256: str) -> dict[str, Any]:
    """Read each page with Indra's text-layer/OCR auto mode."""
    import indra_ocr

    converter = indra_ocr.load(threads=OCR_THREADS, mode="auto")
    sections: dict[str, list[dict[str, Any]]] = {}
    pages: list[dict[str, Any]] = []
    section = "preamble"
    detector = PDFParser()
    for index, page in converter.convert(str(pdf_path), max_pages=MAX_OCR_PAGES):
        number = int(index) + 1
        text = str(page.text or "").strip()
        if len(text) < MIN_PAGE_TEXT:
            continue
        source = str(page.source)
        pages.append({"page": number, "text": text, "source": source})
        for block in page.blocks:
            if not isinstance(block, dict):
                continue
            block_text = str(block.get("text") or "").strip()
            if not block_text:
                continue
            # Indra can label a visible heading as plain text, especially in
            # two-column papers. The parser's short-heading check is safe to
            # run for every block and preserves the page-linked OCR text.
            section = detector._detect_section(block_text) or section
            sections.setdefault(section, []).append(
                {
                    "page": number,
                    "section": section,
                    "bbox": block.get("bbox"),
                    "text": block_text,
                    "ocr_source": source,
                    "char_start": 0,
                    "char_end": len(block_text),
                }
            )
    if not pages:
        raise ValueError("Indra returned no readable pages")
    return {
        "num_pages": len(pages),
        "artifact_sha256": sha256,
        "pages": pages,
        "sections": sections,
        "ocr_engine": "indra",
    }
