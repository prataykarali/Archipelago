"""Bounded Subgraph Generator for Archipelago runtime.

Enforces strict bounded subgraph sizes (5 to 10 nodes for Mode C / Mode B,
and <= 3 nodes for Mode A) to prevent overwhelming multi-hop graph dumps.
Includes pruning by pedagogical relevance, backfilling with foundational
prerequisites, and weak connectivity guarantees.
"""

from __future__ import annotations

# Re-export from src.archipelago.graph.subgraph
from src.archipelago.graph.subgraph import (
    BoundedSubgraph,
    SubgraphEdge,
    SubgraphNode,
    generate_bounded_subgraph,
)

__all__ = [
    "BoundedSubgraph",
    "SubgraphEdge",
    "SubgraphNode",
    "generate_bounded_subgraph",
]
