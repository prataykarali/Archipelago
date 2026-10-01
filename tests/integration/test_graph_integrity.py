"""Integration test verifying Knowledge Graph integrity against production baseline.

Checks node count, edge integrity, relationship types, and reference consistency
using the canonical okf_graph.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GRAPH_FILE = ROOT / "okf_graph.json"


@pytest.mark.integration
def test_graph_file_exists() -> None:
    """Canonical graph file must exist."""
    assert GRAPH_FILE.exists(), f"Graph file missing: {GRAPH_FILE}"


@pytest.mark.integration
def test_graph_structural_integrity() -> None:
    """Verify graph against structural integrity rules."""
    with open(GRAPH_FILE, encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    assert len(nodes) >= 5000, f"Expected at least 5000 nodes, got {len(nodes)}"
    assert len(edges) > 0, "Graph must contain edges"

    node_ids = set()
    duplicates = set()
    for node in nodes:
        nid = node.get("id")
        assert nid, "Every node must have a non-empty id"
        if nid in node_ids:
            duplicates.add(nid)
        node_ids.add(nid)

    assert len(duplicates) == 0, f"Duplicate node IDs found: {len(duplicates)}"

    valid_relations = {
        "REQUIRES", "UNLOCKS", "RELATED", "MENTIONED_IN", "AUTHORED_BY",
        "BELONGS_TO", "CATEGORIZES", "PROVIDES_TEXT", "HAS_CHUNK", "MENTIONS"
    }

    broken_refs = 0
    self_refs = 0
    for edge in edges:
        src = edge.get("from_id") or edge.get("source")
        tgt = edge.get("to_id") or edge.get("target")
        rel = (edge.get("edge_type") or edge.get("relation") or "").upper()

        if src not in node_ids or tgt not in node_ids:
            broken_refs += 1

        if src == tgt:
            self_refs += 1

        assert rel in valid_relations, f"Invalid relation type: {rel}"

    assert broken_refs == 0, f"Found {broken_refs} broken edges (nodes do not exist)"
    assert self_refs == 0, f"Found {self_refs} self-referencing edges"
