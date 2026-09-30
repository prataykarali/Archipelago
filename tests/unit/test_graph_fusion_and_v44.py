"""Unit tests for GraphFusionEngine & V44DatasetGenerator."""

from pathlib import Path
import json
import pytest

from archipelago.graph.graph_fusion import GraphFusionEngine
from archipelago.dataset.v44_generator import V44DatasetGenerator


def test_kahn_dag_cycle_gate():
    fusion = GraphFusionEngine()
    existing_nodes = {"a", "b", "c"}
    existing_edges = {("a", "b"), ("b", "c")}  # a -> b -> c

    # Case 1: Valid new edges that do not introduce cycles
    new_nodes = {"d"}
    new_edges = {("c", "d")}
    is_valid, rejected = fusion.validate_dag_kahn(existing_nodes, existing_edges, new_nodes, new_edges)
    assert is_valid is True
    assert len(rejected) == 0

    # Case 2: Direct cycle (c -> a introduces a -> b -> c -> a)
    cyclic_edges = {("c", "a")}
    is_valid_c, rejected_c = fusion.validate_dag_kahn(existing_nodes, existing_edges, set(), cyclic_edges)
    assert is_valid_c is False
    assert ("c", "a") in rejected_c

    # Case 3: Self-loop (b -> b)
    self_loop = {("b", "b")}
    is_valid_s, rejected_s = fusion.validate_dag_kahn(existing_nodes, existing_edges, set(), self_loop)
    assert is_valid_s is False
    assert ("b", "b") in rejected_s


def test_batch_node_threshold_enforcement():
    fusion = GraphFusionEngine()
    # Generate 180 concepts (exceeding 150 threshold)
    concepts = [
        {"id": f"concept_{i}", "name": f"Concept {i}", "prerequisites": []}
        for i in range(180)
    ]
    res = fusion.merge_batch(concepts, kuzu_engine=None, max_batch_nodes=150)
    assert res["success"] is True
    assert res["total_candidates"] <= 150


def test_v44_dataset_synthesis(tmp_path):
    gen = V44DatasetGenerator("data/catalogs/pearson_bookshelf.json")
    test_concepts = [
        {
            "id": "computer_networks",
            "name": "Computer Networks",
            "domain": "Computer Networks & Security",
            "definition": "Interconnected computing devices sharing data and resources.",
            "difficulty": "foundational",
            "source_book": "Digital Signal Processing, 4e",
            "page_number": 25,
            "prerequisites": [{"id": "digital_transmission", "name": "Digital Transmission"}],
        }
    ]

    out_file = tmp_path / "test_v44.jsonl"
    res = gen.export_dataset(test_concepts, output_path=out_file, sync_to_hf=False)
    assert res["success"] is True
    assert res["total_examples"] >= 3  # Explanation + Reasoning + MCQ
    assert out_file.is_file()

    with open(out_file) as f:
        lines = [json.loads(line) for line in f]

    # Verify task 1: Explanation with citation
    exp = next(ex for ex in lines if ex["task"] == "pedagogical_explanation")
    assert exp["concept_id"] == "computer_networks"
    assert "pdfviewer.html" in exp["source_citation"]["reader_deep_link"]
    assert "page/25" in exp["source_citation"]["reader_deep_link"]

    # Verify task 2: Reasoning chain
    rea = next(ex for ex in lines if ex["task"] == "prerequisite_reasoning")
    assert rea["prerequisite_name"] == "Digital Transmission"

    # Verify task 3: 4-Option MCQ
    mcq = next(ex for ex in lines if ex["task"] == "diagnostic_mcq")
    assert len(mcq["options"]) == 4
    assert set(mcq["options"].keys()) == {"A", "B", "C", "D"}
    assert mcq["correct_option"] == "A"
    assert "pdfviewer.html" in mcq["reader_deep_link"]
