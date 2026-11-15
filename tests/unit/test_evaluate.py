"""Unit tests for okf/evaluate.py."""

import pytest

from okf.evaluate import compare_concepts, compare_edges, structural_audit

# ---------------------------------------------------------------------------
# compare_concepts tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compare_concepts_perfect_match():
    """extracted == gold → precision=1.0, recall=1.0, f1=1.0."""
    concepts = ["algebra", "calculus", "statistics"]
    result = compare_concepts(concepts, concepts)

    assert result["precision"] == pytest.approx(1.0)
    assert result["recall"] == pytest.approx(1.0)
    assert result["f1"] == pytest.approx(1.0)
    assert result["true_positives"] == 3
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 0


@pytest.mark.unit
def test_compare_concepts_partial_match():
    """2/3 extracted are correct → check precision, recall, f1.

    extracted: ["algebra", "calculus", "wrong_concept"]
    gold:      ["algebra", "calculus", "statistics"]

    TP=2, FP=1, FN=1
    precision = 2/(2+1) = 2/3
    recall    = 2/(2+1) = 2/3
    f1        = 2*(2/3)*(2/3) / (2/3+2/3) = 2/3
    """
    extracted = [
        {"concept_name": "Algebra"},
        {"concept_name": "Calculus"},
        {"concept_name": "Wrong Concept"},
    ]
    gold = ["algebra", "calculus", "statistics"]

    result = compare_concepts(extracted, gold)

    assert result["true_positives"] == 2
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 1
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(2 / 3)
    assert result["f1"] == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# compare_edges tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compare_edges_direction_accuracy():
    """One correctly directed edge + one reversed → direction_accuracy = 0.5.

    Gold:      A→B  (source=a, target=b, type=UNLOCKS)
               C→D  (source=c, target=d, type=UNLOCKS)

    Extracted: A→B  correct direction
               D→C  reversed direction (D→C instead of C→D)

    Both pairs exist undirected, so matched_undir has 2 items.
    direction_accuracy = 1 / 2 = 0.5
    """
    gold = [
        {"source": "a", "target": "b", "type": "UNLOCKS"},
        {"source": "c", "target": "d", "type": "UNLOCKS"},
    ]
    extracted = [
        {"source": "a", "target": "b", "type": "UNLOCKS"},  # correct
        {"source": "d", "target": "c", "type": "UNLOCKS"},  # reversed
    ]

    result = compare_edges(extracted, gold)

    assert "direction_accuracy" in result
    assert result["direction_accuracy"] == pytest.approx(0.5)
    assert "directed" in result
    assert "undirected" in result


# ---------------------------------------------------------------------------
# structural_audit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_structural_audit_clean_graph(sample_graph):
    """The sample_graph fixture has no self-loops and no cycles."""
    conn = sample_graph
    audit = structural_audit(conn)

    assert audit["self_edges"] == [], f"Expected no self-edges, got: {audit['self_edges']}"
    assert audit["cycles"] == [], f"Expected no cycles, got: {audit['cycles']}"
    assert "orphan_count" in audit
    assert "orphan_percentage" in audit


@pytest.mark.unit
def test_structural_audit_self_edge(tmp_kuzu_db):
    """A concept with a REQUIRES self-loop must be detected by structural_audit."""
    conn = tmp_kuzu_db

    # Create a concept node
    conn.execute(
        "CREATE (c:Concept {id: 'loop_concept', name: 'Loop Concept', "
        "concept_type: 'definition', difficulty: 'foundational', summary: 'A self-referential concept'})"
    )

    # Create a self-loop edge: loop_concept REQUIRES loop_concept
    conn.execute(
        "MATCH (a:Concept {id: 'loop_concept'}), (b:Concept {id: 'loop_concept'}) "
        "CREATE (a)-[:REQUIRES {relation_type: 'requires', source: 'test:chunk_001'}]->(b)"
    )

    audit = structural_audit(conn)

    self_edge_names = [se["concept"] for se in audit["self_edges"]]
    assert "Loop Concept" in self_edge_names, (
        f"Expected 'Loop Concept' in self_edges, got: {audit['self_edges']}"
    )
    assert len(audit["self_edges"]) >= 1


