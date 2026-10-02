"""evidence.py — Kùzu graph submodule."""
from __future__ import annotations

import json  # noqa: F401
from okf.graph.common import (
    _DEFAULT_DB_PATH, _kuzu_escape, _kuzu_literal, _SCHEMA_DDL,
    _create_schema, _migrate_schema, logger, BASE_DIR,
)  # noqa: F401
from okf.util import create_concept_id  # noqa: F401
import os  # noqa: F401

from .part01_default_conn import (  # noqa: F401
    set_default_connection,
    _get_default_graph_db,
)
from .part02_evidence_return import (  # noqa: F401
    _EVIDENCE_RETURN,
    _row_to_evidence,
    GraphDB,
    _get_conn,
    _is_connection,
    add_document,
    add_chunk,
)
from .part03_get_evidence_for_concept import (  # noqa: F401
    get_evidence_for_concept,
    get_evidence_for_edge,
)
from . import part01_default_conn as _state  # noqa: F401

def __getattr__(name: str):
    """Late-bind ``global``-rebound state (PEP 562)."""
    return getattr(_state, name)


__all__ = ["_EVIDENCE_RETURN", "_row_to_evidence", "_DEFAULT_CONN", "_DEFAULT_GRAPH_DB", "GraphDB", "set_default_connection", "_get_default_graph_db", "_get_conn", "_is_connection", "add_document", "add_chunk", "get_evidence_for_concept", "get_evidence_for_edge"]
