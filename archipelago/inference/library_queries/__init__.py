"""library_queries.py — Cypher queries, metadata lookups, and rich library responses."""
from __future__ import annotations

import importlib  # noqa: F401
import re  # noqa: F401
from typing import Any  # noqa: F401

import kuzu  # noqa: F401
from thefuzz import fuzz  # noqa: F401

from archipelago.inference import state as st  # noqa: F401
from archipelago.inference.graph_lock import graph_lock  # noqa: F401

from .part01_library_catalog_knowledge import (
    JOURNAL_REGISTRY,
    LIBRARY_CATALOG_KNOWLEDGE,
    _populate_pearson_knowledge,
    clean_book_query,
    clean_topic_query,
    parse_chapter_lookup_query,
)
from .part02_get_book_metadata_details import (
    _prefer_papers_query,
    clean_catalog_topic,
    clean_journal_query,
    find_journal_status,
    get_book_metadata_details,
    get_books_for_topic,
    get_chapters_containing_concept,
    get_chapters_of_book,
    get_library_holdings_response,
    get_library_hours_response,
    get_library_materials_response,
    render_library_book_details,
    render_library_books,
    render_library_chapter_lookup,
    render_library_chapters,
)
from .part03_doc_pedagogy_score import (
    _doc_pedagogy_score,
)

__all__ = ["JOURNAL_REGISTRY", "LIBRARY_CATALOG_KNOWLEDGE", "_doc_pedagogy_score", "_populate_pearson_knowledge", "_prefer_papers_query", "clean_book_query", "clean_catalog_topic", "clean_journal_query", "clean_topic_query", "find_journal_status", "get_book_metadata_details", "get_books_for_topic", "get_chapters_containing_concept", "get_chapters_of_book", "get_library_holdings_response", "get_library_hours_response", "get_library_materials_response", "parse_chapter_lookup_query", "render_library_book_details", "render_library_books", "render_library_chapter_lookup", "render_library_chapters"]