# ---------------------------------------------------------------------------
# Research Repair S1 — Gold evaluation correctness & reproducibility tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_s1_identical_export_and_gold_edges_f1_one():
    """Export schema (with provenance 'source' + REQUIRES/UNLOCKS) matching gold yields F1=1.0."""
    gold = {
        "concepts": ["Linear Algebra", "Attention Mechanism", "Transformer"],
        "edges": [
            {"source": "Linear Algebra", "target": "Attention Mechanism", "type": "requires"},
            {"source": "Attention Mechanism", "target": "Transformer", "type": "requires"},
        ],
    }
    # In Kuzu export schema:
    # - 'source' is provenance ('doc1:chunk1'), NOT a node!
    # - REQUIRES: from_name requires to_name => learner path is to_name -> from_name
    # - UNLOCKS: from_name unlocks to_name => learner path is from_name -> to_name
    extracted = {
        "concepts": {
            "linear_algebra": {"name": "Linear Algebra", "sources": [{"doc_id": "doc1"}]},
            "attention_mechanism": {"name": "Attention Mechanism", "sources": [{"doc_id": "doc1"}]},
            "transformer": {"name": "Transformer", "sources": [{"doc_id": "doc1"}]},
        },
        "edges": [
            {
                "from_name": "Attention Mechanism",
                "to_name": "Linear Algebra",
                "edge_type": "REQUIRES",
                "source": "doc1:chunk_001",
            },
            {
                "from_name": "Attention Mechanism",
                "to_name": "Transformer",
                "edge_type": "UNLOCKS",
                "source": "doc1:chunk_002",
            },
        ],
    }
    res = compare_edges(extracted, gold)
    assert res["directed"]["precision"] == pytest.approx(1.0)
    assert res["directed"]["recall"] == pytest.approx(1.0)
    assert res["directed"]["f1"] == pytest.approx(1.0)
    assert res["direction_accuracy"] == pytest.approx(1.0)


@pytest.mark.unit
def test_s1_reversed_prerequisite_direction_not_counted():
    """Reversed prerequisite directions yield directed F1=0.0 while undirected F1=1.0."""
    gold = [
        {"source": "Linear Algebra", "target": "Backpropagation", "type": "requires"},
    ]
    extracted = {
        "edges": [
            {
                # Inverted: claims Linear Algebra requires Backpropagation
                "from_name": "Linear Algebra",
                "to_name": "Backpropagation",
                "edge_type": "REQUIRES",
                "source": "doc1:chunk_001",
            }
        ]
    }
    res = compare_edges(extracted, gold)
    assert res["directed"]["true_positives"] == 0
    assert res["directed"]["f1"] == pytest.approx(0.0)
    assert res["undirected"]["f1"] == pytest.approx(1.0)
    assert res["direction_accuracy"] == pytest.approx(0.0)


@pytest.mark.unit
def test_s1_missing_predictions_lower_recall():
    """Missing predicted edges lower recall while preserving precision=1.0."""
    gold = [
        {"source": "A", "target": "B", "type": "requires"},
        {"source": "B", "target": "C", "type": "requires"},
    ]
    extracted = [{"source": "A", "target": "B", "type": "requires"}]
    res = compare_edges(extracted, gold)
    assert res["directed"]["precision"] == pytest.approx(1.0)
    assert res["directed"]["recall"] == pytest.approx(0.5)
    assert res["directed"]["false_negatives"] == 1


