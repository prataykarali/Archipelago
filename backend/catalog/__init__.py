"""Physical library intelligence, Koha holdings, and catalog operations."""
from __future__ import annotations

from archipelago.inference.catalog_ops import (
    copies_for_title,
    highest_title_count_subject,
    journal_title_and_issue_totals,
    resource_kind_counts,
    subject_title_counts,
    zero_available_copies,
)
from archipelago.inference.corpus_inventory import inventory_for_books
from archipelago.inference.library_queries import (
    get_book_metadata_details,
    get_books_for_topic,
    get_chapters_of_book,
    get_library_holdings_response,
    get_library_hours_response,
)
from archipelago.resolver.pearson import build_reader_url, resolve as resolve_pearson

__all__ = [
    "build_reader_url",
    "copies_for_title",
    "get_book_metadata_details",
    "get_books_for_topic",
    "get_chapters_of_book",
    "get_library_holdings_response",
    "get_library_hours_response",
    "highest_title_count_subject",
    "inventory_for_books",
    "journal_title_and_issue_totals",
    "resolve_pearson",
    "resource_kind_counts",
    "subject_title_counts",
    "zero_available_copies",
]
