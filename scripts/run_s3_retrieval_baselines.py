#!/usr/bin/env python3
"""Run S3 offline retrieval baselines (BM25, Dense, Hybrid RRF) and export
annotation-ready candidate rankings.

Does NOT fabricate gold relevance judgments or report unverified pilot metrics
as legitimate CIKM benchmark results.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import sys
import time
from typing import Any

import numpy as np
import sentence_transformers
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archipelago.eval.dataset_integrity import assert_clean_benchmark_record
from archipelago.eval.retrieval_baselines import (
    BM25Retriever,
    DEFAULT_ARCTIC_QUERY_PREFIX,
    DEFAULT_BM25_B,
    DEFAULT_BM25_K1,
    DEFAULT_DENSE_MODEL,
    DEFAULT_RRF_K,
    DenseRetriever,
    Passage,
    build_fixed_corpus_from_kuzu,
    evaluate_retrieval_systems,
)


def _latency_summary(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    arr = np.asarray(latencies_ms, dtype=np.float64)
    return {
        "mean_ms": round(float(np.mean(arr)), 3),
        "p50_ms": round(float(np.percentile(arr, 50)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "max_ms": round(float(np.max(arr)), 3),
    }


def _load_queries(jsonl_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> int:
    db_path = ROOT / "okf_graph.db"
    queries_path = ROOT / "artifacts" / "validation" / "cikm_qa_pilot_candidates.jsonl"
    manifest_out = ROOT / "artifacts" / "validation" / "s3_corpus_manifest.json"
    json_out = ROOT / "artifacts" / "validation" / "s3_retrieval_candidates_export.json"
    csv_out = ROOT / "artifacts" / "validation" / "s3_retrieval_candidates_export.csv"
    top_k = 10

    passages, manifest = build_fixed_corpus_from_kuzu(db_path)
    manifest["db_path"] = str(db_path.relative_to(ROOT))
    passage_by_id: dict[str, Passage] = {p.passage_id: p for p in passages}
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    queries = _load_queries(queries_path)

    # Baseline A: BM25
    t0 = time.perf_counter()
    bm25 = BM25Retriever(passages, k1=DEFAULT_BM25_K1, b=DEFAULT_BM25_B)
    bm25_index_s = round(time.perf_counter() - t0, 4)

    # Baseline B: Dense (CPU, local cache)
    t0 = time.perf_counter()
    dense = DenseRetriever(
        passages,
        model_name=DEFAULT_DENSE_MODEL,
        device="cpu",
        local_files_only=True,
    )
    dense_index_s = round(time.perf_counter() - t0, 4)

    eval_run = evaluate_retrieval_systems(
        passages,
        queries,
        bm25,
        dense,
        rrf_k=DEFAULT_RRF_K,
        top_k=top_k,
    )
    qrels_bundle = eval_run["qrels_bundle"]
    per_system_eval = eval_run["per_system_evaluation"]
    scored_results = eval_run["scored_results"]
    bm25_lat_ms = eval_run["latencies_ms"]["bm25"]
    dense_lat_ms = eval_run["latencies_ms"]["dense"]
    rrf_lat_ms = eval_run["latencies_ms"]["hybrid_rrf"]

    query_exports: list[dict[str, Any]] = []
    csv_rows: list[dict[str, Any]] = []

    for q in queries:
        qid = q["query_id"]
        question = q["question"]
        system_top = scored_results[qid]

        per_system_formatted: dict[str, list[dict[str, Any]]] = {}
        for sys_name, ranked in system_top.items():
            formatted_hits: list[dict[str, Any]] = []
            for rank_idx, (pid, score) in enumerate(ranked, start=1):
                p = passage_by_id[pid]
                formatted_hits.append(
                    {
                        "rank": rank_idx,
                        "passage_id": pid,
                        "doc_id": p.doc_id,
                        "page_number": p.page_number,
                        "chunk_id": p.chunk_id,
                        "score": round(float(score), 6),
                        "text_preview": p.text[:240],
                    }
                )
                csv_rows.append(
                    {
                        "query_id": qid,
                        "review_status": q.get("review_status", "UNVERIFIED_CANDIDATE"),
                        "system": sys_name,
                        "rank": rank_idx,
                        "passage_id": pid,
                        "doc_id": p.doc_id,
                        "page_number": p.page_number,
                        "chunk_id": p.chunk_id,
                        "score": round(float(score), 6),
                        "human_relevance_label": "",
                        "annotator_notes": "",
                        "question": question,
                        "passage_text": p.text,
                    }
                )
            per_system_formatted[sys_name] = formatted_hits

        query_exports.append(
            {
                "query_id": qid,
                "question": question,
                "question_category": q.get("question_category"),
                "source_doc_ids": q.get("source_doc_ids", []),
                "review_status": q.get("review_status", "UNVERIFIED_CANDIDATE"),
                "rankings": per_system_formatted,
            }
        )

    max_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    human_gold_available = qrels_bundle["evaluable_answerable_queries"] > 0

    export_payload: dict[str, Any] = {
        "benchmark_phase": "S3_RETRIEVAL_BASELINES",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "human_gold_available": human_gold_available,
        "scientific_evaluation_status": (
            "CIKM retrieval performance is NOT YET MEASURABLE."
            if not human_gold_available
            else "EVALUATED_ON_ADJUDICATED_GOLD"
        ),
        "evaluation_summary": per_system_eval,
        "qrels_summary": {
            "status": qrels_bundle["status"],
            "adjudicated_gold_queries": qrels_bundle["adjudicated_gold_queries"],
            "evaluable_answerable_queries": qrels_bundle["evaluable_answerable_queries"],
            "unanswerable_queries": qrels_bundle["unanswerable_queries"],
            "unanswerable_query_ids": qrels_bundle["unanswerable_query_ids"],
            "validation_errors": qrels_bundle["validation_errors"],
        },
        "corpus": {
            "corpus_version": manifest["corpus_version"],
            "corpus_sha256": manifest["corpus_sha256"],
            "unique_passages": manifest["unique_passages"],
            "unique_documents": manifest["unique_documents"],
            "missing_provenance_chunks": manifest["missing_provenance_chunks"],
            "duplicate_passages_removed": manifest["duplicate_passages_removed"],
            "corpus_quality_audit": manifest["corpus_quality_audit"],
        },
        "query_set": {
            "path": str(queries_path.relative_to(ROOT)),
            "total_queries": len(queries),
            "adjudicated_gold_queries": qrels_bundle["adjudicated_gold_queries"],
            "evaluable_answerable_queries": qrels_bundle["evaluable_answerable_queries"],
            "unanswerable_queries": qrels_bundle["unanswerable_queries"],
            "unverified_candidate_queries": len(queries) - qrels_bundle["adjudicated_gold_queries"],
        },
        "systems": {
            "bm25": {
                "config": {"k1": DEFAULT_BM25_K1, "b": DEFAULT_BM25_B, "tokenizer": "alnum_lower"},
                "index_build_seconds": bm25_index_s,
                "query_latency": _latency_summary(bm25_lat_ms),
            },
            "dense": {
                "config": {
                    "model_name": DEFAULT_DENSE_MODEL,
                    "device": "cpu",
                    "local_files_only": True,
                    "query_prefix": DEFAULT_ARCTIC_QUERY_PREFIX,
                    "similarity": "cosine_normalized_dot",
                },
                "index_build_seconds": dense_index_s,
                "query_latency": _latency_summary(dense_lat_ms),
            },
            "hybrid_rrf": {
                "config": {
                    "k": DEFAULT_RRF_K,
                    "inputs": ["bm25", "dense"],
                    "fusion_pool": "full_corpus",
                },
                "index_build_seconds": 0.0,
                "query_latency": _latency_summary(rrf_lat_ms),
            },
        },
        "environment": {
            "python_version": sys.version.split()[0],
            "sentence_transformers_version": sentence_transformers.__version__,
            "torch_version": torch.__version__,
            "numpy_version": np.__version__,
            "max_rss_kb": int(max_rss_kb),
        },
        "candidates": query_exports,
    }

    assert_clean_benchmark_record(export_payload, source_path=json_out)
    json_out.write_text(json.dumps(export_payload, indent=2) + "\n", encoding="utf-8")

    with csv_out.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "query_id",
            "review_status",
            "system",
            "rank",
            "passage_id",
            "doc_id",
            "page_number",
            "chunk_id",
            "score",
            "human_relevance_label",
            "annotator_notes",
            "question",
            "passage_text",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(
        json.dumps(
            {
                "manifest_out": str(manifest_out.relative_to(ROOT)),
                "json_out": str(json_out.relative_to(ROOT)),
                "csv_out": str(csv_out.relative_to(ROOT)),
                "unique_passages": manifest["unique_passages"],
                "unique_documents": manifest["unique_documents"],
                "queries": len(queries),
                "scientific_evaluation_status": export_payload["scientific_evaluation_status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
