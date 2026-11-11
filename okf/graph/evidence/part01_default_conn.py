"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

from typing import Any

from . import _deps as _rt

_DEFAULT_CONN = None


_DEFAULT_GRAPH_DB = None


def set_default_connection(conn: Any) -> None:
    """Set a default connection for module-level functions.

    This allows tests to inject a specific database connection.
    """
    global _DEFAULT_CONN
    _DEFAULT_CONN = conn


def _get_default_graph_db() -> Any:
    """Get a default GraphDB instance (creates one if needed)."""
    global _DEFAULT_GRAPH_DB
    if _DEFAULT_GRAPH_DB is None:
        _DEFAULT_GRAPH_DB = _rt.GraphDB()
    return _DEFAULT_GRAPH_DB
