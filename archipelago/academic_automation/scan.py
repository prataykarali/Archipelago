"""Advance one bounded live OPAC search page on each scheduled run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .discovery import discover_opac_query
from .store import AcademicStore

MAX_QUERIES = 32
MAX_QUERY_CHARS = 100


def scan_configured_queries(
    store: AcademicStore, root: Path, queries_path: Path
) -> dict[str, Any]:
    """Persist a cursor so repeated runs eventually cover configured query pages."""
    loaded = json.loads(queries_path.read_text(encoding="utf-8"))
    if (
        not isinstance(loaded, list)
        or not loaded
        or len(loaded) > MAX_QUERIES
        or any(not isinstance(q, str) or not 2 <= len(q.strip()) <= MAX_QUERY_CHARS for q in loaded)
    ):
        raise ValueError("Academic OPAC queries must be a bounded string list")
    queries = [q.strip() for q in loaded]
    with store._connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS scan_cursor (name TEXT PRIMARY KEY, query_index INTEGER NOT NULL, offset INTEGER NOT NULL)"
        )
        row = db.execute(
            "SELECT query_index,offset FROM scan_cursor WHERE name='configured_opac'"
        ).fetchone()
    index, offset = (int(row[0]), int(row[1])) if row else (0, 0)
    index %= len(queries)
    result = discover_opac_query(store, root, queries[index], offset=offset)
    next_offset = result["next_offset"]
    next_index = index if next_offset is not None else (index + 1) % len(queries)
    with store._connect() as db:
        db.execute(
            "INSERT INTO scan_cursor(name,query_index,offset) VALUES('configured_opac',?,?) "
            "ON CONFLICT(name) DO UPDATE SET query_index=excluded.query_index,offset=excluded.offset",
            (next_index, next_offset or 0),
        )
    result["next_query"] = queries[next_index]
    result["next_query_offset"] = next_offset or 0
    return result
