"""Read existing graph catalogue records for spreadsheet merge planning."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, cast

from okf.query_rows import query_rows

logger = logging.getLogger("archipelago.ingestion.spreadsheet")


def _fetch_existing(record_type: str, clean_str: Callable[[Any], str]) -> dict[str, dict[str, Any]]:
    """Read current catalogue state keyed by record id."""
    existing: dict[str, dict[str, Any]] = {}
    if record_type == "subject":
        query = "MATCH (s:Subject) RETURN s.id, s.subject_name, s.total_titles"
        name_field = "subject_name"
    else:
        query = (
            "MATCH (r:Resource) RETURN r.id, r.title, r.author, r.publisher, "
            "r.copyright_year, r.biblionumber, r.total_copies, r.available_copies, "
            "r.overdue_items, r.is_periodical"
        )
        name_field = "title"
    try:
        import kuzu

        from archipelago.inference import state as st

        if getattr(st, "db", None) is None:
            return existing
        conn = kuzu.Connection(cast(kuzu.Database, st.db))
        for row in query_rows(conn, query):
            existing[str(row[0])] = {
                name_field: clean_str(row[1]),
                "author": clean_str(row[2]) if len(row) > 2 else "",
                "publisher": clean_str(row[3]) if len(row) > 3 else "",
                "year": str(row[4]) if len(row) > 4 and row[4] is not None else "",
                "isbn": clean_str(row[5]) if len(row) > 5 else "",
                "total_copies": row[6] if len(row) > 6 and row[6] is not None else 0,
                "available_copies": row[7] if len(row) > 7 and row[7] is not None else 0,
                "overdue_items": row[8] if len(row) > 8 and row[8] is not None else 0,
                "is_periodical": bool(row[9]) if len(row) > 9 else False,
            }
    except Exception as exc:
        logger.debug("Existing catalogue read unavailable: %s", exc)
    return existing
