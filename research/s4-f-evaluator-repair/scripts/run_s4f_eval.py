#!/usr/bin/env python3
"""S4-F reproducible evaluation script.

Runs the original (baseline) and corrected evaluation side by side for the
LoRA and Attention gold fixtures.  Writes machine-readable before/after JSON
to ``research/s4-f-evaluator-repair/s4f_eval_results.json``.

Usage:
    cd Archipelago && python3 research/s4-f-evaluator-repair/scripts/run_s4f_eval.py

Scientific constraints honoured:
- Gold fixtures are read-only.
- Graph DB is opened read-only.
- No concept, edge, or cycle is inserted, deleted, or relabelled.
- Fuzzy-match threshold is unchanged (90, as defined in okf/eval/_base.py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import kuzu

from okf.eval.gold.compare_aligned import evaluate_pipeline_corrected

GOLD_FIXTURES = [
    ("LoRA", "pilot_corpus/gold/gold_lora.json", "papers/Hu2021_LoRA.pdf"),
    (
        "Attention",
        "pilot_corpus/gold/gold_attention.json",
        "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    ),
]

OUT_PATH = ROOT / "research" / "s4-f-evaluator-repair" / "s4f_eval_results.json"


def _fmt(val: float | None, decimals: int = 4) -> str:
    if val is None:
        return "undefined"
    return f"{val:.{decimals}f}"


def main() -> None:
    db = kuzu.Database(str(ROOT / "okf_graph.db"), read_only=True)
    conn = kuzu.Connection(db)

    all_results: dict[str, dict] = {}

    for label, gold_rel, doc_id in GOLD_FIXTURES:
        gold_path = str(ROOT / gold_rel)
        print(f"\n{'=' * 60}")
        print(f"  {label}  (doc_id={doc_id})")
        print("=" * 60)

        result = evaluate_pipeline_corrected(conn, gold_path, doc_id=doc_id)
        b = result["baseline"]
        c = result["corrected"]
        cp = result["concept_provenance"]
        rs = result["relation_semantics_audit"]

        print(f"\n  Concept evaluation (identical in baseline and corrected):")
        print(
            f"    F1={_fmt(c['concept_f1'])}  "
            f"P={_fmt(c['concept_precision'])}  "
            f"R={_fmt(c['concept_recall'])}  "
            f"TP={c['concept_tp']}  FP={c['concept_fp']}  FN={c['concept_fn']}"
        )

        print(f"\n  === BASELINE edge metrics ===")
        print(
            f"    Directed  F1={_fmt(b['directed_edge_f1'])}  "
            f"TP={b['directed_edge_tp']}"
        )
        print(
            f"    Undirected F1={_fmt(b['undirected_edge_f1'])}  "
            f"TP={b['undirected_edge_tp']}"
        )
        print(
            f"    Direction accuracy = {b['direction_accuracy']}  "
            f"[{b['direction_accuracy_note']}]"
        )
        print(
            f"    Unscopable={b['unscopable_edges']}  "
            f"Skipped RELATED={b['skipped_related']}"
        )

        print(f"\n  === CORRECTED edge metrics ===")
        print(f"    Concept equiv map: {c['equiv_map_applied']}")
        print(f"    Ambiguous mappings excluded: {c['ambiguous_mappings']}")
        print(
            f"    Directed  F1={_fmt(c['directed_edge_f1'])}  "
            f"TP={c['directed_edge_tp']}  "
            f"FP={c['directed_edge_fp']}  FN={c['directed_edge_fn']}"
        )
        print(
            f"    Undirected F1={_fmt(c['undirected_edge_f1'])}  "
            f"TP={c['undirected_edge_tp']}"
        )
        da = c["direction_accuracy"]
        da_str = _fmt(da) if da is not None else "undefined"
        print(
            f"    Direction accuracy = {da_str}  "
            f"status={c['direction_accuracy_status']}  "
            f"denominator={c['direction_accuracy_denominator']}"
        )
        print(f"    Scoping: {c['scoping']}")
        print(f"    Matched directed pairs: {c['matched_directed_pairs']}")

        print(f"\n  === Concept provenance ===")
        print(
            f"    Globally absent gold concepts ({cp['globally_absent_count']}): "
            f"{cp['globally_absent_gold_concepts']}"
        )

        print(f"\n  === Relation semantics audit ===")
        print(
            f"    Unique cycles (prerequisite-only): "
            f"{rs['unique_cycle_count']} "
            f"(raw DFS: {rs['raw_cycle_count']})"
        )
        print(f"    By length: {rs['cycles_by_length']}")

        print(f"\n  === Failed match diagnosis (sample) ===")
        for fm in c["failed_matches_sample"]:
            print(f"    {fm['predicted_edge']}  → {fm['failure_reason']}")

        all_results[label] = result

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=list)
    print(f"\nResults written to {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