@pytest.mark.unit
def test_s1_extra_predictions_lower_precision_and_related_excluded():
    """Extra directed edges lower precision; RELATED edges do not pollute directed eval."""
    gold = [{"source": "A", "target": "B", "type": "requires"}]
    extracted = {
        "edges": [
            {"from_name": "B", "to_name": "A", "edge_type": "REQUIRES", "source": "doc1:c1"},
            {"from_name": "C", "to_name": "B", "edge_type": "REQUIRES", "source": "doc1:c2"},
            # Undirected RELATED edge must be skipped in directed prerequisite eval
            {"from_name": "A", "to_name": "D", "edge_type": "RELATED", "source": "doc1:c3"},
        ]
    }
    res = compare_edges(extracted, gold)
    assert res["directed"]["true_positives"] == 1
    assert res["directed"]["false_positives"] == 1
    assert res["directed"]["precision"] == pytest.approx(0.5)
    assert res["skipped_related_edges"] == 1


@pytest.mark.unit
def test_s1_duplicate_edges_handled_consistently():
    """Duplicate edges in predictions or gold do not inflate TP/FP/FN."""
    gold = [
        {"source": "A", "target": "B", "type": "requires"},
        {"source": "A", "target": "B", "type": "requires"},
    ]
    extracted = {
        "edges": [
            {"from_name": "B", "to_name": "A", "edge_type": "REQUIRES", "source": "doc1:c1"},
            {"from_name": "A", "to_name": "B", "edge_type": "UNLOCKS", "source": "doc1:c2"},
        ]
    }
    res = compare_edges(extracted, gold)
    assert res["predicted_edge_count"] == 1
    assert res["gold_edge_count"] == 1
    assert res["directed"]["true_positives"] == 1
    assert res["directed"]["f1"] == pytest.approx(1.0)


@pytest.mark.unit
def test_s1_document_scoped_evaluation_excludes_unrelated():
    """Document-scoped evaluation filters out concepts and edges from other documents."""
    extracted = {
        "concepts": {
            "lora": {"name": "LoRA", "sources": [{"doc_id": "papers/Hu2021_LoRA.pdf"}]},
            "attention": {"name": "Attention", "sources": [{"doc_id": "papers/Vaswani2017.pdf"}]},
        },
        "edges": [
            {
                "from_name": "LoRA",
                "to_name": "Fine-Tuning",
                "edge_type": "REQUIRES",
                "source": "papers/Hu2021_LoRA.pdf:c1",
            },
            {
                "from_name": "Transformer",
                "to_name": "Attention",
                "edge_type": "REQUIRES",
                "source": "papers/Vaswani2017.pdf:c1",
            },
        ],
    }
    c_res = compare_concepts(extracted["concepts"], ["Low-Rank Adaptation"], doc_id="papers/Hu2021_LoRA.pdf")
    assert c_res["true_positives"] == 1
    assert c_res["false_positives"] == 0
    assert c_res["precision"] == pytest.approx(1.0)

    e_res = compare_edges(
        extracted,
        [{"source": "Fine-Tuning", "target": "Low-Rank Adaptation", "type": "requires"}],
        doc_id="papers/Hu2021_LoRA.pdf",
    )
    assert e_res["predicted_edge_count"] == 1
    assert e_res["directed"]["f1"] == pytest.approx(1.0)


@pytest.mark.unit
def test_s1_missing_doc_id_reported_as_unscopable():
    """Concepts and edges lacking doc provenance are excluded and reported honestly."""
    extracted = {
        "concepts": {
            "lora": {"name": "LoRA", "sources": [{"doc_id": "doc1"}]},
            "orphan_no_prov": {"name": "Orphan Concept", "sources": []},
        },
        "edges": [
            {"from_name": "LoRA", "to_name": "Rank", "edge_type": "REQUIRES", "source": "doc1:c1"},
            {"from_name": "Foo", "to_name": "Bar", "edge_type": "REQUIRES", "source": "pearson_batch1"},
            {"from_name": "Baz", "to_name": "Qux", "edge_type": "REQUIRES", "source": None},
        ],
    }
    c_res = compare_concepts(extracted["concepts"], ["Low-Rank Adaptation"], doc_id="doc1")
    assert c_res["unscopable_concepts"] == 1
    assert c_res["false_positives"] == 0

    e_res = compare_edges(
        extracted,
        [{"source": "Rank", "target": "Low-Rank Adaptation", "type": "requires"}],
        doc_id="doc1",
    )
    assert e_res["unscopable_edges"] == 2
    assert e_res["directed"]["f1"] == pytest.approx(1.0)


