"""
tests/unit/test_subject_ingestion.py
Session 2 exit criteria: Subject nodes are correctly created from ODS data.
"""
import os
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..", "..")
sys.path.insert(0, _ROOT)

import kuzu
from catalog_schema import create_schema
from catalog_ingest import ingest_subjects, _clean_str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_ods(tmp_dir: str, rows: list[list]) -> str:
    """Write a 5-row mock ODS using pandas and return its path."""
    import pandas as pd

    filepath = os.path.join(tmp_dir, "mock_subjects.ods")
    # rows include the header row at index 0
    df = pd.DataFrame(rows)
    df.to_excel(filepath, engine="odf", index=False, header=False)
    return filepath


def _open_fresh_db(tmp_dir: str) -> str:
    """Create a fresh KùzuDB with the full schema. Returns db_path (DB is closed)."""
    db_path = os.path.join(tmp_dir, "test_graph.db")
    db      = kuzu.Database(db_path)
    conn    = kuzu.Connection(db)
    create_schema(conn)
    del conn, db   # release exclusive lock so ingest can open its own kuzu.Database
    return db_path


def _query(db_path: str, cypher: str):
    """Open a fresh read connection, run a query, return the QueryResult."""
    db   = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    return conn.execute(cypher)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIngestSubjects:

    MOCK_ROWS = [
        ["Subject", "Total Titles"],   # header
        ["Computer Science", 194],
        ["Electronics", 109],
        ["Mathematics", 60],
        ["Physics", 69],
        ["Management", 83],
    ]

    def test_creates_five_subject_nodes(self, tmp_path):
        """Exactly 5 Subject nodes should be created from the 5-row mock ODS."""
        filepath = _make_mock_ods(str(tmp_path), self.MOCK_ROWS)
        db_path  = _open_fresh_db(str(tmp_path))

        result = ingest_subjects(db_path, filepath)

        res   = _query(db_path, "MATCH (s:Subject) RETURN COUNT(s)")
        count = res.get_next()[0]

        assert count == 5, f"Expected 5 Subject nodes, got {count}"
        assert result["merged"] == 5
        assert result["errors"] == 0

    def test_subject_names_correct(self, tmp_path):
        """Verify the actual subject names are stored correctly."""
        filepath = _make_mock_ods(str(tmp_path), self.MOCK_ROWS)
        db_path  = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, filepath)

        res   = _query(db_path, "MATCH (s:Subject) RETURN s.subject_name ORDER BY s.subject_name")
        names = []
        while res.has_next():
            names.append(res.get_next()[0])

        assert "Computer Science" in names
        assert "Electronics"      in names
        assert "Mathematics"      in names
        assert "Physics"          in names
        assert "Management"       in names

    def test_total_titles_stored(self, tmp_path):
        """Verify total_titles counts are stored on Subject nodes."""
        filepath = _make_mock_ods(str(tmp_path), self.MOCK_ROWS)
        db_path  = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, filepath)

        res   = _query(db_path, "MATCH (s:Subject {subject_name: 'Computer Science'}) RETURN s.total_titles")
        count = res.get_next()[0]
        assert count == 194, f"Expected 194, got {count}"

    def test_idempotent_rerun(self, tmp_path):
        """Running ingest twice should not duplicate Subject nodes (MERGE semantics)."""
        filepath = _make_mock_ods(str(tmp_path), self.MOCK_ROWS)
        db_path  = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, filepath)
        ingest_subjects(db_path, filepath)  # second run

        res   = _query(db_path, "MATCH (s:Subject) RETURN COUNT(s)")
        count = res.get_next()[0]
        assert count == 5, f"Re-run created duplicates. Expected 5, got {count}"

    def test_empty_rows_skipped(self, tmp_path):
        """Rows with empty subject names should be silently skipped."""
        rows_with_blank = [
            ["Subject", "Total Titles"],
            ["Computer Science", 194],
            ["", 50],
            [None, 30],
            ["Physics", 69],
        ]
        filepath = _make_mock_ods(str(tmp_path), rows_with_blank)
        db_path  = _open_fresh_db(str(tmp_path))

        result = ingest_subjects(db_path, filepath)

        res   = _query(db_path, "MATCH (s:Subject) RETURN COUNT(s)")
        count = res.get_next()[0]
        assert count == 2, f"Expected 2 valid subjects, got {count}"
        assert result["skipped"] >= 2


class TestCleanStr:
    def test_strips_whitespace(self):
        assert _clean_str("  hello  ") == "hello"

    def test_none_returns_none(self):
        assert _clean_str(None) is None

    def test_nan_returns_none(self):
        import math
        assert _clean_str(float("nan")) is None

    def test_empty_string_returns_none(self):
        assert _clean_str("") is None
        assert _clean_str("   ") is None
