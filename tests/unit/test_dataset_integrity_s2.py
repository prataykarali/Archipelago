"""Reproducibility and dataset integrity tests for Research Repair S2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archipelago.eval.dataset_integrity import (
    assert_clean_benchmark_record,
    build_document_disjoint_splits,
    detect_cross_split_contamination,
    jaccard_similarity,
    normalize_doc_id,
    template_skeleton_hash,
)
from okf.evaluate import compare_concepts, compare_edges


def _synthetic_rows() -> list[dict]:
    docs = [
        ("https://arxiv.org/abs/1706.03762v2", "Attention Is All You Need introduces scaled dot-product attention."),
        ("10.48550/arXiv.1706.03762", "Multi-head attention projects queries keys and values into subspaces."),
        ("papers/Hu2021_LoRA.pdf", "LoRA freezes pretrained weights and injects trainable rank matrices."),
        ("papers/Hu2021_LoRA.pdf", "Rank decomposition reduces trainable parameters by ten thousand times."),
        ("papers/Lewis2020_RAG.pdf", "RAG combines dense retrieval with sequence to sequence generation."),
        ("papers/Edge2024_GraphRAG.pdf", "GraphRAG builds entity graphs and hierarchical community summaries."),
        ("papers/Kwon2023_vLLM.pdf", "PagedAttention manages KV cache blocks using virtual memory paging."),
    ]
    return [
        {
            "task": "academic_okf",
            "doc_id": did,
            "messages": [
                {"role": "user", "content": text},
                {"role": "assistant", "content": "[]"},
            ],
        }
        for did, text in docs
    ]


@pytest.mark.unit
def test_s2_document_disjoint_split_integrity():
    """All chunks from the same canonical document stay in the same partition."""
    splits, manifest = build_document_disjoint_splits(_synthetic_rows(), seed=42)
    assert manifest["contamination_check"]["is_document_disjoint"] is True
    assert manifest["doc_counts"]["total"] == 5  # 1706.03762v2 and 10.48550/arXiv.1706.03762 merge!
    for pair_overlap in manifest["contamination_check"]["doc_id_overlaps"].values():
        assert pair_overlap == []
    assert sum(manifest["row_counts"].values()) == 7


@pytest.mark.unit
def test_s2_duplicate_near_dup_and_template_detection():
    """Exact duplicates are dropped; near-duplicates and template skeletons are detected."""
    rows = _synthetic_rows()
    # Add an exact duplicate of a different doc's text under another doc_id
    rows.append(
        {
            "task": "academic_okf",
            "doc_id": "papers/DupDoc.pdf",
            "messages": rows[2]["messages"],
        }
    )
    splits, manifest = build_document_disjoint_splits(rows, seed=42)
    assert manifest["dropped_exact_duplicates"] == 1
    assert manifest["contamination_check"]["is_exact_deduped"] is True

    # Near-duplicate detection
    a = "LoRA freezes pretrained weights and injects trainable rank decomposition matrices."
    b = "LoRA freezes pretrained weights and injects trainable rank decomposition matrix."
    assert jaccard_similarity(a, b) >= 0.65

    # Template-equivalent skeleton detection
    t1 = "Paper Attention Is All You Need achieved 28.4 BLEU on WMT14."
    t2 = "Paper Direct Preference Optimization achieved 91.2 WinRate on AnthropicHH."
    assert template_skeleton_hash(t1) == template_skeleton_hash(t2)


@pytest.mark.unit
def test_s2_stable_splits_under_repeated_runs():
    """Repeated runs with the same seed produce byte-identical document assignments."""
    rows = _synthetic_rows()
    splits1, m1 = build_document_disjoint_splits(rows, seed=123)
    splits2, m2 = build_document_disjoint_splits(rows, seed=123)
    assert m1["documents"] == m2["documents"]
    assert splits1 == splits2


@pytest.mark.unit
def test_s2_source_document_identity_normalization():
    """Equivalent arXiv, DOI, and versioned identifiers normalize identically."""
    assert normalize_doc_id("https://arxiv.org/abs/1706.03762v5") == "arxiv:1706.03762"
    assert normalize_doc_id("10.48550/arXiv.1706.03762") == "arxiv:1706.03762"
    assert normalize_doc_id("1706.03762") == "arxiv:1706.03762"
    assert normalize_doc_id("https://doi.org/10.1145/3600006.3613165") == "doi:10.1145/3600006.3613165"


@pytest.mark.unit
def test_s2_no_training_test_overlap():
    """detect_cross_split_contamination flags leaked docs and passes clean splits."""
    leaked = {
        "train": [{"doc_id": "papers/Hu2021_LoRA.pdf", "instruction": "a", "output": "b"}],
        "test": [{"doc_id": "papers/Hu2021_LoRA.pdf", "instruction": "c", "output": "d"}],
    }
    report = detect_cross_split_contamination(leaked)
    assert report["is_document_disjoint"] is False
    assert "papers/hu2021_lora.pdf" in report["doc_id_overlaps"]["train__vs__test"]


@pytest.mark.unit
def test_s2_evaluation_metrics_correct_denominators():
    """Precision/recall/F1 denominators use exact TP, FP, FN counts."""
    c_res = compare_concepts(["A", "B", "Extra"], ["A", "B", "Missing"])
    assert c_res["true_positives"] == 2
    assert c_res["false_positives"] == 1
    assert c_res["false_negatives"] == 1
    assert c_res["precision"] == pytest.approx(2 / 3)
    assert c_res["recall"] == pytest.approx(2 / 3)


@pytest.mark.unit
def test_s2_directed_relation_reversals_count_as_incorrect():
    """Reversed prerequisite edge direction yields 0.0 directed F1."""
    gold = [{"source": "Linear Algebra", "target": "LoRA", "type": "requires"}]
    pred = [{"source": "LoRA", "target": "Linear Algebra", "type": "requires"}]
    res = compare_edges(pred, gold)
    assert res["directed"]["true_positives"] == 0
    assert res["directed"]["f1"] == pytest.approx(0.0)


@pytest.mark.unit
def test_s2_missing_ground_truth_not_treated_as_correct():
    """Predictions against empty gold ground truth must score 0.0 (not 1.0)."""
    assert compare_concepts(["LoRA"], [])["f1"] == pytest.approx(0.0)
    assert compare_edges([{"source": "A", "target": "B", "type": "requires"}], [])["directed"]["f1"] == pytest.approx(0.0)


@pytest.mark.unit
def test_s2_invalid_provenance_explicitly_reported():
    """Missing/opaque provenance is quarantined during split build and flagged in eval."""
    rows = _synthetic_rows() + [{"task": "academic_okf", "doc_id": "", "messages": []}]
    _splits, manifest = build_document_disjoint_splits(rows, seed=42)
    assert manifest["quarantined_missing_doc_id"] == 1

    extracted = {
        "concepts": {"c1": {"name": "LoRA", "sources": []}},
        "edges": [{"from_name": "LoRA", "to_name": "Rank", "edge_type": "REQUIRES", "source": "pearson_batch1"}],
    }
    assert compare_concepts(extracted["concepts"], ["LoRA"], doc_id="papers/Hu2021_LoRA.pdf")["unscopable_concepts"] == 1
    assert compare_edges(extracted, [{"source": "Rank", "target": "LoRA", "type": "requires"}], doc_id="papers/Hu2021_LoRA.pdf")["unscopable_edges"] == 1


@pytest.mark.unit
def test_s2_contaminated_historical_metrics_blocked_from_export():
    """Historical 97.22% artifact and token-only records cannot enter publication exports."""
    with pytest.raises(ValueError, match="INVALID_FOR_SCIENTIFIC_CLAIMS"):
        assert_clean_benchmark_record(
            {"overall_token_accuracy_pct": 97.22},
            source_path=Path("models/lib_qwen_scholarly_lora/dual_dataset_benchmark_results.json"),
        )
    with pytest.raises(ValueError, match="leakage"):
        assert_clean_benchmark_record({"train_test_leakage_detected": True})
    with pytest.raises(ValueError, match="token accuracy"):
        assert_clean_benchmark_record({"overall_token_accuracy_pct": 97.22})
