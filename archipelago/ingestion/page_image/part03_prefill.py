"""Page-image prefill: scanned index/content page → populated ingestion record.

Flow (all local, no external AI call):

    librarian clicks an image of the book's index or content page
        ↓ local OCR (Tesseract)
        ↓ field extraction (title, author, ISBN, publisher, year, edition, TOC)
        ↓ mention lookup against every indexed source
        ↓ prefill payload with the EXACT verified source URL
"""
from __future__ import annotations

import logging
from typing import Any

from archipelago.ingestion.mention import MentionMatch, MentionResult, mention_book, prefill_from_match
from archipelago.ingestion.page_image.part01_ocr import (
    OCRUnavailable,
    group_lines,
    is_supported_image,
    line_text,
    ocr_available,
    ocr_image_bytes,
    ocr_text_blocks,
)
from archipelago.ingestion.page_image.part02_parse import (
    PageExtraction,
    extract_page_fields,
    mean_confidence,
)

logger = logging.getLogger("archipelago.ingestion.page_image")

MAX_SUGGESTIONS = 5
MIN_USEFUL_FIELD_HITS = 2
IMAGE_FORMATS = ("PNG", "JPEG", "TIFF", "BMP", "WEBP")

__all__ = [
    "MAX_SUGGESTIONS",
    "IMAGE_FORMATS",
    "OCRUnavailable",
    "PageExtraction",
    "is_supported_image",
    "ocr_available",
    "extract_page_from_image",
    "extract_page_from_text",
    "build_prefill",
]


def _lines_from_blocks(blocks: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Reconstruct page text and ordered lines from positioned OCR words."""
    grouped = group_lines(blocks)
    lines = [line_text(words) for words in grouped]
    return "\n".join(lines), lines


def extract_page_from_image(data: bytes) -> PageExtraction:
    """OCR an index/content page image and extract its fields."""
    blocks = ocr_text_blocks(data)
    text, lines = _lines_from_blocks(blocks)
    if not text.strip():
        raise OCRUnavailable(
            "No text was recognised on that image. Try a sharper or larger scan."
        )
    extraction = extract_page_fields(text, lines=lines)
    extraction.ocr_confidence = mean_confidence(blocks)
    return extraction


def extract_page_from_text(text: str) -> PageExtraction:
    """Extract fields from pasted page text (no OCR needed)."""
    return extract_page_fields(text, lines=(text or "").splitlines())


def _search_queries(extraction: PageExtraction) -> list[str]:
    """Build mention-search queries, strongest signal first."""
    queries: list[str] = []
    if extraction.isbn:
        queries.append(extraction.isbn)
    if extraction.title:
        queries.append(extraction.title)
    return queries


def _merge_matches(results: list[MentionResult]) -> list[MentionMatch]:
    """Flatten several mention lookups, strongest first, without duplicates."""
    seen: set[str] = set()
    out: list[MentionMatch] = []
    for result in results:
        for match in result.matches:
            key = f"{match.match_kind}:{match.title}".lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(match)
    out.sort(key=lambda m: m.confidence, reverse=True)
    return out[:MAX_SUGGESTIONS]


def build_prefill(
    extraction: PageExtraction,
    filename: str | None = None,
) -> dict[str, Any]:
    """Turn a page extraction into a librarian-ready prefill payload.

    Resolved page fields are trusted; source metadata is only added when the
    mention lookup actually found a real indexed record.
    """
    fields: dict[str, Any] = {}
    if extraction.title:
        fields["title"] = extraction.title
    if extraction.author:
        fields["author"] = extraction.author
    if extraction.isbn:
        fields["isbn"] = extraction.isbn
    if extraction.publisher:
        fields["publisher"] = extraction.publisher
    if extraction.year:
        fields["year"] = extraction.year
    if extraction.edition:
        fields["edition"] = extraction.edition
    if extraction.toc_entries:
        fields["table_of_contents"] = extraction.toc_entries
        fields["chapter_count"] = len(extraction.toc_entries)
    if extraction.is_index_page:
        fields["page_kind"] = "index"
    elif extraction.is_content_page:
        fields["page_kind"] = "content"

    matches: list[MentionMatch] = []
    no_match_reason = ""
    searched_queries: list[str] = []
    if _search_queries(extraction):
        results = []
        for query in _search_queries(extraction):
            searched_queries.append(query)
            results.append(mention_book(query))
        matches = _merge_matches(results)
        if not matches:
            no_match_reason = (
                "This page's title/ISBN is not in any indexed source. "
                "Nothing was invented — add a catalogue row or upload the file."
            )
    else:
        no_match_reason = "No title or ISBN was recognised to search with."

    # A recognised top match supplies the exact verified source page. Its
    # bibliographic fields are only adopted when the match is trustworthy, so a
    # fuzzy title hit can never overwrite details read off the page.
    suggested = prefill_from_match(matches[0]) if matches else {}
    for key in ("title", "author", "isbn", "source_url", "doc_id", "domain", "kind", "license_mode"):
        if not fields.get(key) and suggested.get(key):
            fields[key] = suggested[key]

    untrusted = bool(matches) and not suggested.get("metadata_trusted", False)
    if untrusted:
        warnings = list(extraction.warnings)
        warnings.append(
            "Top title match is not an exact identifier match — confirm the "
            "suggested author/details before ingesting."
        )
        extraction.warnings = warnings

    useful = len([k for k in ("title", "author", "isbn", "publisher", "year") if fields.get(k)])

    return {
        "success": useful >= MIN_USEFUL_FIELD_HITS or bool(matches),
        "source": "page_image" if ocr_available() else "page_text",
        "filename": filename or "",
        "ocr_available": ocr_available(),
        "ocr_confidence": extraction.ocr_confidence,
        "is_index_page": extraction.is_index_page,
        "is_content_page": extraction.is_content_page,
        "fields": fields,
        "matched_sources": [m.to_dict() for m in matches],
        "top_match_trusted": suggested.get("metadata_trusted", False),
        "suggested_fields": suggested.get("suggested_fields", {}),
        "searched_queries": searched_queries,
        "no_match_reason": no_match_reason,
        "warnings": extraction.warnings,
        # Without a licensed file we never assume full-text extraction rights.
        "suggested_license_mode": "metadata_only"
        if not any(m.doc_id.endswith(".pdf") for m in matches)
        else "full",
    }
