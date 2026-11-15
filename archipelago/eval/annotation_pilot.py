"""S4-A Human-Gold Annotation Pilot & Source Verification utilities.

Provides:
- Source & quote_span verification against local PDFs and corpus passages
- Blinded, deduplicated candidate pool construction (hiding system names & ranks,
  adding independently sampled corpus passages)
- Dual-reviewer blank annotation templates (never pre-filled)
- Disagreement-preserving adjudication workflow
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import random
from typing import Any, Sequence

from archipelago.eval.dataset_integrity import normalize_doc_id
from archipelago.eval.retrieval_baselines import (
    Passage,
    normalize_passage_text,
)

PILOT_SELECTED_QUERY_IDS = (
    "CIKM-PILOT-001",  # multi_hop_prerequisite
    "CIKM-PILOT-005",  # multi_hop_prerequisite
    "CIKM-PILOT-013",  # multi_hop_prerequisite
    "CIKM-PILOT-002",  # single_hop_definition
    "CIKM-PILOT-004",  # cross_paper_comparison
    "CIKM-PILOT-023",  # unanswerable_out_of_corpus
)

FORBIDDEN_SYSTEM_KEYS = frozenset({"system", "systems", "rank", "ranks", "score", "scores", "bm25", "dense", "hybrid_rrf"})


def verify_quote_in_passage(quote_span: str, passage_text: str) -> bool:
    """Verify whether normalized quote_span occurs in normalized passage_text."""
    norm_quote = normalize_passage_text(quote_span).lower()
    norm_passage = normalize_passage_text(passage_text).lower()
    if not norm_quote:
        return False
    return norm_quote in norm_passage


def verify_sources_and_quotes(
    queries: Sequence[dict[str, Any]],
    passage_by_id: dict[str, Passage],
    *,
    pdf_root: Path,
    doc_provenance_by_canonical: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Inspect source PDF accessibility, Kuzu provenance, and quote_span matches."""
    reports: list[dict[str, Any]] = []
    for q in queries:
        qid = q["query_id"]
        source_checks: list[dict[str, Any]] = []
        discrepancies: list[str] = []

        for raw_doc in q.get("source_doc_ids", []):
            canon_doc = normalize_doc_id(raw_doc)
            pdf_path = pdf_root / raw_doc
            pdf_exists = pdf_path.is_file()
            pdf_sha256 = (
                hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                if pdf_exists
                else None
            )
            kuzu_meta = (doc_provenance_by_canonical or {}).get(canon_doc, {})
            has_kuzu_hash = bool(kuzu_meta.get("doc_hash"))
            has_kuzu_url = bool(kuzu_meta.get("pdf_url"))
            if not pdf_exists:
                discrepancies.append(f"missing_local_pdf:{raw_doc}")
            if not has_kuzu_hash or not has_kuzu_url:
                discrepancies.append(f"missing_kuzu_pdf_provenance:{canon_doc}")

            source_checks.append(
                {
                    "raw_doc_id": raw_doc,
                    "canonical_doc_id": canon_doc,
                    "local_pdf_exists": pdf_exists,
                    "local_pdf_sha256": pdf_sha256,
                    "kuzu_doc_hash_present": has_kuzu_hash,
                    "kuzu_pdf_url_present": has_kuzu_url,
                }
            )

        quote_checks: list[dict[str, Any]] = []
        for ref in q.get("gold_supporting_passages", []):
            doc_id = normalize_doc_id(str(ref.get("doc_id", "")))
            chunk_id = str(ref.get("chunk_id", "")).strip()
            page_num = ref.get("page_number")
            quote_span = str(ref.get("quote_span", ""))
            pid = f"{doc_id}::{chunk_id}"
            passage = passage_by_id.get(pid)

            if passage is None:
                discrepancies.append(f"missing_passage:{pid}")
                quote_checks.append(
                    {
                        "passage_id": pid,
                        "passage_exists": False,
                        "page_matches": False,
                        "quote_matches": False,
                    }
                )
                continue

            page_matches = isinstance(page_num, int) and not isinstance(page_num, bool) and passage.page_number == page_num
            if not page_matches:
                discrepancies.append(
                    f"page_mismatch:{pid}:expected_{passage.page_number}_got_{page_num}"
                )
            quote_matches = verify_quote_in_passage(quote_span, passage.text)
            if not quote_matches:
                discrepancies.append(f"quote_not_found_in_passage:{pid}")

            quote_checks.append(
                {
                    "passage_id": pid,
                    "passage_exists": True,
                    "page_matches": page_matches,
                    "quote_matches": quote_matches,
                }
            )

        if not q.get("gold_supporting_passages") and q.get("answerability_status") != "UNANSWERABLE_OUT_OF_CORPUS":
            discrepancies.append("no_gold_supporting_passages_yet_requires_human_annotation")

        reports.append(
            {
                "query_id": qid,
                "question_category": q.get("question_category"),
                "review_status": q.get("review_status"),
                "answerability_status": q.get("answerability_status"),
                "sources": source_checks,
                "quote_checks": quote_checks,
                "discrepancies": discrepancies,
                "requires_manual_verification": bool(discrepancies),
            }
        )
    return reports


