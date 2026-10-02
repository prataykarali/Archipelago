"""Feature regression — institutional catalog (librarian surface).

Covers the ``Resource`` / ``Subject`` catalog path end to end:

* the catalog DDL is part of the canonical graph schema, so any graph built by
  ingestion can be searched (``/api/catalog/search`` used to match nothing
  because only ``catalog_schema.create_schema`` declared those tables and no
  production path called it);
* Koha periodicals and the Pearson eLibrary bookshelf both MERGE idempotently;
* identifier slugs, subject normalisation and spreadsheet coercion are total
  functions (no crash on null/NaN/blank cells);
* re-running ingest converges rather than duplicating rows.

Deterministic: builds a throwaway Kuzu database in ``tmp_path``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog_populate import (  # noqa: E402
    ingest_catalog,
    ingest_pearson_bookshelf,
    normalize_subject,
    resource_id,
    subject_id,
)

pytestmark = pytest.mark.unit


# ─── Schema is present on a freshly ingested graph ──────────────────────────


def test_catalog_tables_exist_after_ensure_schema(tmp_path):
    """A graph created by the pipeline must expose the catalog tables."""
    import kuzu

    from catalog_schema import create_schema

    db_path = str(tmp_path / "graph.db")
    conn = kuzu.Connection(kuzu.Database(db_path))
    create_schema(conn)

    present = set()
    tables = conn.execute("CALL show_tables() RETURN *")
    while tables.has_next():
        present.add(tables.get_next()[1])

    assert {"Resource", "Subject", "CATEGORIZES", "PROVIDES_TEXT"} <= present


def test_canonical_schema_ddl_includes_catalog_tables():
    """The DDL list itself must carry the catalog tables, not just the shim."""
    from okf.graph.common import _SCHEMA_DDL

    joined = "\n".join(_SCHEMA_DDL)
    assert "CREATE NODE TABLE Resource" in joined
    assert "CREATE NODE TABLE Subject" in joined


def test_catalog_bridge_links_resource_to_document(tmp_path):
    """PROVIDES_TEXT wiring still resolves after the schema consolidation."""
    import kuzu

    from catalog_bridge import link_resource_to_document

    db_path = str(tmp_path / "bridge.db")
    conn = kuzu.Connection(kuzu.Database(db_path))
    from catalog_schema import create_schema

    create_schema(conn)
    conn.execute("MERGE (d:Document {id: 'doc1'})")
    conn.execute("MERGE (r:Resource {id: 'res1', title: 'Algorithms'})")

    # The bridge matches on title, not id.
    assert link_resource_to_document(db_path, "Algorithms", "doc1")
    # Re-open: the bridge writes through its own connection, and the handle
    # above predates the commit.
    verify = kuzu.Connection(kuzu.Database(db_path, read_only=True))
    linked = verify.execute(
        "MATCH (r:Resource)-[:PROVIDES_TEXT]->(d:Document) RETURN count(*)"
    ).get_next()[0]
    assert linked == 1


def test_catalog_bridge_reports_failure_for_unknown_title(tmp_path):
    """A title that matches no Resource must report False, not a silent no-op."""
    from catalog_bridge import link_resource_to_document
    import kuzu

    db_path = str(tmp_path / "miss.db")
    conn = kuzu.Connection(kuzu.Database(db_path))
    from catalog_schema import create_schema

    create_schema(conn)
    conn.execute("MERGE (d:Document {id: 'doc1'})")
    conn.execute("MERGE (r:Resource {id: 'res1', title: 'Algorithms'})")

    assert link_resource_to_document(db_path, "Nonexistent Title", "doc1") is False


# ─── Identifier + normalisation helpers are total ────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("%Computer Science%", "Computer Science"),
        ("  Electronics  ", "Electronics"),
        ("%Total%", "Unclassified"),
        ("total", "Unclassified"),
        ("", "Unclassified"),
        (None, "Unclassified"),
    ],
)
def test_normalize_subject_strips_koha_wrapping_and_placeholders(raw, expected):
    assert normalize_subject(raw) == expected


@pytest.mark.parametrize(
    "biblionumber, title, prefix",
    [
        ("1910", "Journal", "res_bn_"),
        ("", "Design and Analysis", "res_design_and_analysis"),
        (None, "OS Internals", "res_os_internals"),
    ],
)
def test_resource_id_prefers_biblionumber_then_title(biblionumber, title, prefix):
    assert resource_id(biblionumber, title).startswith(prefix)


def test_resource_id_is_stable_across_calls():
    """Re-ingesting the same book must produce the same key (MERGE safety)."""
    assert resource_id("9789332526532", "DSP") == resource_id("9789332526532", "DSP")


def test_subject_id_is_slugged():
    assert subject_id("Signal Processing & Mathematics") == (
        "subj_signal_processing_mathematics"
    )


@pytest.mark.parametrize("cell, expected", [("7", 7), (7, 7), ("", 0), (None, 0), ("n/a", 0)])
def test_spreadsheet_coercion_never_raises(cell, expected):
    from catalog_populate import _to_int

    assert _to_int(cell) == expected


def test_barcodes_render_as_json_array():
    from catalog_populate import _barcodes

    assert _barcodes("J297, J621") == '["J297", "J621"]'
    assert _barcodes(None) == "[]"


# ─── Real exports populate the catalog idempotently ─────────────────────────


def _make_koha_export(tmp_path: Path) -> Path:
    """Write a minimal Koha-style export pair (periodical + a textbook)."""
    pd = pytest.importorskip("pandas")
    koha = tmp_path / "koha"
    koha.mkdir()
    subjects = pd.DataFrame({"Subject": ["Computer Science", "%Total%"], "Total Titles": [2, 99]})
    titles = pd.DataFrame(
        {
            "biblionumber": [1910, 22],
            "Title": ["Journal of Testing", "Design and Analysis of Algorithms"],
            "Author": [None, "Levitin"],
            "Publisher": [None, "Pearson"],
            "Accn Nos.": ["J1", "A2"],
            "No. of copies": [2, 3],
            "Available Copies": [1, 2],
            "Available Barcodes": ["J1", "A2, A3"],
            "Overdue Items": [0, 1],
        }
    )
    subjects.to_excel(koha / "SUBJECT-WISE TITLE COUNT-reportresults.ods", engine="odf", index=False)
    titles.to_excel(koha / "Titles List with specified keyword-reportresults.ods", engine="odf", index=False)
    return koha


def test_ingest_catalog_populates_and_is_idempotent(tmp_path):
    pytest.importorskip("pandas")
    import kuzu

    koha = _make_koha_export(tmp_path)
    db_path = str(tmp_path / "cat.db")

    first = ingest_catalog(db_path, str(koha))
    assert first["resources"] == 2
    # The "%Total%" placeholder row is rejected; every Resource also gets a
    # subject ("General" when the export names none), so both rows land.
    assert first["subjects"] == 1

    conn = kuzu.Connection(kuzu.Database(db_path, read_only=True))
    assert conn.execute("MATCH (r:Resource) RETURN count(r)").get_next()[0] == 2
    assert conn.execute("MATCH (s:Subject) RETURN count(s)").get_next()[0] == 2
    assert conn.execute("MATCH (s:Subject)-[:CATEGORIZES]->(r:Resource) RETURN count(*)").get_next()[0] == 2

    second = ingest_catalog(db_path, str(koha))
    assert second == first
    assert conn.execute("MATCH (r:Resource) RETURN count(r)").get_next()[0] == 2


def test_ingest_catalog_skips_missing_export_without_raising(tmp_path):
    """A missing export yields zeros, not an exception (librarian UX)."""
    result = ingest_catalog(str(tmp_path / "empty.db"), str(tmp_path / "does-not-exist"))
    assert result == {"subjects": 0, "resources": 0}


def test_pearson_bookshelf_populates_searchable_books(tmp_path):
    """The eLibrary bookshelf is the institution's book catalogue."""
    import json

    import kuzu

    db_path = str(tmp_path / "pearson.db")
    shelf = tmp_path / "pearson_bookshelf.json"
    shelf.write_text(
        json.dumps(
            {
                "total_books": 2,
                "source": "pearson",
                "books": [
                    {
                        "id": "b1",
                        "title": "Digital Signal Processing, 4e",
                        "author": "Proakis",
                        "isbn": "9789332526532",
                        "domain": "Signal Processing & Mathematics",
                        "page_count": 1157,
                        "subscription_id": "sub-1",
                        "cover_url": "https://example.org/cover.jpg",
                        "reader_base_url": "https://example.org/reader",
                    },
                    {"id": "b2"},  # no title -> skipped
                ],
            }
        ),
        encoding="utf-8",
    )

    result = ingest_pearson_bookshelf(db_path, str(shelf))
    assert result["resources"] == 1

    conn = kuzu.Connection(kuzu.Database(db_path, read_only=True))
    row = conn.execute("MATCH (r:Resource) RETURN r.title, r.author, r.biblionumber").get_next()
    assert list(row) == ["Digital Signal Processing, 4e", "Proakis", "9789332526532"]


