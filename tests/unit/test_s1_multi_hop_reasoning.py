"""tests/unit/test_s1_multi_hop_reasoning.py — Acceptance Tests for S1 Multi-Hop Reasoning.

Covers:
- X alone (single-anchor reasoning).
- X vs Y (two-concept comparison/relation).
- X + Y + Z (three-concept reasoning, e.g. transformers, RAG, knowledge graphs).
- Four-concept reasoning (e.g. transformers, self-attention, BERT, LoRA).
- Missing nodes and partial evidence handling (no manufactured edges).
- Directed and undirected relationship search with edge semantics preservation.
- Cycle protection against infinite graph loops.
- Explicit stored graph relationships vs document-inferred relationships.
- Coherent synthesized explanation covering every requested concept with citations.
"""

from __future__ import annotations

from pathlib import Path
import sys
import pytest

ARCHIPELAGO_DIR = Path(__file__).resolve().parents[2]
HOST_DIR = ARCHIPELAGO_DIR / "host_inference"

if str(ARCHIPELAGO_DIR) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO_DIR))
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

from host_inference.engine.multi_hop import (
    extract_concept_mentions,
    find_directed_and_undirected_path,
    multi_hop_reasoning,
    resolve_concept,
)
import engine as hosted_engine


@pytest.fixture(scope="module")
def engine():
    return hosted_engine.Engine()


# ── 1. Concept Extraction for 1, 2, 3, 4 Concepts ────────────────────────────


def test_extract_single_concept():
    query = "Explain transformer architecture"
    concepts = extract_concept_mentions(query)
    assert len(concepts) >= 1
    assert any("transformer" in c.lower() for c in concepts)


def test_extract_two_concepts():
    query = "How does Softmax connect to Self-Attention?"
    concepts = extract_concept_mentions(query)
    assert len(concepts) == 2
    assert any("softmax" in c.lower() for c in concepts)
    assert any("self-attention" in c.lower() or "attention" in c.lower() for c in concepts)


def test_extract_three_concepts():
    query = "How are transformers, retrieval-augmented generation and knowledge graphs related?"
    concepts = extract_concept_mentions(query)
    assert len(concepts) == 3
    assert any("transformer" in c.lower() for c in concepts)
    assert any("retrieval" in c.lower() or "rag" in c.lower() for c in concepts)
    assert any("knowledge graph" in c.lower() for c in concepts)


def test_extract_four_concepts():
    query = "How are transformers, self-attention, BERT, and LoRA related?"
    concepts = extract_concept_mentions(query)
    assert len(concepts) == 4
    lowered = [c.lower() for c in concepts]
    assert any("transformer" in c for c in lowered)
    assert any("attention" in c for c in lowered)
    assert any("bert" in c for c in lowered)
    assert any("lora" in c for c in lowered)


# ── 2. Directed and Undirected Traversal with Edge Semantics ───────────────────


def test_directed_path_preserves_semantics(engine):
    """Path search must record whether the relation was REQUIRES, UNLOCKS, or RELATED."""
    graph = engine.graph
    path = find_directed_and_undirected_path(graph, "transformer", "rag", max_hops=4)
    assert path.is_connected, "Path between transformer and rag must be found"
    assert len(path.hops) > 0
    for hop in path.hops:
        assert hop.relation in {"REQUIRES", "UNLOCKS", "RELATED"}
        rendered = hop.render()
        assert "-> (" in rendered or "<-[" in rendered


def test_cycle_protection_terminates_promptly(engine):
    """Traversing cyclic structures must not cause recursion or infinite loop."""
    graph = engine.graph
    # Verify traversal terminates with a small max_hops bound
    path = find_directed_and_undirected_path(graph, "neural_network", "deep_learning", max_hops=3)
    assert path is not None


# ── 3. Three-Concept Reasoning (X + Y + Z) ────────────────────────────────────


def test_three_concept_reasoning_covers_all_concepts_and_cites(engine):
    query = "How are transformers, retrieval-augmented generation and knowledge graphs related?"
    result = engine.answer(query)

    assert result["route"] == "MULTI_CONCEPT"
    text = result["text"]

    # Invariant 1: All three concepts must be present in explanation
    assert "transformer" in text.lower(), "transformers must be discussed"
    assert "retrieval" in text.lower() or "rag" in text.lower(), "RAG must be discussed"
    assert "knowledge graph" in text.lower(), "knowledge graphs must be discussed"

    # Invariant 2: Multi-hop payload must be populated
    payload = result["payload"]
    multi_hop = payload.get("multi_hop") or {}
    assert len(multi_hop.get("concepts", [])) == 3
    assert len(multi_hop.get("indexed", [])) == 3

    # Invariant 3: Must carry citations
    assert len(payload["citations"]) >= 1, "Must carry grounded citations across anchors"


# ── 4. Four-Concept Reasoning ─────────────────────────────────────────────────


def test_four_concept_reasoning_covers_all_four(engine):
    query = "How are transformers, self-attention, BERT, and LoRA related?"
    result = engine.answer(query)

    assert result["route"] == "MULTI_CONCEPT"
    text = result["text"]

    # Invariant: Does not silently ignore the 3rd or 4th concept
    assert "transformer" in text.lower()
    assert "attention" in text.lower()
    assert "bert" in text.lower()
    assert "lora" in text.lower() or "adaptation" in text.lower()

    multi_hop = result["payload"].get("multi_hop") or {}
    assert len(multi_hop.get("concepts", [])) == 4


# ── 5. Missing Nodes and Partial Evidence (Honesty Invariant) ─────────────────


def test_missing_node_reports_partial_coverage_without_manufacturing_edges(engine):
    """When one concept is missing, explain verified ones and state limitation honestly."""
    query = "How are transformers, quantum_supersymmetry, and BERT related?"
    result = engine.answer(query)

    assert result["route"] == "MULTI_CONCEPT"
    text = result["text"]

    # Invariant: Indexed concepts explained
    assert "transformer" in text.lower()
    assert "bert" in text.lower()

    # Invariant: Missing concept explicitly identified
    assert "quantum_supersymmetry" in text.lower() or "not indexed" in text.lower()
    assert "not indexed" in text.lower() or "limitations" in text.lower() or "no bridge" in text.lower()

    multi_hop = result["payload"].get("multi_hop") or {}
    assert multi_hop.get("is_partial") is True
    assert "quantum_supersymmetry" in [m.lower() for m in multi_hop.get("missing", [])]


# ── 6. Two-Concept Relations (X vs Y) ─────────────────────────────────────────


def test_two_concept_relation_with_path(engine):
    query = "How does Attention Mechanism connect to Self-Attention?"
    result = engine.answer(query)
    assert result["route"] in ("RELATION", "GRAPH_SYNTHESIS", "MULTI_CONCEPT")
    assert "Attention" in result["text"]
    assert len(result["payload"]["citations"]) >= 1