def build_blinded_annotation_pool(
    passages: Sequence[Passage],
    queries: Sequence[dict[str, Any]],
    candidate_passage_ids_by_query: dict[str, Sequence[str]],
    *,
    random_sample_per_query: int = 3,
    seed: int = 42,
) -> dict[str, list[dict[str, Any]]]:
    """Build deduplicated, blinded candidate pools with independently sampled controls.

    Strips all retrieval-system names, ranks, and scores so annotators cannot
    infer which system retrieved a passage.
    """
    passage_by_id = {p.passage_id: p for p in passages}
    all_pids = sorted(passage_by_id.keys())
    pools: dict[str, list[dict[str, Any]]] = {}

    for q in queries:
        qid = q["query_id"]
        seen: set[str] = set()
        pool_pids: list[str] = []

        for pid in candidate_passage_ids_by_query.get(qid, []):
            if pid in passage_by_id and pid not in seen:
                seen.add(pid)
                pool_pids.append(pid)

        rng = random.Random(f"{seed}:{qid}")
        remaining = [pid for pid in all_pids if pid not in seen]
        k_sample = min(random_sample_per_query, len(remaining))
        if k_sample > 0:
            sampled = rng.sample(remaining, k_sample)
            for pid in sampled:
                seen.add(pid)
                pool_pids.append(pid)

        rng.shuffle(pool_pids)

        items: list[dict[str, Any]] = []
        for idx, pid in enumerate(pool_pids, start=1):
            p = passage_by_id[pid]
            items.append(
                {
                    "pool_item_id": f"CAND-{idx:02d}",
                    "passage_id": p.passage_id,
                    "doc_id": p.doc_id,
                    "chunk_id": p.chunk_id,
                    "page_number": p.page_number,
                    "section_title": p.section_title,
                    "text": p.text,
                }
            )
        pools[qid] = items
    return pools


def create_reviewer_records(
    queries: Sequence[dict[str, Any]],
    blinded_pools: dict[str, list[dict[str, Any]]],
    *,
    reviewer_id: str,
) -> list[dict[str, Any]]:
    """Create blank human-annotation records for one independent reviewer.

    Never auto-fills human judgments and never marks records ADJUDICATED_GOLD.
    """
    records: list[dict[str, Any]] = []
    for q in queries:
        qid = q["query_id"]
        pool = blinded_pools.get(qid, [])
        records.append(
            {
                "query_id": qid,
                "reviewer_id": reviewer_id,
                "question": q["question"],
                "question_category": q.get("question_category"),
                "source_doc_ids": q.get("source_doc_ids", []),
                "review_status": "UNVERIFIED_CANDIDATE",
                "answerability_assessment": None,
                "passage_relevance_judgments": {
                    item["pool_item_id"]: None for item in pool
                },
                "pool_item_to_passage_id": {
                    item["pool_item_id"]: item["passage_id"] for item in pool
                },
                "quote_and_page_verified": None,
                "prerequisite_dependency_verified": None,
                "requires_multiple_supporting_passages": None,
                "supporting_quote_spans": [],
                "reviewer_notes": "",
            }
        )
    return records


