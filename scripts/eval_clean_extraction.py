#!/usr/bin/env python3
"""Offline S2 extraction & benchmark evaluation report (no model retraining, no GPU)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import kuzu

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from archipelago.eval.dataset_integrity import assert_clean_benchmark_record  # noqa: E402
from okf.evaluate import evaluate_pipeline  # noqa: E402
from okf.graph_db import export_graph  # noqa: E402


def compute_clean_extraction_report(repo_root: Path = ROOT) -> dict[str, Any]:
    """Assemble genuinely measurable extraction metrics and mark unmeasurable ones."""
    db_path = repo_root / "okf_graph.db"
    conn = kuzu.Connection(kuzu.Database(str(db_path), read_only=True))
    db_export = export_graph(conn)

    total_concepts = len(db_export["concepts"])
    scoped_concepts = sum(1 for c in db_export["concepts"].values() if c.get("sources"))
    total_edges = len(db_export["edges"])
    valid_prov_edges = sum(
        1
        for e in db_export["edges"]
        if isinstance(e.get("source"), str) and ":" in e["source"]
    )

    lora_eval = evaluate_pipeline(
        conn,
        str(repo_root / "pilot_corpus/gold/gold_lora.json"),
        doc_id="papers/Hu2021_LoRA.pdf",
    )
    attn_eval = evaluate_pipeline(
        conn,
        str(repo_root / "pilot_corpus/gold/gold_attention.json"),
        doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    )

    # Check historical 97.22% artifact is blocked from publication export
    hist_path = repo_root / "models/lib_qwen_scholarly_lora/dual_dataset_benchmark_results.json"
    hist_blocked = False
    if hist_path.exists():
        try:
            assert_clean_benchmark_record(
                json.loads(hist_path.read_text(encoding="utf-8")),
                source_path=hist_path,
            )
        except ValueError:
            hist_blocked = True

    return {
        "schema_version": "s2_clean_eval_v1",
        "historical_9722_blocked_from_export": hist_blocked,
        "document_scoped_gold_graph_metrics": {
            "gold_lora_Hu2021": {
                "concept_precision": lora_eval["concept_comparison"]["precision"],
                "concept_recall": lora_eval["concept_comparison"]["recall"],
                "concept_f1": lora_eval["concept_comparison"]["f1"],
                "directed_edge_f1": lora_eval["edge_comparison"]["directed"]["f1"],
                "unscopable_concepts": lora_eval["concept_comparison"]["unscopable_concepts"],
                "unscopable_edges": lora_eval["edge_comparison"]["unscopable_edges"],
            },
            "gold_attention_Vaswani2017": {
                "concept_precision": attn_eval["concept_comparison"]["precision"],
                "concept_recall": attn_eval["concept_comparison"]["recall"],
                "concept_f1": attn_eval["concept_comparison"]["f1"],
                "directed_edge_f1": attn_eval["edge_comparison"]["directed"]["f1"],
                "unscopable_concepts": attn_eval["concept_comparison"]["unscopable_concepts"],
                "unscopable_edges": attn_eval["edge_comparison"]["unscopable_edges"],
            },
        },
        "provenance_coverage": {
            "concepts_with_doc_provenance": scoped_concepts,
            "total_concepts": total_concepts,
            "concept_provenance_coverage_pct": round(scoped_concepts / total_concepts * 100, 2)
            if total_concepts
            else 0.0,
            "edges_with_valid_doc_chunk_provenance": valid_prov_edges,
            "total_edges": total_edges,
            "edge_provenance_coverage_pct": round(valid_prov_edges / total_edges * 100, 2)
            if total_edges
            else 0.0,
        },
        "unmeasurable_without_independent_labels_or_clean_slm_run": {
            "slm_concept_f1_on_clean_splits_v1": "NOT MEASURABLE (no clean re-run executed in S2; v4 eval aborted at 123/138)",
            "empty_negative_passage_accuracy_on_clean_splits": "NOT MEASURABLE (no clean negative-only held-out test set in clean_splits_v1)",
            "quote_span_correctness_on_fulltext_pdfs": "NOT MEASURABLE (prior LoRA 26-page full-text check yielded 0 accepted fields)",
            "schema_validity_on_clean_splits_v1": "NOT MEASURABLE (model inference prohibited during S2)",
            "teacher_forced_token_accuracy": "EXCLUDED (not a valid extraction metric; historical 97.22% invalidated by 95% leakage)",
        },
    }


def main() -> int:
    report = compute_clean_extraction_report(ROOT)
    out_path = ROOT / "artifacts/validation/s2_clean_eval_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
