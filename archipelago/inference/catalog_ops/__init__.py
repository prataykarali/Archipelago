"""Catalog statistics from Kuzu when available, else ODS-derived CSVs."""
from __future__ import annotations

import csv  # noqa: F401
import re  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any  # noqa: F401
from archipelago.inference import state as st  # noqa: F401

from .part01_repo_root import (  # noqa: F401
    _REPO_ROOT,
    _DERIVED,
    _SUBJECT_COUNTS_CSV,
    _SUBJECT_TITLES_CSV,
    _JOURNAL_ISSUES_CSV,
    _HOLDINGS_CSV,
    _DEFAULT_SUBJECT_LIMIT,
    _DEFAULT_ZERO_COPY_LIMIT,
    _read_csv,
    _kuzu_conn,
    subject_title_counts,
    highest_title_count_subject,
    format_subject_leaderboard,
    journal_title_and_issue_totals,
    format_journal_totals,
    resource_kind_counts,
    format_library_holdings_overview,
    _extract_keyword,
    format_keyword_title_search,
    zero_available_copies,
    format_zero_copy_audit,
)
from .part02_format_citation import (  # noqa: F401
    format_citation,
    copies_for_title,
    format_copies_reply,
)

__all__ = ["_REPO_ROOT", "_DERIVED", "_SUBJECT_COUNTS_CSV", "_SUBJECT_TITLES_CSV", "_JOURNAL_ISSUES_CSV", "_HOLDINGS_CSV", "_DEFAULT_SUBJECT_LIMIT", "_DEFAULT_ZERO_COPY_LIMIT", "_read_csv", "_kuzu_conn", "subject_title_counts", "highest_title_count_subject", "format_subject_leaderboard", "journal_title_and_issue_totals", "format_journal_totals", "resource_kind_counts", "format_library_holdings_overview", "_extract_keyword", "format_keyword_title_search", "zero_available_copies", "format_zero_copy_audit", "format_citation", "copies_for_title", "format_copies_reply"]
