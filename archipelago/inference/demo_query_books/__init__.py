"""Hardcoded demo-query book stack + availability + page links.

Spreadsheet: docs/demo_query_books.csv
doc_id values must match files under pdfs/ so Page/Split modes open real PDFs."""

from __future__ import annotations

import csv  # noqa: F401
from pathlib import Path  # noqa: F401
import re  # noqa: F401
from typing import Any  # noqa: F401
from urllib.parse import quote  # noqa: F401

from archipelago.inference.demo_query_books_data import DEMO_BOOK_ROWS  # noqa: F401

from .part01_query_matchers import (
    _CSV_PATH,
    _HOLDINGS_MARKER,
    _PDF_ROOT,
    _QUERY_MATCHERS,
    _ROWS,
    DOC_ID_ALIASES,
    _coerce_row,
    _load_rows,
    book_titles_phrase,
    books_for_query,
    citation_overlays_for_query,
    enrich_reply_with_books,
    format_availability_table,
    format_inline_page_links,
    match_demo_query_key,
    merge_demo_citations,
    page_view_href,
    resolve_doc_id,
)
from .part02_demo_passage_for_doc import (
    demo_passage_for_doc,
)

__all__ = [
    "DOC_ID_ALIASES",
    "_CSV_PATH",
    "_HOLDINGS_MARKER",
    "_PDF_ROOT",
    "_QUERY_MATCHERS",
    "_ROWS",
    "_coerce_row",
    "_load_rows",
    "book_titles_phrase",
    "books_for_query",
    "citation_overlays_for_query",
    "demo_passage_for_doc",
    "enrich_reply_with_books",
    "format_availability_table",
    "format_inline_page_links",
    "match_demo_query_key",
    "merge_demo_citations",
    "page_view_href",
    "resolve_doc_id",
]
