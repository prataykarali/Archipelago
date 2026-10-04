"""Explicit catalogue location fields stored locally, never external model evidence."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
FIELDS = ("call_number", "barcode", "rack", "shelf", "location")


def ensure_fields(conn) -> None:
    """Extend existing Resource schemas without dropping data."""
    for field in FIELDS:
        try:
            conn.execute(f"ALTER TABLE Resource ADD {field} STRING DEFAULT ''")
        except RuntimeError as exc:
            if "exist" not in str(exc).lower() and "already has" not in str(exc).lower():
                raise


def store_fields(conn, record_id: str, fields: dict) -> None:
    """Update only explicitly supplied location attributes."""
    supplied = {field: str(fields[field]) for field in FIELDS if field in fields}
    if not supplied:
        return
    assignment = ", ".join(f"r.{field}=${field}" for field in supplied)
    conn.execute(
        "MATCH (r:Resource {id:$id}) SET " + assignment,
        {"id": record_id, **supplied},
    )


def read_fields(conn) -> dict[str, dict]:
    """Return additional location fields when the resource schema supports them."""
    try:
        result = conn.execute(
            "MATCH (r:Resource) RETURN r.id, " + ", ".join("r." + f for f in FIELDS)
        )
        records = {}
        while result.has_next():
            row = result.get_next()
            records[str(row[0])] = dict(zip(FIELDS, row[1:], strict=True))
        return records
    except RuntimeError:
        logger.debug("Legacy catalogue has no imported location fields.")
        return {}
