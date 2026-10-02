"""Ingest the institutional Koha/OPAC export into the graph's catalog tables.

The ``Resource`` / ``Subject`` tables were previously only ever created by
``catalog_schema.create_schema`` — which no production path called — so
``/api/catalog/search`` matched nothing even though the institution had
exported its catalogue. This module is the missing producer: it reads the
Koha ODS reports (subject counts + title list) and MERGEs them into the graph.

Idempotent: re-running converges to the same rows (``MERGE`` on a stable id).
"""
from __future__ import annotations

from collections.abc import Iterable
import logging
import math
import re
from typing import Any

import kuzu
import pandas as pd

logger = logging.getLogger(__name__)

SUBJECT_ODS = "SUBJECT-WISE TITLE COUNT-reportresults.ods"
TITLES_ODS = "Titles List with specified keyword-reportresults.ods"

# Columns in the Koha "Titles List" export, in file order.
TITLE_COLUMNS = (
    "biblionumber",
    "Title",
    "Author",
    "Publisher",
    "Accn Nos.",
    "No. of copies",
    "Available Copies",
    "Available Barcodes",
    "Overdue Items",
)
# Index of each field we consume within TITLE_COLUMNS.
COL_BIBLIONUMBER = 0
COL_TITLE = 1
COL_AUTHOR = 2
COL_PUBLISHER = 3
COL_ACC_NOS = 4
COL_COPIES = 5
COL_AVAILABLE = 6
COL_BARCODES = 7
COL_OVERDUE = 8

UNKNOWN_PUBLISHER = "Unknown"
NO_SUBJECT = "General"
UNKNOWN_SUBJECT_LABEL = "Unclassified"
# Koha subjects arrive percent-wrapped ("%Computer Science%"); the export also
# contains placeholder rows such as "%Total%" that are not real subjects.
PLACEHOLDER_SUBJECTS = frozenset({"total", "%total%", "n/a", "none"})
PERIODICAL_HINT = "journal"


def clean_str(val: Any) -> str | None:
    """Return a stripped string, or None for null/blank/NaN values."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    text = str(val).strip()
    return text or None


def _slug(text: str) -> str:
    """Slugify a title/subject into an identifier fragment."""
    return re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")


def subject_id(name: str) -> str:
    """Stable primary key for a Subject node."""
    return f"subj_{_slug(name) or 'unclassified'}"


def resource_id(biblionumber: Any, title: str) -> str:
    """Stable primary key for a Resource node.

    Prefers the Koha biblionumber (authoritative and stable across retitles);
    falls back to a slug of the title when the export omits it.
    """
    bn = clean_str(biblionumber)
    if bn and bn not in {"0", "nan"}:
        return f"res_bn_{bn}"
    slug = _slug(title)
    return f"res_{slug or 'unknown'}"


def normalize_subject(raw: str | None) -> str:
    """Strip Koha's percent-wrapping and reject placeholder subjects."""
    name = (raw or "").strip().strip("%").strip()
    if not name or name.lower() in PLACEHOLDER_SUBJECTS:
        return UNKNOWN_SUBJECT_LABEL
    return name


def _to_int(val: Any) -> int:
    """Coerce a spreadsheet cell to int, defaulting to 0."""
    num = clean_str(val)
    if num is None:
        return 0
    try:
        return int(float(num))
    except (TypeError, ValueError):
        return 0


def _barcodes(raw: Any) -> str:
    """Render the barcodes cell as a JSON array string for the Resource row."""
    text = clean_str(raw) or ""
    parts = [p.strip() for p in text.replace(";", ",").split(",")]
    kept = [p for p in parts if p]
    return "[" + ", ".join(f'"{p}"' for p in kept) + "]"


def _is_periodical(title: str, publisher: str) -> bool:
    """Heuristic: journals/periodicals are flagged so they can be filtered out."""
    haystack = f"{title} {publisher}".lower()
    return PERIODICAL_HINT in haystack


