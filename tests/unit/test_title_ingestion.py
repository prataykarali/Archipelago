"""
tests/unit/test_title_ingestion.py
Session 3 exit criteria: Resource nodes + CATEGORIZES edges created correctly.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..", "..")
sys.path.insert(0, _ROOT)

import kuzu
from catalog_schema import create_schema
from catalog_ingest import ingest_subjects, ingest_titles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_titles_ods(tmp_dir: str, rows: list[list]) -> str:
    import pandas as pd
    filepath = os.path.join(tmp_dir, "mock_titles.ods")
    pd.DataFrame(rows).to_excel(filepath, engine="odf", index=False, header=False)
    return filepath


def _make_mock_subjects_ods(tmp_dir: str) -> str:
    import pandas as pd
    filepath = os.path.join(tmp_dir, "mock_subjects.ods")
    data = [
        ["Subject", "Total Titles"],
        ["Computer Science", 10],
        ["Mathematics", 5],
    ]
    pd.DataFrame(data).to_excel(filepath, engine="odf", index=False, header=False)
    return filepath


def _open_fresh_db(tmp_dir: str) -> str:
    """Create schema in a fresh KùzuDB; release lock and return db_path."""
    db_path = os.path.join(tmp_dir, "test_graph.db")
    db      = kuzu.Database(db_path)
    conn    = kuzu.Connection(db)
    create_schema(conn)
    del conn, db   # release exclusive lock
    return db_path


def _query(db_path: str, cypher: str):
    """Open a fresh connection, run query, return QueryResult."""
    db   = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    return conn.execute(cypher)


MOCK_TITLE_ROWS = [
    ["Subject",          "Title",                            "Author",         "Copyright Year"],
    ["Computer Science", "Introduction to Algorithms",       "Cormen",         2022],
    ["Computer Science", "Clean Code",                       "Robert Martin",  2008],
    ["Mathematics",      "Linear Algebra Done Right",        "Sheldon Axler",  2015],
    ["Mathematics",      "Calculus",                         "Spivak",         None],
    ["Computer Science", "Design Patterns",                  "Gang of Four",   1994],
]


class TestIngestTitles:

    def test_resource_count_matches_unique_titles(self, tmp_path):
        """5 unique titles → exactly 5 Resource nodes."""
        subj_file  = _make_mock_subjects_ods(str(tmp_path))
        title_file = _make_mock_titles_ods(str(tmp_path), MOCK_TITLE_ROWS)
        db_path    = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, subj_file)
        result = ingest_titles(db_path, title_file)

        res   = _query(db_path, "MATCH (r:Resource) RETURN COUNT(r)")
        count = res.get_next()[0]
        assert count == 5, f"Expected 5 Resource nodes, got {count}"
        assert result["resources"] == 5

    def test_categorizes_edge_count(self, tmp_path):
        """Each resource should have exactly 1 CATEGORIZES incoming edge."""
        subj_file  = _make_mock_subjects_ods(str(tmp_path))
        title_file = _make_mock_titles_ods(str(tmp_path), MOCK_TITLE_ROWS)
        db_path    = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, subj_file)
        result = ingest_titles(db_path, title_file)

        res        = _query(db_path, "MATCH (s:Subject)-[e:CATEGORIZES]->(r:Resource) RETURN COUNT(e)")
        edge_count = res.get_next()[0]
        assert edge_count == 5, f"Expected 5 CATEGORIZES edges, got {edge_count}"

    def test_every_resource_has_one_incoming_categorizes(self, tmp_path):
        """No Resource should have zero or more than one CATEGORIZES edge."""
        subj_file  = _make_mock_subjects_ods(str(tmp_path))
        title_file = _make_mock_titles_ods(str(tmp_path), MOCK_TITLE_ROWS)
        db_path    = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, subj_file)
        ingest_titles(db_path, title_file)

        res = _query(
            db_path,
            "MATCH (r:Resource) "
            "OPTIONAL MATCH (s:Subject)-[:CATEGORIZES]->(r) "
            "RETURN r.title, COUNT(s) AS edge_count"
        )
        while res.has_next():
            row = res.get_next()
            title, edge_count = row[0], row[1]
            assert edge_count == 1, (
                f"Resource '{title}' has {edge_count} CATEGORIZES edges (expected exactly 1)"
            )

    def test_subject_nodes_not_duplicated(self, tmp_path):
        """Subject nodes from Session 2 should be reused, not duplicated."""
        subj_file  = _make_mock_subjects_ods(str(tmp_path))
        title_file = _make_mock_titles_ods(str(tmp_path), MOCK_TITLE_ROWS)
        db_path    = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, subj_file)
        before = _query(db_path, "MATCH (s:Subject) RETURN COUNT(s)").get_next()[0]

        ingest_titles(db_path, title_file)
        after = _query(db_path, "MATCH (s:Subject) RETURN COUNT(s)").get_next()[0]

        assert after == before, (
            f"Subject count changed from {before} to {after} — duplicates created!"
        )

    def test_null_copyright_year_handled(self, tmp_path):
        """Resources with no copyright year should store NULL without error."""
        subj_file  = _make_mock_subjects_ods(str(tmp_path))
        title_file = _make_mock_titles_ods(str(tmp_path), MOCK_TITLE_ROWS)
        db_path    = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, subj_file)
        result = ingest_titles(db_path, title_file)
        assert result["errors"] == 0

    def test_whitespace_stripped_from_titles(self, tmp_path):
        """Titles with leading/trailing whitespace should be stored cleaned."""
        rows_with_spaces = [
            ["Subject",          "Title",          "Author",   "Copyright Year"],
            ["Computer Science", "  Clean Code  ", "Martin",   2008],
        ]
        subj_file  = _make_mock_subjects_ods(str(tmp_path))
        title_file = _make_mock_titles_ods(str(tmp_path), rows_with_spaces)
        db_path    = _open_fresh_db(str(tmp_path))

        ingest_subjects(db_path, subj_file)
        ingest_titles(db_path, title_file)

        res   = _query(db_path, "MATCH (r:Resource) RETURN r.title")
        title = res.get_next()[0]
        assert title == title.strip(), f"Title has whitespace: '{title}'"
