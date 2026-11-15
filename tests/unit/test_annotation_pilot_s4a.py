"""Unit and quality tests for Archipelago S4-A Human-Gold Annotation Pilot."""

from __future__ import annotations

import json
from pathlib import Path

from archipelago.eval.annotation_pilot import (
    FORBIDDEN_SYSTEM_KEYS,
    adjudicate_reviewer_pair,
    build_blinded_annotation_pool,
    create_reviewer_records,
    verify_quote_in_passage,
    verify_sources_and_quotes,
)
from archipelago.eval.dataset_integrity import content_hash
from archipelago.eval.retrieval_baselines import (
    Passage,
    build_qrels_from_records,
    normalize_passage_text,
)

ROOT = Path(__file__).resolve().parents[2]


def _sample_passages() -> list[Passage]:
    raw = [
        ("doca", "c1", 1, "Intro", "Gradient descent optimizes convex loss functions."),
        ("doca", "c2", 2, "Backprop", "Backpropagation computes gradients via the chain rule."),
        ("docb", "c1", 3, "Attention", "Scaled dot-product attention scales by sqrt(d_k)."),
        ("docc", "c1", 4, "LoRA", "Low-rank adaptation freezes pretrained weights."),
        ("docd", "c1", 5, "vLLM", "PagedAttention partitions KV cache into non-contiguous blocks."),
    ]
    out: list[Passage] = []
    for d, c, p, s, t in raw:
        norm = normalize_passage_text(t)
        out.append(Passage(f"{d}::{c}", d, c, p, s, norm, content_hash(norm)))
    return out


def test_quote_span_and_invalid_page_verification(tmp_path: Path) -> None:
    passages = _sample_passages()
    by_id = {p.passage_id: p for p in passages}
    assert verify_quote_in_passage("via the chain rule", by_id["doca::c2"].text)
    assert not verify_quote_in_passage("nonexistent quote", by_id["doca::c2"].text)

    pdf_file = tmp_path / "doca"
    pdf_file.write_bytes(b"%PDF-1.4\n")

    queries = [
        {
            "query_id": "CIKM-Q1",
            "question_category": "single_hop_definition",
            "review_status": "UNVERIFIED_CANDIDATE",
            "answerability_status": "ANSWERABLE",
            "source_doc_ids": ["doca"],
            "gold_supporting_passages": [
                {
                    "doc_id": "doca",
                    "chunk_id": "c2",
                    "page_number": 99,  # invalid page reference
                    "quote_span": "missing span",  # mismatched quote
                }
            ],
        }
    ]
    reports = verify_sources_and_quotes(
        queries,
        by_id,
        pdf_root=tmp_path,
        doc_provenance_by_canonical={"doca": {"doc_hash": "h", "pdf_url": "https://x/a.pdf"}},
    )
    assert reports[0]["requires_manual_verification"] is True
    assert any("page_mismatch" in d for d in reports[0]["discrepancies"])
    assert any("quote_not_found_in_passage" in d for d in reports[0]["discrepancies"])


def test_blinded_pool_hides_system_labels_and_templates_not_fabricated() -> None:
    passages = _sample_passages()
    queries = [
        {
            "query_id": "CIKM-PILOT-001",
            "question": "How does backpropagation compute gradients?",
            "question_category": "multi_hop_prerequisite",
            "source_doc_ids": ["doca"],
        }
    ]
    pools = build_blinded_annotation_pool(
        passages,
        queries,
        {"CIKM-PILOT-001": ["doca::c2", "doca::c2", "docb::c1"]},
        random_sample_per_query=2,
        seed=42,
    )
    pool = pools["CIKM-PILOT-001"]
    # 2 unique retrieved + 2 randomly sampled = 4 deduplicated items
    assert len(pool) == 4
    assert len({item["passage_id"] for item in pool}) == 4
    for item in pool:
        assert not (set(item.keys()) & FORBIDDEN_SYSTEM_KEYS)

    recs = create_reviewer_records(queries, pools, reviewer_id="reviewer_a")
    assert len(recs) == 1
    r = recs[0]
    assert r["review_status"] == "UNVERIFIED_CANDIDATE"
    assert r["answerability_assessment"] is None
    assert r["quote_and_page_verified"] is None
    assert all(v is None for v in r["passage_relevance_judgments"].values())


