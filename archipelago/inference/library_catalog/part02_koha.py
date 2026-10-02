"""Koha ODS export loaders: holdings, journals, subject counts, subject titles."""

from __future__ import annotations

import logging
from pathlib import Path

from archipelago.inference.library_catalog.part01_ods import parse_ods_rows

logger = logging.getLogger("archipelago.inference.library_catalog_api")

HOLDINGS_ODS = "Titles List with specified keyword-reportresults.ods"
JOURNALS_ODS = "JOURNALS TITLES AND ISSUE COUNTS-reportresults.ods"
SUBJECT_COUNTS_ODS = "SUBJECT-WISE TITLE COUNT-reportresults.ods"
SUBJECT_TITLES_ODS = "SUBJECT-WISE TITLE COUNT-reportresults (1).ods"

_DEFAULT_COPIES = 0


def _cell(row: list[str], index: int, default: str = "") -> str:
    """Read one cell, tolerating short rows."""
    if len(row) > index and row[index]:
        return row[index]
    return default


def _int_cell(row: list[str], index: int) -> int:
    """Read one cell as an int, never raising on malformed Koha exports."""
    raw = _cell(row, index, "0")
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_COPIES


def load_holdings(path: Path | None) -> tuple[list[dict], int, int]:
    """Load Koha holdings rows plus total/available copy counts."""
    if not path:
        return [], 0, 0
    rows = parse_ods_rows(path)
    if len(rows) <= 1:
        return [], 0, 0

    holdings: list[dict] = []
    total_copies = 0
    available_copies = 0
    for r in rows[1:]:
        c_num = _int_cell(r, 5)
        a_num = _int_cell(r, 6)
        total_copies += c_num
        available_copies += a_num
        holdings.append(
            {
                "biblionumber": _cell(r, 0),
                "title": _cell(r, 1),
                "author": _cell(r, 2, "Unknown"),
                "publisher": _cell(r, 3, "Unknown"),
                "accession": _cell(r, 4),
                "no_of_copies": c_num,
                "available_copies": a_num,
                "available_barcodes": _cell(r, 7),
                "overdue_items": _cell(r, 8, "0"),
                "available_ratio": f"{a_num} / {c_num}",
            }
        )
    return holdings, total_copies, available_copies


def load_journals(path: Path | None) -> list[dict]:
    """Load journal title / volume / date / status rows."""
    if not path:
        return []
    rows = parse_ods_rows(path)
    if len(rows) <= 1:
        return []
    return [
        {
            "title": _cell(r, 0),
            "vol": _cell(r, 1),
            "date": _cell(r, 2),
            "status": _cell(r, 3),
        }
        for r in rows[1:]
    ]


def load_subject_counts(path: Path | None) -> list[dict]:
    """Load subject-wise title counts."""
    if not path:
        return []
    rows = parse_ods_rows(path)
    if len(rows) <= 1:
        return []
    return [{"subject": _cell(r, 0), "total_titles": _cell(r, 1, "0")} for r in rows[1:]]


def load_subject_titles(path: Path | None) -> list[dict]:
    """Load per-subject detailed title rows."""
    if not path:
        return []
    rows = parse_ods_rows(path)
    if len(rows) <= 1:
        return []
    return [
        {
            "subject": _cell(r, 0),
            "title": _cell(r, 1),
            "author": _cell(r, 2),
            "year": _cell(r, 3),
        }
        for r in rows[1:]
    ]
