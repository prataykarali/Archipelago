"""Bounded Subgraph Generator for Archipelago.

Enforces strict bounded subgraph sizes (5 to 10 nodes for Mode C / Mode B,
and <= 3 nodes for Mode A) to prevent overwhelming multi-hop graph dumps.
Includes pruning by pedagogical relevance, backfilling with foundational
prerequisites, and weak connectivity guarantees."""
from __future__ import annotations

from collections import deque  # noqa: F401
from dataclasses import asdict, dataclass, field  # noqa: F401
import hashlib  # noqa: F401
from typing import Any  # noqa: F401

from .part01_subgraphnode import (  # noqa: F401
    SubgraphNode,
    SubgraphEdge,
    BoundedSubgraph,
    _DIFFICULTY_RANK,
    _UNIVERSAL_FOUNDATIONS,
    _normalize_id,
    _build_name_to_id_index,
    _resolve_id,
    _get_node_info,
    _get_direct_prereqs,
    _get_direct_unlocks,
    _get_related_neighbors,
    _induce_subgraph_edges,
)
from .part02_ensure_weak_connectivity import (  # noqa: F401
    _ensure_weak_connectivity,
    generate_bounded_subgraph,
)

__all__ = ["SubgraphNode", "SubgraphEdge", "BoundedSubgraph", "_DIFFICULTY_RANK", "_UNIVERSAL_FOUNDATIONS", "_normalize_id", "_build_name_to_id_index", "_resolve_id", "_get_node_info", "_get_direct_prereqs", "_get_direct_unlocks", "_get_related_neighbors", "_induce_subgraph_edges", "_ensure_weak_connectivity", "generate_bounded_subgraph"]
