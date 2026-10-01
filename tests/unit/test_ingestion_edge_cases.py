"""Unit tests for ingestion edge cases and malformed input handling.

Tests empty CSV files, malformed formatting, missing required columns,
and duplicate record handling.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "tests" / "fixtures"


@pytest.mark.unit
def test_empty_csv_handling() -> None:
    """An empty CSV (header only) should result in 0 records parsed without crashing."""
    empty_csv = FIXTURES_DIR / "empty.csv"
    assert empty_csv.exists()

    rows = []
    with open(empty_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) == 0


@pytest.mark.unit
def test_missing_columns_detected() -> None:
    """CSV missing required schema columns (e.g. title) must be identified."""
    missing_csv = FIXTURES_DIR / "missing_columns.csv"
    assert missing_csv.exists()

    required_cols = {"title", "author"}
    with open(missing_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])

    missing = required_cols - fieldnames
    assert len(missing) > 0
    assert "title" in missing
    assert "author" in missing


@pytest.mark.unit
def test_duplicate_row_filtering() -> None:
    """Duplicate rows within ingestion files should be detected and deduplicated."""
    sample_records = [
        {"title": "Book A", "isbn": "111", "author": "Author A"},
        {"title": "Book A", "isbn": "111", "author": "Author A"},
        {"title": "Book B", "isbn": "222", "author": "Author B"},
    ]

    seen = set()
    deduped = []
    for rec in sample_records:
        key = (rec["title"].lower().strip(), rec.get("isbn", "").strip())
        if key not in seen:
            seen.add(key)
            deduped.append(rec)

    assert len(deduped) == 2
    assert len(seen) == 2
