"""Persistence boundary for the library holdings snapshot.

One concern: validating an uploaded librarian CSV and persisting it.  Routes
depend on this object, so a test can substitute an in-memory store.
"""
from __future__ import annotations

from library_inventory import parse_inventory_csv, save_inventory


class InventoryStore:
    """Validate and persist the institutional holdings snapshot."""

    @staticmethod
    def parse(raw: bytes) -> list[dict]:
        """Parse an uploaded CSV export. Raises ``ValueError`` on a bad schema."""
        return parse_inventory_csv(raw)

    @staticmethod
    def save(rows: list[dict]) -> None:
        """Persist the snapshot. Raises on storage failure."""
        save_inventory(rows)
