"""library_queries.py — Cypher queries, metadata lookups, and rich library responses."""
from __future__ import annotations

import re  # noqa: F401
from typing import Any  # noqa: F401
from thefuzz import fuzz  # noqa: F401
from archipelago.inference.graph_lock import graph_lock  # noqa: F401
from archipelago.inference import state as st  # noqa: F401
import kuzu  # noqa: F401
import importlib  # noqa: F401

from .part01_library_catalog_knowledge import (  # noqa: F401
    LIBRARY_CATALOG_KNOWLEDGE,
    _populate_pearson_knowledge,
    JOURNAL_REGISTRY,
    clean_topic_query,
    clean_book_query,
    parse_chapter_lookup_query,
)
from .part02_get_book_metadata_details import (  # noqa: F401
    get_book_metadata_details,
    render_library_book_details,
    get_books_for_topic,
    get_library_hours_response,
    get_library_holdings_response,
    render_library_books,
    render_library_chapters,
    render_library_chapter_lookup,
    get_chapters_of_book,
    get_chapters_containing_concept,
    clean_catalog_topic,
    clean_journal_query,
    find_journal_status,
    _prefer_papers_query,
)
from .part03_doc_pedagogy_score import (  # noqa: F401
    _doc_pedagogy_score,
)

__all__ = ["LIBRARY_CATALOG_KNOWLEDGE", "_populate_pearson_knowledge", "JOURNAL_REGISTRY", "clean_topic_query", "clean_book_query", "parse_chapter_lookup_query", "get_book_metadata_details", "render_library_book_details", "get_books_for_topic", "get_library_hours_response", "get_library_holdings_response", "render_library_books", "render_library_chapters", "render_library_chapter_lookup", "get_chapters_of_book", "get_chapters_containing_concept", "clean_catalog_topic", "clean_journal_query", "find_journal_status", "_prefer_papers_query", "_doc_pedagogy_score"]