def adjudicate_reviewer_pair(
    rec_a: dict[str, Any],
    rec_b: dict[str, Any],
    *,
    adjudicator_id: str | None = None,
    resolved_answerability: str | None = None,
    resolved_relevance: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Compare two independent reviewer records, preserving disagreements."""
    qid = rec_a["query_id"]
    if rec_b["query_id"] != qid:
        raise ValueError(f"Query ID mismatch: {qid} vs {rec_b['query_id']}")

    incomplete: list[str] = []
    for label, rec in (("reviewer_a", rec_a), ("reviewer_b", rec_b)):
        if rec.get("answerability_assessment") is None:
            incomplete.append(f"{label}:missing_answerability_assessment")
        if rec.get("quote_and_page_verified") is None:
            incomplete.append(f"{label}:missing_quote_and_page_verified")
        if rec.get("prerequisite_dependency_verified") is None:
            incomplete.append(f"{label}:missing_prerequisite_dependency_verified")
        if rec.get("requires_multiple_supporting_passages") is None:
            incomplete.append(f"{label}:missing_requires_multiple_supporting_passages")
        judgments = rec.get("passage_relevance_judgments") or {}
        if not judgments or any(v is None for v in judgments.values()):
            incomplete.append(f"{label}:incomplete_passage_relevance_judgments")
        elif any(isinstance(v, bool) or v not in (0, 1, 2) for v in judgments.values()):
            incomplete.append(f"{label}:invalid_relevance_grade")

    if incomplete:
        return {
            "query_id": qid,
            "review_status": "UNVERIFIED_CANDIDATE",
            "disagreements": [],
            "incomplete_fields": incomplete,
        }

    disagreements: list[dict[str, Any]] = []
    for field in (
        "answerability_assessment",
        "quote_and_page_verified",
        "prerequisite_dependency_verified",
        "requires_multiple_supporting_passages",
    ):
        if rec_a.get(field) != rec_b.get(field):
            disagreements.append(
                {
                    "field": field,
                    "reviewer_a": rec_a.get(field),
                    "reviewer_b": rec_b.get(field),
                }
            )

    rel_a = rec_a["passage_relevance_judgments"]
    rel_b = rec_b["passage_relevance_judgments"]
    all_items = sorted(set(rel_a.keys()) | set(rel_b.keys()))
    for item_id in all_items:
        if rel_a.get(item_id) != rel_b.get(item_id):
            disagreements.append(
                {
                    "field": f"passage_relevance:{item_id}",
                    "reviewer_a": rel_a.get(item_id),
                    "reviewer_b": rel_b.get(item_id),
                }
            )

    if not disagreements:
        return {
            "query_id": qid,
            "review_status": "ADJUDICATED_GOLD",
            "answerability_status": rec_a["answerability_assessment"],
            "relevant_passage_labels": {
                rec_a["pool_item_to_passage_id"][k]: int(v)
                for k, v in rel_a.items()
            },
            "disagreements": [],
            "incomplete_fields": [],
            "adjudicator_id": adjudicator_id or "consensus",
        }

    if adjudicator_id and resolved_answerability is not None and resolved_relevance is not None:
        return {
            "query_id": qid,
            "review_status": "ADJUDICATED_GOLD",
            "answerability_status": resolved_answerability,
            "relevant_passage_labels": {
                rec_a["pool_item_to_passage_id"][k]: int(v)
                for k, v in resolved_relevance.items()
            },
            "disagreements": disagreements,
            "incomplete_fields": [],
            "adjudicator_id": adjudicator_id,
        }

    return {
        "query_id": qid,
        "review_status": "DOUBLE_ANNOTATED_DISAGREEMENT",
        "disagreements": disagreements,
        "incomplete_fields": [],
        "adjudicator_id": None,
    }
