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
    audit_corpus_quality,
    build_qrels_from_records,
    evaluate_rankings,
    evaluate_retrieval_systems,
    mean_reciprocal_rank,
    ndcg_at_k,
    normalize_passage_text,
    precision_at_k,
    recall_at_k,
    rrf_fuse,
)


def _make_passages() -> list[Passage]:
    raw = [
        ("doca", "c1", 1, "Intro", "Gradient descent optimizes convex loss functions iteratively."),
        ("doca", "c2", 2, "Chain Rule", "Backpropagation computes gradients via the chain rule in neural networks."),
        ("docb", "c1", 1, "Matrices", "Eigenvalues and eigenvectors characterize linear transformations."),
        ("docc", "c1", 3, "Attention", "Scaled dot-product attention weights values by query-key similarity."),
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
    assert r1[0][0] == "docb::c1"
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
    assert r1[0][0] == "doca::c2"
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


def test_s31_end_to_end_adjudicated_gold_graded_and_unanswerable() -> None:
    passages = _make_passages()
    bm25 = BM25Retriever(passages)
    dense = DenseRetriever(passages, encoder=_synthetic_encoder, query_prefix="")

    queries = [
        {
            "query_id": "CIKM-SYN-001",
            "source_doc_ids": ["doca"],
            "question": "How does backpropagation compute gradients in neural networks?",
            "question_category": "single_hop_definition",
            "gold_supporting_passages": [
                {
                    "doc_id": "doca",
                    "chunk_id": "c2",
                    "page_number": 2,
                    "quote_span": "Backpropagation computes gradients via the chain rule",
                }
            ],
            "exact_page_refs": ["doca:p2"],
            "relevant_passage_labels": {
                "doca::c2": 2,
                "doca::c1": 1,
                "docb::c1": 0,
            },
            "expected_prerequisite_paths": [],
            "answerability_status": "ANSWERABLE",
            "annotator_id": "ann_1",
            "annotation_confidence": 0.95,
            "disagreement_notes": None,
            "review_status": "ADJUDICATED_GOLD",
        },
        {
            "query_id": "CIKM-SYN-002",
            "source_doc_ids": [],
            "question": "What is the melting point of titanium alloy in this corpus?",
            "question_category": "unanswerable_out_of_corpus",
            "gold_supporting_passages": [],
            "exact_page_refs": [],
            "relevant_passage_labels": {},
            "expected_prerequisite_paths": [],
            "answerability_status": "UNANSWERABLE_OUT_OF_CORPUS",
            "annotator_id": "ann_1",
            "annotation_confidence": 1.0,
            "disagreement_notes": None,
            "review_status": "ADJUDICATED_GOLD",
        },
        {
            "query_id": "CIKM-SYN-003",
            "source_doc_ids": ["docC"],
            "question": "How does scaled dot-product attention weight values?",
            "question_category": "single_hop_definition",
            "gold_supporting_passages": [
                {
                    "doc_id": "docC",
                    "chunk_id": "c1",
                    "page_number": 3,
                    "quote_span": "Scaled dot-product attention",
                }
            ],
            "exact_page_refs": ["docC:p3"],
            "relevant_passage_labels": {},
            "expected_prerequisite_paths": [],
            "answerability_status": "ANSWERABLE",
            "annotator_id": "ann_1",
            "annotation_confidence": 0.9,
            "disagreement_notes": None,
            "review_status": "SINGLE_ANNOTATED",  # Must NOT be evaluated as adjudicated gold
        },
    ]

    result = evaluate_retrieval_systems(
        passages,
        queries,
        bm25,
        dense,
        rrf_k=60,
        top_k=4,
        ks=(1, 2, 4),
    )

    qb = result["qrels_bundle"]
    assert qb["status"] == "ADJUDICATED_GOLD_AVAILABLE"
    assert qb["adjudicated_gold_queries"] == 2
    assert qb["evaluable_answerable_queries"] == 1
    assert qb["unanswerable_queries"] == 1
    assert qb["unanswerable_query_ids"] == ["CIKM-SYN-002"]
    assert qb["validation_errors"] == []

    # Verify all 3 systems received actual per-query rankings and evaluated CIKM-SYN-001
    for sys_name in ("bm25", "dense", "hybrid_rrf"):
        ev = result["per_system_evaluation"][sys_name]
        assert ev["status"] == "EVALUATED"
        assert ev["evaluated_queries"] == 1
        # Rank 1 is docA::c2 (grade 2) for all 3 systems on this synthetic query
        assert ev["metrics"]["mrr"] == 1.0
        assert ev["metrics"]["precision@1"] == 1.0
        assert ev["metrics"]["recall@1"] == 0.5  # 1 of 2 positives (c2, c1)
        assert ev["metrics"]["recall@4"] == 1.0


def test_s31_negative_invalid_statuses_and_malformed_passages() -> None:
    passages = _make_passages()
    passage_by_id = {p.passage_id: p for p in passages}

    bad_queries = [
        {
            "query_id": "CIKM-BAD-STATUS",
            "review_status": "VERIFIED_GOLD",  # Unsupported status
            "answerability_status": "ANSWERABLE",
            "gold_supporting_passages": [{"doc_id": "docA", "chunk_id": "c1", "page_number": 1, "quote_span": "x"}],
            "relevant_passage_labels": {},
        },
        {
            "query_id": "CIKM-BAD-PAGE",
            "review_status": "ADJUDICATED_GOLD",
            "answerability_status": "ANSWERABLE",
            "gold_supporting_passages": [{"doc_id": "docA", "chunk_id": "c1", "page_number": 99, "quote_span": "x"}],
            "relevant_passage_labels": {},
        },
        {
            "query_id": "CIKM-BAD-MISSING-PASSAGE",
            "review_status": "ADJUDICATED_GOLD",
            "answerability_status": "ANSWERABLE",
            "gold_supporting_passages": [{"doc_id": "docZ", "chunk_id": "c9", "page_number": 1, "quote_span": "x"}],
            "relevant_passage_labels": {},
        },
        {
            "query_id": "CIKM-BAD-NO-ANNOTATIONS",
            "review_status": "ADJUDICATED_GOLD",
            "answerability_status": "ANSWERABLE",
            "gold_supporting_passages": [],
            "relevant_passage_labels": {"docA::c1": 0},
        },
        {
            "query_id": "CIKM-BAD-UNANSWERABLE-WITH-GOLD",
            "review_status": "ADJUDICATED_GOLD",
            "answerability_status": "UNANSWERABLE_OUT_OF_CORPUS",
            "gold_supporting_passages": [{"doc_id": "docA", "chunk_id": "c1", "page_number": 1, "quote_span": "x"}],
            "relevant_passage_labels": {},
        },
    ]

    qb = build_qrels_from_records(bad_queries, passage_by_id)
    assert qb["status"] == "NO_HUMAN_GOLD"
    assert qb["evaluable_answerable_queries"] == 0
    assert len(qb["validation_errors"]) == 5


def test_s31_corpus_quality_audit_flags_without_silent_deletion() -> None:
    passages = [
        Passage("doc_idx::c1", "data_science_2019/index_2019_data-science.pdf", "c1", 1, "Index", "alpha 10, 12, 14, 16, 18", "h1"),
        Passage("doc_bad_page::c1", "doc_bad_page", "c1", 0, "Body", "Some body text", "h2"),
        Passage("doc_good::c1", "doc_good", "c1", 1, "Body", "First chunk", "h3"),
        Passage("doc_good::c2", "doc_good", "c2", 2, "Body", "Second chunk", "h4"),
    ]
    audit = audit_corpus_quality(
        passages,
        raw_doc_ids_by_canonical={"doc_good": {"doc_good", "Doc_Good"}},
        doc_provenance_by_canonical={
            "data_science_2019/index_2019_data-science.pdf": {"doc_hash": None, "pdf_url": None, "page_count": 10},
            "doc_bad_page": {"doc_hash": "abc", "pdf_url": "https://example.com/a.pdf", "page_count": 5},
            "doc_good": {"doc_hash": "def", "pdf_url": "https://example.com/b.pdf", "page_count": 5},
        },
    )
    assert audit["index_only_passage_count"] == 1
    assert audit["invalid_page_number_count"] == 1
    assert audit["duplicate_document_identity_count"] == 1
    assert audit["one_chunk_document_count"] == 2
    assert audit["missing_verifiable_pdf_provenance_passages"] == 1
    assert "retained_and_flagged_for_audit" in audit["inclusion_exclusion_policy"]
