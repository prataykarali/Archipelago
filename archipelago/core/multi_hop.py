"""archipelago/core/multi_hop.py — Multi-Anchor, Multi-Hop Reasoning.

Re-exports multi-hop reasoning primitives from host_inference or standalone implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add host_inference to sys.path if not present so it can import engine modules
_HOST_DIR = Path(__file__).resolve().parents[2] / "host_inference"
if str(_HOST_DIR) not in sys.path:
    sys.path.insert(0, str(_HOST_DIR))

try:
    from engine.multi_hop import (
        DEFAULT_MAX_HOPS,
        PairwisePath,
        RelationshipEdge,
        ResolvedConcept,
        extract_concept_mentions,
        find_directed_and_undirected_path,
        multi_hop_reasoning,
        resolve_concept,
    )
except ImportError:
    # Direct import fallback
    from host_inference.engine.multi_hop import (  # type: ignore
        DEFAULT_MAX_HOPS,
        PairwisePath,
        RelationshipEdge,
        ResolvedConcept,
        extract_concept_mentions,
        find_directed_and_undirected_path,
        multi_hop_reasoning,
        resolve_concept,
    )

__all__ = [
    "DEFAULT_MAX_HOPS",
    "PairwisePath",
    "RelationshipEdge",
    "ResolvedConcept",
    "extract_concept_mentions",
    "find_directed_and_undirected_path",
    "multi_hop_reasoning",
    "resolve_concept",
]