def test_pearson_bookshelf_missing_file_is_a_no_op(tmp_path):
    result = ingest_pearson_bookshelf(
        str(tmp_path / "x.db"), str(tmp_path / "absent.json")
    )
    assert result == {"subjects": 0, "resources": 0}


# ─── The API surface returns real rows ──────────────────────────────────────


def test_catalog_search_endpoint_returns_matches_for_a_real_book(tmp_path, monkeypatch):
    """Regression: this endpoint returned zero results for every query.

    The route swallowed a Binder exception because ``Resource`` was absent from
    the graph. The test builds a graph with the real schema and a known title,
    then asserts the route finds it.
    """
    import kuzu

    import archipelago.api.engine_state as engine_state
    from archipelago.api import app as app_module
    from archipelago.api.routes_library import app as library_app

    db_path = str(tmp_path / "api.db")
    conn = kuzu.Connection(kuzu.Database(db_path))
    from catalog_schema import create_schema

    create_schema(conn)
    conn.execute(
        "MERGE (r:Resource {id: 'res_algo', title: 'Design and Analysis of Algorithms', "
        "author: 'Levitin', biblionumber: '22', publisher: 'Pearson', "
        "copyright_year: 2012, total_copies: 3, available_copies: 2})"
    )

    monkeypatch.setattr(engine_state, "DB_PATH", db_path)
    monkeypatch.setattr(engine_state, "_kuzu_conn", None)
    monkeypatch.setattr(app_module, "app", library_app, raising=False)
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    library_app.config["TESTING"] = True

    with library_app.test_client() as client:
        payload = client.get("/api/catalog/search?q=algorithms").get_json()

    assert payload["count"] == 1
    assert payload["results"][0]["title"] == "Design and Analysis of Algorithms"
    assert payload["results"][0]["author"] == "Levitin"


def test_catalog_search_returns_empty_for_unknown_term(tmp_path, monkeypatch):
    """An empty result set is honest, not an error."""
    import kuzu

    import archipelago.api.engine_state as engine_state
    from catalog_schema import create_schema

    db_path = str(tmp_path / "api2.db")
    conn = kuzu.Connection(kuzu.Database(db_path))
    create_schema(conn)
    conn.execute("MERGE (r:Resource {id: 'r1', title: 'Signals'})")

    monkeypatch.setattr(engine_state, "DB_PATH", db_path)
    monkeypatch.setattr(engine_state, "_kuzu_conn", None)
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")

    from archipelago.api.routes_library import app as library_app

    library_app.config["TESTING"] = True
    with library_app.test_client() as client:
        payload = client.get("/api/catalog/search?q=nonexistent").get_json()

    assert payload["count"] == 0
    assert payload["results"] == []