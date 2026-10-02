"""KùzuDB graph ingestion with MERGE semantics."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from okf.config import BASE_DIR, infer_source_category
from okf.exports import build_graph_rag_index, build_visual_graph
from okf.util import _source_record, create_concept_id

logger = logging.getLogger(__name__)

# Cap a DDL statement's log rendering so one long CREATE does not flood the log.
DDL_LOG_MAX_CHARS = 120

# Anchor the default DB to the repo root so behaviour never depends on the
# process CWD (a CWD=parent process once minted an empty schema-only DB there).
_DEFAULT_DB_PATH = str(BASE_DIR / "okf_graph.db")


def _kuzu_escape(value: str) -> str:
    """Escape a string literal for inline Kuzu Cypher queries.

    Kuzu uses backslash escaping (\\') — NOT SQL-style doubled quotes ('').
    Doubled quotes raise a parser exception, which ensure_concept/ensure_chunk
    silently swallowed, dropping any node/chunk whose text contained an
    apostrophe (root cause of phantom viz nodes missing from the concepts dict).
    """
    return (value or "").replace("\\", "\\\\").replace("'", "\\'")


def _kuzu_literal(value) -> str:
    """Render a Python value as an inline Kuzu Cypher literal (None -> NULL)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return f"'{_kuzu_escape(str(value))}'"


# ---------------------------------------------------------------------------
# Schema DDL — single source of truth. Fresh databases (ingest_to_kuzu and
# GraphDB on a new path) get the full column set via these CREATEs; databases
# built before the citation-correctness columns existed are upgraded in place
# by _migrate_schema().
# ---------------------------------------------------------------------------
_SCHEMA_DDL = [
    """
    CREATE NODE TABLE Document (
        id STRING PRIMARY KEY,
        doc_hash STRING,
        page_count INT64,
        title STRING,
        edition STRING,
        page_label_map STRING
    )
    """,
    """
    CREATE NODE TABLE Chunk (
        id STRING PRIMARY KEY,
        chunk_id STRING,
        page_number INT64,
        section_title STRING,
        text_passage STRING,
        text_offset_start INT64,
        text_offset_end INT64,
        block_x DOUBLE,
        block_y DOUBLE,
        block_w DOUBLE,
        block_h DOUBLE
    )
    """,
    """
    CREATE NODE TABLE Concept (
        id STRING PRIMARY KEY,
        name STRING,
        concept_type STRING,
        difficulty STRING,
        summary STRING,
        tags STRING
    )
    """,
    """
    CREATE REL TABLE HAS_CHUNK (
        FROM Document TO Chunk
    )
    """,
    """
    CREATE REL TABLE MENTIONS (
        FROM Chunk TO Concept
    )
    """,
    """
    CREATE REL TABLE REQUIRES (
        FROM Concept TO Concept,
        relation_type STRING,
        source STRING
    )
    """,
    """
    CREATE REL TABLE UNLOCKS (
        FROM Concept TO Concept,
        relation_type STRING,
        source STRING
    )
    """,
    """
    CREATE REL TABLE RELATED (
        FROM Concept TO Concept,
        relation_type STRING,
        source STRING
    )
    """,
    # ── Institutional catalog (Koha / OPAC physical inventory) ──────────────
    # These used to live only in root `catalog_schema.py`, which production code
    # never called — so every graph built by ingest_to_kuzu() lacked the
    # Resource/Subject tables and `MATCH (r:Resource)` raised a Binder
    # exception.  `/api/catalog/search` swallowed it and returned zero results,
    # i.e. the librarian catalog search was silently dead.  Keeping the DDL here
    # makes the graph schema one list again; catalog_schema.py now delegates.
    """
    CREATE NODE TABLE Subject (
        id STRING PRIMARY KEY,
        subject_name STRING,
        total_titles INT64
    )
    """,
    """
    CREATE NODE TABLE Resource (
        id STRING PRIMARY KEY,
        title STRING,
        author STRING,
        copyright_year INT64,
        publisher STRING,
        biblionumber STRING,
        total_copies INT64,
        available_copies INT64,
        barcodes STRING,
        overdue_items INT64,
        is_periodical BOOLEAN
    )
    """,
    """
    CREATE REL TABLE CATEGORIZES (
        FROM Subject TO Resource
    )
    """,
    """
    CREATE REL TABLE PROVIDES_TEXT (
        FROM Resource TO Document,
        pdf_url STRING
    )
    """,
]

# Columns added after the original schema shipped (citation correctness).
# Kuzu 0.11.x raises a Binder exception ("... already exists in table ...")
# when ALTER TABLE ADD targets an existing property, so every ALTER is wrapped
# in try/except — running the migration repeatedly is a no-op (idempotent).
_MIGRATION_COLUMNS = [
    ("Chunk", "text_offset_start", "INT64"),
    ("Chunk", "text_offset_end", "INT64"),
    ("Chunk", "block_x", "DOUBLE"),
    ("Chunk", "block_y", "DOUBLE"),
    ("Chunk", "block_w", "DOUBLE"),
    ("Chunk", "block_h", "DOUBLE"),
    ("Document", "doc_hash", "STRING"),
    ("Document", "page_count", "INT64"),
    ("Document", "title", "STRING"),
    ("Document", "edition", "STRING"),
    ("Document", "page_label_map", "STRING"),
    ("Document", "pdf_url", "STRING"),
    ("Resource", "barcodes", "STRING"),
    ("Resource", "overdue_items", "INT64"),
    ("Resource", "is_periodical", "BOOLEAN"),
    ("Concept", "tags", "STRING"),
]


def _run_ddl(conn: Any, statements: Iterable[str]) -> None:
    """Execute idempotent DDL, logging (not swallowing) anything unexpected.

    Every statement here is `IF NOT EXISTS` or an `ALTER ... ADD`, so the
    expected failure is "already exists".  That case is logged at debug level;
    any *other* error is a real defect and must be visible, so it is logged at
    error level before continuing.  Callers rely on the operations being
    best-effort (a legacy database may be locked, read-only, or mid-ingest), so
    the loop never raises — but nothing is hidden either.
    """
    for ddl in statements:
        try:
            conn.execute(ddl)
        except Exception as exc:
            if _is_already_exists(exc):
                logger.debug("Schema object already present, skipping: %s", _first_line(ddl))
            else:
                logger.error("Schema DDL failed (%s): %s", _first_line(ddl), exc)


def _first_line(ddl: str) -> str:
    """Collapse a DDL statement to its first line for readable logging."""
    collapsed = " ".join(ddl.split())
    return collapsed[:DDL_LOG_MAX_CHARS]


def _is_already_exists(exc: Exception) -> bool:
    """True when a DDL failure is the expected idempotency case.

    Kuzu words the two no-op cases differently depending on the statement:
    ``CREATE ... IF NOT EXISTS`` against a present table raises "already exists",
    while ``ALTER TABLE ... ADD`` against a present column raises "already has
    property". Both mean "nothing to do", so both are debug-level.
    """
    text = str(exc).lower()
    return "already exists" in text or "already has property" in text


def _create_schema(conn: Any) -> None:
    """CREATE all node/rel tables (concept graph + institutional catalog)."""
    _run_ddl(conn, _SCHEMA_DDL)


def _migrate_schema(conn: Any) -> None:
    """ALTER pre-existing tables to add the citation-correctness columns."""
    _run_ddl(conn, (f"ALTER TABLE {t} ADD {c} {k}" for t, c, k in _MIGRATION_COLUMNS))



__all__ = [
    "BASE_DIR",
    "_DEFAULT_DB_PATH",
    "_MIGRATION_COLUMNS",
    "_SCHEMA_DDL",
    "_create_schema",
    "_kuzu_escape",
    "_kuzu_literal",
    "_migrate_schema",
    "_source_record",
    "build_graph_rag_index",
    "build_visual_graph",
    "create_concept_id",
    "infer_source_category",
    "logger",
]
