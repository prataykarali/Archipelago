"""Shim: okf.graph_db → okf.graph.* (feature split, ≤500 LOC modules)."""

from typing import Any

from okf.graph.common import (
    _DEFAULT_DB_PATH,
    _kuzu_escape,
    _kuzu_literal,
)

# Re-bind module-level names so tests can read/write okf.graph_db._DEFAULT_CONN
# and stay in sync with okf.graph.evidence (single source of truth via setattr).
import okf.graph.evidence as _evidence
from okf.graph.evidence import (
    _DEFAULT_CONN,
    _DEFAULT_GRAPH_DB,
    GraphDB,
    add_chunk,
    add_document,
    get_evidence_for_concept,
    get_evidence_for_edge,
    set_default_connection,
)
from okf.graph.export import enforce_dag, export_graph, get_edge_provenance, get_orphan_ratio
from okf.graph.ingest import ingest_to_kuzu


def __getattr__(name: str) -> Any:
    if name in ("_DEFAULT_CONN", "_DEFAULT_GRAPH_DB"):
        return getattr(_evidence, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value: Any) -> None:
    if name in ("_DEFAULT_CONN", "_DEFAULT_GRAPH_DB"):
        setattr(_evidence, name, value)
        return
    globals()[name] = value


__all__ = [
    "_DEFAULT_CONN",
    "_DEFAULT_DB_PATH",
    "_DEFAULT_GRAPH_DB",
    "GraphDB",
    "_kuzu_escape",
    "_kuzu_literal",
    "add_chunk",
    "add_document",
    "enforce_dag",
    "export_graph",
    "get_edge_provenance",
    "get_evidence_for_concept",
    "get_evidence_for_edge",
    "get_orphan_ratio",
    "ingest_to_kuzu",
    "set_default_connection",
]
