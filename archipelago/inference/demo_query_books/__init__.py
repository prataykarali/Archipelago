"""Hardcoded demo-query book stack + availability + page links.

Spreadsheet: docs/demo_query_books.csv
doc_id values must match files under pdfs/ so Page/Split modes open real PDFs."""
from __future__ import annotations

import csv  # noqa: F401
import re  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any  # noqa: F401
from urllib.parse import quote  # noqa: F401
from archipelago.inference.demo_query_books_data import DEMO_BOOK_ROWS  # noqa: F401

from .part01_query_matchers import (  # noqa: F401
    _QUERY_MATCHERS,
    DOC_ID_ALIASES,
    _CSV_PATH,
    _PDF_ROOT,
    resolve_doc_id,
    _coerce_row,
    _load_rows,
    _ROWS,
    match_demo_query_key,
    books_for_query,
    book_titles_phrase,
    page_view_href,
    format_availability_table,
    format_inline_page_links,
    _HOLDINGS_MARKER,
    enrich_reply_with_books,
    citation_overlays_for_query,
    merge_demo_citations,
)
from .part02_demo_passage_for_doc import (  # noqa: F401
    demo_passage_for_doc,
)

__all__ = ["_QUERY_MATCHERS", "DOC_ID_ALIASES", "_CSV_PATH", "_PDF_ROOT", "resolve_doc_id", "_coerce_row", "_load_rows", "_ROWS", "match_demo_query_key", "books_for_query", "book_titles_phrase", "page_view_href", "format_availability_table", "format_inline_page_links", "_HOLDINGS_MARKER", "enrich_reply_with_books", "citation_overlays_for_query", "merge_demo_citations", "demo_passage_for_doc"]
