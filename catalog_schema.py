"""
Institutional catalog schema for KùzuDB — thin compat shim.

The catalog DDL used to live only here, while production ingestion created
tables from ``okf.graph.common._SCHEMA_DDL`` (concept graph only). No
production path ever called ``create_schema``, so every real graph was missing
``Resource`` / ``Subject`` and ``/api/catalog/search`` silently matched nothing.
The DDL is now part of the canonical schema list in ``okf.graph.common``; this
module remains so existing imports and tests keep working.
"""
from __future__ import annotations

from typing import Any

from okf.graph.common import _create_schema, _migrate_schema

__all__ = ["create_schema"]


def create_schema(conn: Any) -> None:
    """Ensure the full graph schema (concepts + institutional catalog) exists."""
    _create_schema(conn)
    _migrate_schema(conn)