"""Offline unit and reproducibility tests for Archipelago S3 retrieval baselines."""

from __future__ import annotations

import math

import numpy as np
import pytest

from archipelago.eval.dataset_integrity import assert_clean_benchmark_record, content_hash
from archipelago.eval.retrieval_baselines import (
    BM25Retriever,
    DenseRetriever,
    Passage,
    evaluate_rankings,
    mean_reciprocal_rank,
    ndcg_at_k,
    normalize_passage_text,
    precision_at_k,
    recall_at_k,
    rrf_fuse,
)


def _make_passages() -> list[Passage]:
    raw = [
        ("docA", "c1", 1, "Intro", "Gradient descent optimizes convex loss functions iteratively."),
        ("docA", "c2", 2, "Chain Rule", "Backpropagation computes gradients via the chain rule in neural networks."),
        ("docB", "c1", 1, "Matrices", "Eigenvalues and eigenvectors characterize linear transformations."),
        ("docC", "c1", 3, "Attention", "Scaled dot-product attention weights values by query-key similarity."),
    ]
    passages: list[Passage] = []
    for doc_id, chunk_id, page, section, text in raw:
        norm = normalize_passage_text(text)
        passages.append(
            Passage(
                passage_id=f"{doc_id}::{chunk_id}",
                doc_id=doc_id,
                chunk_id=chunk_id,
                page_number=page,
                section_title=section,
                text=norm,
                content_sha256=content_hash(norm),
            )
        )
    return passages


def _synthetic_encoder(texts: list[str]) -> np.ndarray:
    """Deterministic 4-dim bag-of-concept encoder for offline tests."""
    vocab = ["gradient", "backpropagation", "eigenvalues", "attention"]
    vecs = []
    for t in texts:
        low = t.lower()
        vec = [1.0 if kw in low else 0.05 for kw in vocab]
        vecs.append(vec)
    return np.asarray(vecs, dtype=np.float32)


def test_passage_identity_and_corpus_consistency() -> None:
    passages = _make_passages()
    pids = [p.passage_id for p in passages]
    assert len(pids) == len(set(pids))

    bm25 = BM25Retriever(passages)
    dense = DenseRetriever(passages, encoder=_synthetic_encoder, query_prefix="")
    assert bm25.passage_ids == dense.passage_ids == pids


def test_bm25_ranking_and_determinism() -> None:
    passages = _make_passages()
    bm25 = BM25Retriever(passages, k1=1.5, b=0.75)

    r1 = bm25.search("eigenvalues linear transformations", top_k=4)
    r2 = bm25.search("eigenvalues linear transformations", top_k=4)
    assert r1 == r2
    assert r1[0][0] == "docB::c1"
    assert r1[0][1] > r1[1][1]


def test_bm25_deterministic_tie_breaking() -> None:
    p1 = Passage("docB::c1", "docB", "c1", 1, "", "alpha beta", content_hash("alpha beta"))
    p2 = Passage("docA::c1", "docA", "c1", 1, "", "alpha beta", content_hash("alpha beta"))
    bm25 = BM25Retriever([p1, p2])
    ranked = bm25.search("alpha", top_k=2)
    assert [pid for pid, _ in ranked] == ["docA::c1", "docB::c1"]
    assert math.isclose(ranked[0][1], ranked[1][1], rel_tol=1e-9)


def test_dense_retrieval_correctness_and_determinism() -> None:
    passages = _make_passages()
    dense = DenseRetriever(passages, encoder=_synthetic_encoder, query_prefix="")

    r1 = dense.search("backpropagation neural networks", top_k=4)
    r2 = dense.search("backpropagation neural networks", top_k=4)
    assert r1 == r2
    assert r1[0][0] == "docA::c2"
    assert len({pid for pid, _ in r1}) == 4


def test_rrf_fusion_math_duplicates_missing_and_ties() -> None:
    # Ranker 1 has duplicate "p1" (should only count first occurrence at rank 1)
    r1 = [("p1", 10.0), ("p1", 9.0), ("p2", 8.0), ("p3", 7.0)]
    # Ranker 2 omits "p3" and puts "p2" first, "p1" second
    r2 = [("p2", 0.9), ("p1", 0.8), ("p4", 0.7)]

    fused = rrf_fuse([r1, r2], k=60, top_k=4)
    scores = dict(fused)

    # p1: 1/(60+1) + 1/(60+2)
    expected_p1 = 1.0 / 61.0 + 1.0 / 62.0
    # p2: 1/(60+2) + 1/(60+1) -> exact tie with p1!
    expected_p2 = 1.0 / 62.0 + 1.0 / 61.0
    expected_p3 = 1.0 / 63.0
    expected_p4 = 1.0 / 63.0

    assert math.isclose(scores["p1"], expected_p1, rel_tol=1e-12)
    assert math.isclose(scores["p2"], expected_p2, rel_tol=1e-12)
    assert math.isclose(scores["p3"], expected_p3, rel_tol=1e-12)
    assert math.isclose(scores["p4"], expected_p4, rel_tol=1e-12)

    # Deterministic tie-breaking by passage_id: p1 before p2, p3 before p4
    assert [pid for pid, _ in fused] == ["p1", "p2", "p3", "p4"]


def test_ir_metrics_on_synthetic_fixtures() -> None:
    ranked = ["p2", "p1", "p3", "p4"]
    rel_binary = {"p1", "p4"}

    assert math.isclose(recall_at_k(ranked, rel_binary, 2) or 0.0, 0.5)
    assert math.isclose(precision_at_k(ranked, rel_binary, 2) or 0.0, 0.5)
    assert math.isclose(mean_reciprocal_rank([ranked], [rel_binary]) or 0.0, 0.5)

    # Binary nDCG@4: hits at rank 2 and 4 -> DCG = 1/log2(3) + 1/log2(5)
    # Ideal: hits at rank 1 and 2 -> IDCG = 1/log2(2) + 1/log2(3)
    dcg = 1.0 / math.log2(3) + 1.0 / math.log2(5)
    idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)
    assert math.isclose(ndcg_at_k(ranked, rel_binary, 4) or 0.0, dcg / idcg, rel_tol=1e-9)

    # Graded relevance
    rel_graded = {"p1": 2.0, "p4": 1.0}
    res = evaluate_rankings({"q1": ranked}, {"q1": rel_graded}, ks=(2, 4))
    assert res["status"] == "EVALUATED"
    assert res["evaluated_queries"] == 1
    assert res["metrics"]["mrr"] == 0.5


def test_missing_relevance_judgments_and_contaminated_guard() -> None:
    assert recall_at_k(["p1"], set(), 1) is None
    assert precision_at_k(["p1"], set(), 1) is None
    assert mean_reciprocal_rank([["p1"]], [set()]) is None
    assert ndcg_at_k(["p1"], set(), 1) is None

    res = evaluate_rankings({"q1": ["p1", "p2"]}, {})
    assert res == {"status": "NO_HUMAN_GOLD", "evaluated_queries": 0, "metrics": None}

    with pytest.raises(ValueError, match="Contaminated"):
        assert_clean_benchmark_record(
            {"overall_token_accuracy_pct": 97.22},
            source_path="models/lib_qwen_scholarly_lora/dual_dataset_benchmark_results.json",
        )