def _esc(value: str) -> str:
    """Escape a string literal for inline Kuzu Cypher (backslash escaping)."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _read_ods(path: str) -> pd.DataFrame:
    """Read an ODS export, falling back to the default Excel engine."""
    try:
        return pd.read_excel(path, engine="odf")
    except Exception:
        return pd.read_excel(path)


def _merge_subject(conn: Any, name: str, total_titles: int) -> None:
    """MERGE one Subject node, updating the title count each run."""
    conn.execute(
        f"MERGE (s:Subject {{id: '{subject_id(name)}'}}) "
        f"ON MATCH SET s.total_titles = {total_titles} "
        f"ON CREATE SET s.subject_name = '{_esc(name)}', s.total_titles = {total_titles}"
    )


def _merge_resource(conn: Any, res_id: str, row: dict[str, Any]) -> None:
    """MERGE one Resource node plus its CATEGORIZES edge to the subject."""
    title = row["title"]
    conn.execute(
        f"MERGE (r:Resource {{id: '{res_id}'}}) "
        f"ON MATCH SET r.title = '{_esc(title)}', r.author = '{_esc(row['author'])}', "
        f"r.publisher = '{_esc(row['publisher'])}', r.biblionumber = '{_esc(row['biblionumber'])}', "
        f"r.total_copies = {row['total_copies']}, r.available_copies = {row['available_copies']}, "
        f"r.barcodes = '{row['barcodes']}', r.overdue_items = {row['overdue_items']}, "
        f"r.is_periodical = {str(row['is_periodical']).lower()} "
        f"ON CREATE SET r.title = '{_esc(title)}', r.author = '{_esc(row['author'])}', "
        f"r.copyright_year = {row['copyright_year']}, r.publisher = '{_esc(row['publisher'])}', "
        f"r.biblionumber = '{_esc(row['biblionumber'])}', r.total_copies = {row['total_copies']}, "
        f"r.available_copies = {row['available_copies']}, r.barcodes = '{row['barcodes']}', "
        f"r.overdue_items = {row['overdue_items']}, "
        f"r.is_periodical = {str(row['is_periodical']).lower()}"
    )
    subject = row["subject"]
    _merge_subject(conn, subject, 0)
    conn.execute(
        f"MATCH (s:Subject {{id: '{subject_id(subject)}'}}), (r:Resource {{id: '{res_id}'}}) "
        f"MERGE (s)-[:CATEGORIZES]->(r)"
    )


def _title_row(series: Any) -> dict[str, Any]:
    """Project one titles-export row onto the Resource column set."""
    title = clean_str(series.iloc[COL_TITLE]) or UNKNOWN_PUBLISHER
    publisher = clean_str(series.iloc[COL_PUBLISHER]) or UNKNOWN_PUBLISHER
    biblionumber = clean_str(series.iloc[COL_BIBLIONUMBER]) or "0"
    return {
        "title": title,
        "author": clean_str(series.iloc[COL_AUTHOR]) or UNKNOWN_PUBLISHER,
        "publisher": publisher,
        "biblionumber": biblionumber,
        "subject": NO_SUBJECT,
        "copyright_year": 0,
        "total_copies": _to_int(series.iloc[COL_COPIES]),
        "available_copies": _to_int(series.iloc[COL_AVAILABLE]),
        "barcodes": _barcodes(series.iloc[COL_BARCODES]),
        "overdue_items": _to_int(series.iloc[COL_OVERDUE]),
        "is_periodical": _is_periodical(title, publisher),
    }


def ingest_catalog(
    db_path: str,
    koha_dir: str,
    subject_ods: str | None = None,
    titles_ods: str | None = None,
) -> dict[str, int]:
    """Populate Subject/Resource/CATEGORIZES from a Koha ODS export directory.

    Returns counts of merged subjects and resources.
    """
    from pathlib import Path

    from catalog_schema import create_schema

    base = Path(koha_dir)
    subjects_path = base / (subject_ods or SUBJECT_ODS)
    titles_path = base / (titles_ods or TITLES_ODS)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    create_schema(conn)

    subject_count = 0
    if subjects_path.is_file():
        frame = _read_ods(str(subjects_path))
        subj_col, titles_col = frame.columns[0], frame.columns[1]
        for _, record in frame.iterrows():
            name = normalize_subject(clean_str(record[subj_col]))
            if name == UNKNOWN_SUBJECT_LABEL:
                continue
            _merge_subject(conn, name, _to_int(record[titles_col]))
            subject_count += 1

    resource_count = 0
    if titles_path.is_file():
        frame = _read_ods(str(titles_path))
        for _, series in frame.iterrows():
            title = clean_str(series.iloc[COL_TITLE])
            if not title:
                continue
            row = _title_row(series)
            _merge_resource(conn, resource_id(row["biblionumber"], row["title"]), row)
            resource_count += 1

    logger.info(
        "Catalog ingest: %d subjects, %d resources from %s", subject_count, resource_count, koha_dir
    )
    return {"subjects": subject_count, "resources": resource_count}


def iter_catalog_titles(db_path: str) -> Iterable[str]:
    """Yield every catalogued title, for librarian-facing inventory screens."""
    db = kuzu.Database(db_path, read_only=True)
    conn = kuzu.Connection(db)
    result = conn.execute("MATCH (r:Resource) RETURN r.title")
    while result.has_next():
        yield result.get_next()[0]


def _pearson_row(book: dict[str, Any]) -> dict[str, Any] | None:
    """Project one Pearson eLibrary bookshelf entry onto the Resource columns."""
    title = clean_str(book.get("title"))
    if not title:
        return None
    page_count = _to_int(book.get("page_count"))
    return {
        "title": title,
        "author": clean_str(book.get("author")) or UNKNOWN_PUBLISHER,
        "publisher": clean_str(book.get("publisher")) or "Pearson eLibrary",
        "biblionumber": clean_str(book.get("isbn")) or "0",
        "subject": normalize_subject(clean_str(book.get("domain"))) or UNKNOWN_SUBJECT_LABEL,
        "copyright_year": 0,
        "total_copies": 1,
        "available_copies": 1,
        "barcodes": "[]",
        "overdue_items": 0,
        "is_periodical": False,
        # Retained on the row for the reader gateway, not a graph column.
        "page_count": page_count,
        "subscription_id": clean_str(book.get("subscription_id")) or "",
        "reader_base_url": clean_str(book.get("reader_base_url")) or "",
        "pdf_url": clean_str(book.get("cover_url")) or "",
    }


def ingest_pearson_bookshelf(
    db_path: str, bookshelf_path: str, base_url: str | None = None
) -> dict[str, int]:
    """Merge the Pearson eLibrary bookshelf into the catalog tables.

    This is the institution's *book* catalogue: the Koha export holds
    periodicals, so without this step ``/api/catalog/search`` could not answer a
    question about a textbook at all. Idempotent via ``MERGE`` on the ISBN.
    """
    import json
    from pathlib import Path

    from catalog_schema import create_schema

    path = Path(bookshelf_path)
    if not path.is_file():
        logger.info("Pearson bookshelf not found at %s; skipping", path)
        return {"subjects": 0, "resources": 0}

    payload = json.loads(path.read_text(encoding="utf-8"))
    books = payload.get("books", []) if isinstance(payload, dict) else []

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    create_schema(conn)

    merged = 0
    subjects: set[str] = set()
    for book in books:
        row = _pearson_row(book)
        if row is None:
            continue
        res_id = f"res_pearson_{_slug(row['biblionumber']) or _slug(row['title'])}"
        _merge_resource(conn, res_id, row)
        subjects.add(row["subject"])
        merged += 1

    logger.info("Pearson bookshelf ingest: %d resources from %s", merged, path)
    return {"subjects": len(subjects), "resources": merged}


__all__ = [
    "ingest_catalog",
    "ingest_pearson_bookshelf",
    "iter_catalog_titles",
    "normalize_subject",
    "resource_id",
    "subject_id",
]
