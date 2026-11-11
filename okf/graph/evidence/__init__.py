"""evidence.py — Kùzu graph submodule."""

from __future__ import annotations

import json  # noqa: F401
import os  # noqa: F401
from typing import Any

from okf.graph.common import (
    _DEFAULT_DB_PATH,  # noqa: F401
    _SCHEMA_DDL,  # noqa: F401
    BASE_DIR,  # noqa: F401
    _create_schema,  # noqa: F401
    _kuzu_escape,  # noqa: F401
    _kuzu_literal,  # noqa: F401
    _migrate_schema,  # noqa: F401
    logger,  # noqa: F401
)
from okf.util import create_concept_id  # noqa: F401

from . import part01_default_conn as _state
from .part01_default_conn import (
    _get_default_graph_db,
    set_default_connection,
)
from .part02_evidence_return import (
    _EVIDENCE_RETURN,
    GraphDB,
    _get_conn,
    _is_connection,
    _row_to_evidence,
    add_chunk,
    add_document,
)
from .part03_get_evidence_for_concept import (
    get_evidence_for_concept,
    get_evidence_for_edge,
)


def __getattr__(name: str) -> Any:
    """Late-bind ``global``-rebound state (PEP 562)."""
    return getattr(_state, name)


__all__ = [
    "_DEFAULT_CONN",
    "_DEFAULT_GRAPH_DB",
    "_EVIDENCE_RETURN",
    "GraphDB",
    "_get_conn",
    "_get_default_graph_db",
    "_is_connection",
    "_row_to_evidence",
    "add_chunk",
    "add_document",
    "get_evidence_for_concept",
    "get_evidence_for_edge",
    "set_default_connection",
]
