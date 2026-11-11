"""Catalog statistics from Kuzu when available, else ODS-derived CSVs."""

from __future__ import annotations

import csv  # noqa: F401
from pathlib import Path  # noqa: F401
import re  # noqa: F401
from typing import Any  # noqa: F401

from archipelago.inference import state as st  # noqa: F401

from .part01_repo_root import (
    _DEFAULT_SUBJECT_LIMIT,
    _DEFAULT_ZERO_COPY_LIMIT,
    _DERIVED,
    _HOLDINGS_CSV,
    _JOURNAL_ISSUES_CSV,
    _REPO_ROOT,
    _SUBJECT_COUNTS_CSV,
    _SUBJECT_TITLES_CSV,
    _extract_keyword,
    _kuzu_conn,
    _read_csv,
    format_journal_totals,
    format_keyword_title_search,
    format_library_holdings_overview,
    format_subject_leaderboard,
    format_zero_copy_audit,
    highest_title_count_subject,
    journal_title_and_issue_totals,
    resource_kind_counts,
    subject_title_counts,
    zero_available_copies,
)
from .part02_format_citation import (
    copies_for_title,
    format_citation,
    format_copies_reply,
)

__all__ = [
    "_DEFAULT_SUBJECT_LIMIT",
    "_DEFAULT_ZERO_COPY_LIMIT",
    "_DERIVED",
    "_HOLDINGS_CSV",
    "_JOURNAL_ISSUES_CSV",
    "_REPO_ROOT",
    "_SUBJECT_COUNTS_CSV",
    "_SUBJECT_TITLES_CSV",
    "_extract_keyword",
    "_kuzu_conn",
    "_read_csv",
    "copies_for_title",
    "format_citation",
    "format_copies_reply",
    "format_journal_totals",
    "format_keyword_title_search",
    "format_library_holdings_overview",
    "format_subject_leaderboard",
    "format_zero_copy_audit",
    "highest_title_count_subject",
    "journal_title_and_issue_totals",
    "resource_kind_counts",
    "subject_title_counts",
    "zero_available_copies",
]
