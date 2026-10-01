"""Unit tests for knowledge graph topological and schema edge cases.

Tests boundary conditions: zero nodes, single node, disconnected nodes,
duplicate edges, self-referencing cycles, and invalid relationship types.
"""

from __future__ import annotations

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_graph import build_report, VALID_RELATIONS


@pytest.mark.unit
def test_graph_zero_nodes() -> None:
    """Empty graph data payload should report failure gracefully."""
    empty_graph = {"nodes": [], "edges": []}
    report = build_report(empty_graph)
    assert report["node_count"] == 0
    assert report["status"] == "FAIL"


@pytest.mark.unit
def test_graph_single_isolated_node() -> None:
    """A graph with 1 isolated node has 1 orphan and 0 edges."""
    single_node = {
        "nodes": [{"id": "node_1", "concept_name": "Lone Node"}],
        "edges": [],
    }
    report = build_report(single_node)
    assert report["node_count"] == 1
    assert report["orphan_nodes"] == 1
    assert report["edge_count"] == 0


@pytest.mark.unit
def test_graph_self_referencing_edge_detected() -> None:
    """Edges where source == target must be flagged."""
    graph_with_self_ref = {
        "nodes": [
            {"id": "node_a", "concept_name": "Node A"},
            {"id": "node_b", "concept_name": "Node B"},
        ],
        "edges": [
            {"from_id": "node_a", "to_id": "node_a", "edge_type": "REQUIRES", "source_ref": "doc:1"},
            {"from_id": "node_a", "to_id": "node_b", "edge_type": "REQUIRES", "source_ref": "doc:1"},
        ],
    }
    report = build_report(graph_with_self_ref)
    assert report["self_refs"] == 1
    assert report["status"] == "FAIL"


@pytest.mark.unit
def test_graph_invalid_relation_type() -> None:
    """Relationships outside the defined ontology must be caught."""
    graph_invalid_rel = {
        "nodes": [
            {"id": "node_a", "concept_name": "Node A"},
            {"id": "node_b", "concept_name": "Node B"},
        ],
        "edges": [
            {"from_id": "node_a", "to_id": "node_b", "edge_type": "MADE_UP_RELATION", "source_ref": "doc:1"},
        ],
    }
    report = build_report(graph_invalid_rel)
    assert report["invalid_relations"] == 1
    assert report["status"] == "FAIL"


@pytest.mark.unit
def test_graph_duplicate_edges() -> None:
    """Duplicate edges between the same nodes with the same relation must be flagged."""
    graph_dup_edges = {
        "nodes": [
            {"id": "node_a", "concept_name": "Node A"},
            {"id": "node_b", "concept_name": "Node B"},
        ],
        "edges": [
            {"from_id": "node_a", "to_id": "node_b", "edge_type": "REQUIRES", "source_ref": "doc:1"},
            {"from_id": "node_a", "to_id": "node_b", "edge_type": "REQUIRES", "source_ref": "doc:1"},
        ],
    }
    report = build_report(graph_dup_edges)
    assert report["duplicate_edges"] == 1