@pytest.mark.unit
def test_s1_empty_gold_and_prediction_conventions():
    """Both empty -> 1.0; one empty -> 0.0 for both concepts and edges."""
    both_empty_c = compare_concepts([], [])
    assert both_empty_c["f1"] == pytest.approx(1.0)

    empty_pred_c = compare_concepts([], ["Algebra"])
    assert empty_pred_c["f1"] == pytest.approx(0.0)
    assert empty_pred_c["false_negatives"] == 1

    empty_gold_c = compare_concepts(["Algebra"], [])
    assert empty_gold_c["f1"] == pytest.approx(0.0)
    assert empty_gold_c["false_positives"] == 1

    both_empty_e = compare_edges([], [])
    assert both_empty_e["directed"]["f1"] == pytest.approx(1.0)

    empty_pred_e = compare_edges([], [{"source": "A", "target": "B", "type": "requires"}])
    assert empty_pred_e["directed"]["f1"] == pytest.approx(0.0)
    assert empty_pred_e["directed"]["false_negatives"] == 1


@pytest.mark.unit
def test_s1_normalization_no_false_matches():
    """Hyphen/alias normalization matches genuine equivalents without conflating distinct concepts."""
    gold = [{"source": "Self-Attention", "target": "Low-Rank Adaptation", "type": "requires"}]
    extracted_match = [
        {"source": "self attention", "target": "LoRA", "type": "requires"},
    ]
    assert compare_edges(extracted_match, gold)["directed"]["f1"] == pytest.approx(1.0)

    extracted_distinct = [
        {"source": "Attention", "target": "Low-Rank Adaptation", "type": "requires"},
    ]
    assert compare_edges(extracted_distinct, gold)["directed"]["f1"] == pytest.approx(0.0)


@pytest.mark.unit
def test_s1_structural_dag_validity_independent_of_semantic_correctness(tmp_kuzu_db, tmp_path):
    """A structurally valid DAG (0 cycles, 0 self-loops) can still have 0.0 semantic Edge F1."""
    conn = tmp_kuzu_db
    conn.execute(
        "CREATE (a:Concept {id: 'c1', name: 'Concept One', concept_type: 'definition', "
        "difficulty: 'foundational', summary: 'One'})"
    )
    conn.execute(
        "CREATE (b:Concept {id: 'c2', name: 'Concept Two', concept_type: 'definition', "
        "difficulty: 'intermediate', summary: 'Two'})"
    )
    conn.execute(
        "MATCH (a:Concept {id: 'c1'}), (b:Concept {id: 'c2'}) "
        "CREATE (a)-[:REQUIRES {relation_type: 'requires', source: 'doc1:c1'}]->(b)"
    )
    audit = structural_audit(conn)
    assert audit["cycles"] == []
    assert audit["self_edges"] == []

    gold_file = tmp_path / "gold.json"
    gold_file.write_text(
        '{"concepts": ["Concept One", "Concept Two"], '
        '"edges": [{"source": "Concept One", "target": "Concept Two", "type": "requires"}]}',
        encoding="utf-8",
    )
    from okf.evaluate import evaluate_pipeline

    report = evaluate_pipeline(conn, str(gold_file))
    # Structural audit is clean, but c1 REQUIRES c2 means c2 -> c1 (reversed vs gold c1 -> c2)
    assert report["structural_audit"]["cycles"] == []
    assert report["edge_comparison"]["directed"]["f1"] == pytest.approx(0.0)
