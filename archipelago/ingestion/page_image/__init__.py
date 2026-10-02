"""Scanned page-image prefill for librarian ingestion.

Lets a librarian click an image of a book's index (table of contents) or
content page and auto-populate the ingestion record, resolving the exact
verified source page from the title/ISBN that was read off the page.
"""
from __future__ import annotations

from archipelago.ingestion.page_image.part01_ocr import (
    IMAGE_FORMATS,
    OCRUnavailable,
    is_supported_image,
    ocr_available,
    ocr_image_bytes,
    ocr_text_blocks,
)
from archipelago.ingestion.page_image.part02_parse import (
    PageExtraction,
    extract_page_fields,
    extract_isbn_field,
    extract_publisher,
    extract_toc,
    extract_year,
)
from archipelago.ingestion.page_image.part03_prefill import (
    MAX_SUGGESTIONS,
    build_prefill,
    extract_page_from_image,
    extract_page_from_text,
)

__all__ = [
    "IMAGE_FORMATS",
    "MAX_SUGGESTIONS",
    "OCRUnavailable",
    "PageExtraction",
    "build_prefill",
    "extract_isbn_field",
    "extract_page_fields",
    "extract_page_from_image",
    "extract_page_from_text",
    "extract_publisher",
    "extract_toc",
    "extract_year",
    "is_supported_image",
    "ocr_available",
    "ocr_image_bytes",
    "ocr_text_blocks",
]