def test_incomplete_judgments_disagreements_and_adjudication_consistency() -> None:
    passages = _sample_passages()
    queries = [{"query_id": "CIKM-PILOT-002", "question": "What is attention?", "source_doc_ids": ["docb"]}]
    pools = build_blinded_annotation_pool(passages, queries, {"CIKM-PILOT-002": ["docb::c1"]}, random_sample_per_query=1)
    rec_a = create_reviewer_records(queries, pools, reviewer_id="reviewer_a")[0]
    rec_b = create_reviewer_records(queries, pools, reviewer_id="reviewer_b")[0]

    # Unfilled records -> incomplete_fields reported, never ADJUDICATED_GOLD
    inc = adjudicate_reviewer_pair(rec_a, rec_b)
    assert inc["review_status"] == "UNVERIFIED_CANDIDATE"
    assert inc["incomplete_fields"]

    # Fill both reviewers with a disagreement on passage relevance
    for rec in (rec_a, rec_b):
        rec["answerability_assessment"] = "ANSWERABLE"
        rec["quote_and_page_verified"] = True
        rec["prerequisite_dependency_verified"] = True
        rec["requires_multiple_supporting_passages"] = False
    keys = sorted(rec_a["passage_relevance_judgments"].keys())
    rec_a["passage_relevance_judgments"][keys[0]] = 2
    rec_a["passage_relevance_judgments"][keys[1]] = 0
    rec_b["passage_relevance_judgments"][keys[0]] = 1  # disagreement
    rec_b["passage_relevance_judgments"][keys[1]] = 0

    dis = adjudicate_reviewer_pair(rec_a, rec_b)
    assert dis["review_status"] == "DOUBLE_ANNOTATED_DISAGREEMENT"
    assert len(dis["disagreements"]) == 1

    # Explicit adjudicator resolution -> ADJUDICATED_GOLD
    adj = adjudicate_reviewer_pair(
        rec_a,
        rec_b,
        adjudicator_id="lead_adjudicator",
        resolved_answerability="ANSWERABLE",
        resolved_relevance={keys[0]: 2, keys[1]: 0},
    )
    assert adj["review_status"] == "ADJUDICATED_GOLD"
    assert adj["adjudicator_id"] == "lead_adjudicator"


def test_unanswerable_pilot_query_evaluated_separately() -> None:
    passages = _sample_passages()
    by_id = {p.passage_id: p for p in passages}
    records = [
        {
            "query_id": "CIKM-PILOT-023",
            "question_category": "unanswerable_out_of_corpus",
            "answerability_status": "UNANSWERABLE_OUT_OF_CORPUS",
            "review_status": "ADJUDICATED_GOLD",
            "gold_supporting_passages": [],
            "relevant_passage_labels": {},
        }
    ]
    qb = build_qrels_from_records(records, by_id)
    assert qb["unanswerable_queries"] == 1
    assert qb["unanswerable_query_ids"] == ["CIKM-PILOT-023"]
    assert qb["evaluable_answerable_queries"] == 0
    assert qb["status"] == "NO_HUMAN_GOLD"


def test_generated_s4a_templates_have_zero_fabricated_gold() -> None:
    report = json.loads((ROOT / "artifacts" / "validation" / "s4a_source_verification_report.json").read_text())
    assert report["selected_queries"] == 6
    assert report["human_annotations_filled"] == 0
    assert report["adjudicated_gold_count"] == 0
    for fname in ("s4a_reviewer_a_template.json", "s4a_reviewer_b_template.json"):
        recs = json.loads((ROOT / "artifacts" / "validation" / fname).read_text())
        assert len(recs) == 6
        for rec in recs:
            assert rec["review_status"] == "UNVERIFIED_CANDIDATE"
            assert rec["answerability_assessment"] is None
            assert all(v is None for v in rec["passage_relevance_judgments"].values())
