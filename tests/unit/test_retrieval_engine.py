"""Unit tests for TwoPassHybridRetriever, BFS Pathfinding, and Topic Suggestion Engine."""
from __future__ import annotations

import pytest
from archipelago.core.retrieval import (
    MAX_CHUNKS,
    MAX_PREREQS,
    MAX_UNLOCKS,
    TwoPassHybridRetriever,
)


@pytest.fixture
def mock_concepts():
    return {
        "transformer": {
            "name": "Transformer Architecture",
            "difficulty": "intermediate",
            "summary": "Attention-based sequence model.",
            "prerequisites": ["attention_mechanism", "linear_algebra"],
            "unlocks": ["bert", "gpt"],
            "sources": [
                {"doc_id": "Vaswani2017.pdf", "chunk_id": "c1", "page_number": 3, "text_passage": "Attention is all you need."},
                {"doc_id": "Vaswani2017.pdf", "chunk_id": "c2", "page_number": 4, "text_passage": "Multi-head attention allows..."},
            ],
        },
        "attention_mechanism": {
            "name": "Attention Mechanism",
            "difficulty": "foundational",
            "summary": "Soft alignment of sequence tokens.",
            "prerequisites": ["linear_algebra"],
            "unlocks": ["transformer"],
            "sources": [],
        },
        "linear_algebra": {
            "name": "Linear Algebra",
            "difficulty": "foundational",
            "summary": "Vectors, matrices, and transformations.",
            "prerequisites": [],
            "unlocks": ["attention_mechanism"],
            "sources": [],
        },
        "bert": {
            "name": "BERT",
            "difficulty": "advanced",
            "summary": "Bidirectional Encoder Representations from Transformers.",
            "prerequisites": ["transformer"],
            "unlocks": [],
            "sources": [],
        },
        "gpt": {
            "name": "GPT",
            "difficulty": "advanced",
            "summary": "Generative Pre-trained Transformer.",
            "prerequisites": ["transformer"],
            "unlocks": [],
            "sources": [],
        },
    }


@pytest.fixture
def retriever(mock_concepts):
    return TwoPassHybridRetriever(concepts_data=mock_concepts)


def test_anchor_resolution_exact_and_fuzzy(retriever):
    # Exact match
    hits = retriever.resolve_anchor("transformer")
    assert len(hits) > 0
    assert hits[0][0] == "transformer"
    assert hits[0][1] == 1.0

    # Fuzzy match with spelling typo
    fuzzy_hits = retriever.resolve_anchor("transformr")
    assert len(fuzzy_hits) > 0
    assert fuzzy_hits[0][0] == "transformer"
    assert fuzzy_hits[0][1] >= 0.70


def test_shortest_path_dual_entity(retriever):
    # Shortest path between linear_algebra and bert
    path = retriever.find_shortest_path("linear_algebra", "bert")
    assert path is not None
    assert path[0] == "linear_algebra"
    assert path[-1] == "bert"
    # Should traverse: linear_algebra -> attention_mechanism -> transformer -> bert
    assert "transformer" in path


def test_upstream_prerequisites_bounded(retriever):
    prereqs = retriever.get_upstream_prerequisites("transformer", max_hops=2)
    assert len(prereqs) <= MAX_PREREQS
    prereq_ids = [p["id"] for p in prereqs]
    assert "attention_mechanism" in prereq_ids


def test_downstream_unlocks_bounded(retriever):
    unlocks = retriever.get_downstream_unlocks("transformer", max_hops=2)
    assert len(unlocks) <= MAX_UNLOCKS
    unlock_ids = [u["id"] for u in unlocks]
    assert "bert" in unlock_ids or "gpt" in unlock_ids


def test_evidence_chunks_lineage(retriever):
    chunks = retriever.get_evidence_chunks("transformer", max_chunks=MAX_CHUNKS)
    assert len(chunks) <= MAX_CHUNKS
    assert len(chunks) == 2
    assert chunks[0]["doc_id"] == "Vaswani2017.pdf"
    assert chunks[0]["page_number"] == 3
    assert "Attention is all you need" in chunks[0]["text_passage"]


def test_topic_suggestion_fuzzy_discovery(retriever):
    # Ambiguous term "attentn"
    suggestions = retriever.suggest_topics("attentn", top_k=3)
    assert len(suggestions) > 0
    top_cand = suggestions[0]
    assert top_cand["id"] == "attention_mechanism"
    assert "prerequisites" in top_cand
    assert "unlocks" in top_cand
