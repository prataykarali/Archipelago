"""Unit tests for LibQwenConceptExtractor & Ingestion Rules."""

import pytest

from archipelago.ingestion.lib_qwen_extractor import (
    LibQwenConceptExtractor,
    canonical_concept_id,
    clean_json_payload,
    is_negative_sample,
)


def test_clean_json_payload():
    # 1. Bare JSON array wrapped in markdown fences
    fenced_array = "```json\n[{\"name\": \"Attention\", \"definition\": \"Dynamically weight tokens.\", \"difficulty\": \"intermediate\"}]\n```"
    res1 = clean_json_payload(fenced_array)
    assert "concepts" in res1
    assert len(res1["concepts"]) == 1
    assert res1["concepts"][0]["name"] == "Attention"

    # 2. Top-level object with concepts key
    fenced_obj = "```\n{\"concepts\": [{\"name\": \"BERT\", \"definition\": \"Bidirectional encoder.\", \"difficulty\": \"intermediate\"}]}\n```"
    res2 = clean_json_payload(fenced_obj)
    assert len(res2["concepts"]) == 1
    assert res2["concepts"][0]["name"] == "BERT"

    # 3. Invalid payload fallback
    assert clean_json_payload("not json at all") == {"concepts": []}


def test_is_negative_sample():
    # Short text
    assert is_negative_sample("Too short") is True

    # Bibliography page
    bib = "Bibliography\n1. Vaswani et al. Attention is all you need. 2017.\n2. Devlin et al. BERT. 2018." + " " * 100
    assert is_negative_sample(bib) is True

    # Preface page
    preface = "Preface\nThis book is intended for undergraduate students studying computer networks." + " " * 100
    assert is_negative_sample(preface) is True

    # Legitimate pedagogical text
    real = (
        "In this chapter, we discuss Dijkstra's shortest path algorithm. "
        "The algorithm maintains a set of visited vertices and repeatedly selects "
        "the unvisited vertex with the minimum tentative distance. "
        "It relies on priority queues and graph adjacency lists."
    )
    assert is_negative_sample(real) is False


def test_second_pass_relation_resolver():
    extractor = LibQwenConceptExtractor()

    raw_concepts = [
        {
            "id": "transformer",
            "name": "Transformer",
            "definition": "Sequence model based on attention.",
            "difficulty": "intermediate",
            "prerequisites": ["Attention Mechanism"],
        },
        {
            "id": "attention_mechanism",
            "name": "Attention Mechanism",
            "definition": "Weighted combination of input tokens.",
            "difficulty": "foundational",
            # Reciprocal cycle: Attention Mechanism lists Transformer as prerequisite
            "prerequisites": ["Transformer", "Attention Mechanism"],  # includes self-loop
        },
    ]

    resolved = extractor.second_pass_relation_resolver(raw_concepts)
    assert len(resolved) == 2

    # Transformer requires Attention Mechanism
    t_node = next(c for c in resolved if c["id"] == "transformer")
    assert any(p["id"] == "attention_mechanism" for p in t_node["prerequisites"])

    # Attention Mechanism must NOT have reciprocal prerequisite on Transformer or self-loop
    a_node = next(c for c in resolved if c["id"] == "attention_mechanism")
    prereq_ids = [p["id"] for p in a_node["prerequisites"]]
    assert "transformer" not in prereq_ids, "Reciprocal cycle should be eliminated"
    assert "attention_mechanism" not in prereq_ids, "Self-loop should be eliminated"


def test_live_lib_qwen_extraction():
    extractor = LibQwenConceptExtractor()
    text = (
        "Backpropagation is an algorithm for calculating gradients in multilayer artificial neural networks. "
        "It applies the chain rule of calculus recursively backward from the output layer to the input layer. "
        "Gradients computed via backpropagation are used by gradient descent optimizers to update synaptic weights."
    )

    concepts = extractor.extract_from_chunk(text, book_title="Deep Learning", page_number=15, domain="AI & Machine Learning")
    assert isinstance(concepts, list)
    if concepts:  # If Ollama is running lib-qwen
        c_names = [c["name"].lower() for c in concepts]
        assert any("backpropagation" in n or "gradient" in n or "neural" in n for n in c_names)
