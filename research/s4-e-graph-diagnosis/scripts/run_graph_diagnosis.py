#!/usr/bin/env python3
"""
S4-E Graph Evaluation Diagnosis Script.

Reproduces S1 document-scoped and whole-graph evaluations, performs root-cause
investigation into 0% Edge F1, analyzes the 9 graph cycles, audits the 157 edge
provenance issues (and 101 unscopable edges), and outputs a structured diagnostic artifact.

Usage:
    python3 research/s4-e-graph-diagnosis/scripts/run_graph_diagnosis.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import kuzu
from okf.canonicalize import _concept_key, canonicalize_name
from okf.eval._base import _rf_fuzz, FUZZY_MATCH_THRESHOLD
from okf.eval.gold.edge_extraction import _extract_edges, _edge_matches_doc
from okf.eval.gold.part01_load_gold_graph import (
    _canonical_key,
    _canonicalize_edge_set,
    compare_concepts,
    compare_edges,
    load_gold_graph,
)
from okf.eval.structural import structural_audit
from okf.graph_db import export_graph


def diagnose_graph(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database missing at {db_path}")

    conn = kuzu.Connection(kuzu.Database(str(db_path), read_only=True))
    export = export_graph(conn)
    audit = structural_audit(conn)

    # 1. Reproduce S1 Evaluations
    gold_files = {
        "gold_lora": (ROOT / "pilot_corpus" / "gold" / "gold_lora.json", "papers/Hu2021_LoRA.pdf"),
        "gold_attention": (ROOT / "pilot_corpus" / "gold" / "gold_attention.json", "papers/Vaswani2017_Attention_Is_All_You_Need.pdf"),
        "gold_curriculum": (ROOT / "pilot_corpus" / "gold" / "gold_curriculum.json", None),
    }

    eval_results = {}
    for gkey, (gpath, doc_id) in gold_files.items():
        gdata = load_gold_graph(str(gpath))
        # whole graph
        c_whole = compare_concepts(export["concepts"], gdata["concepts"] if "concepts" in gdata else gdata, doc_id=None)
        e_whole = compare_edges(export, gdata, doc_id=None)
        
        # doc scoped if applicable
        c_scoped = None
        e_scoped = None
        if doc_id:
            c_scoped = compare_concepts(export["concepts"], gdata["concepts"] if "concepts" in gdata else gdata, doc_id=doc_id)
            e_scoped = compare_edges(export, gdata, doc_id=doc_id)

        eval_results[gkey] = {
            "gold_path": str(gpath.relative_to(ROOT)),
            "doc_id": doc_id,
            "whole_graph": {
                "concept": c_whole,
                "edge": e_whole,
            },
            "document_scoped": {
                "concept": c_scoped,
                "edge": e_scoped,
            } if doc_id else None,
        }

    # 2. Cycle Diagnosis
    cycles = audit.get("cycles", [])
    cycle_details = []
    edges_by_pair = {}
    for e in export["edges"]:
        pair = (e["from_id"], e["to_id"])
        edges_by_pair.setdefault(pair, []).append(e)

    for cyc in cycles:
        hops = []
        for i in range(len(cyc) - 1):
            u, v = cyc[i], cyc[i + 1]
            matched = edges_by_pair.get((u, v), [])
            for m in matched:
                hops.append({
                    "from_id": u,
                    "to_id": v,
                    "edge_type": m["edge_type"],
                    "relation": m.get("relation"),
                    "source": m.get("source"),
                })
        cycle_details.append({
            "length": len(cyc) - 1,
            "nodes": cyc,
            "hops": hops,
            "is_symmetric_dual_insertion": (len(cyc) - 1 == 2 and any(h.get("source") == "librarian_upload" for h in hops)),
        })

    # 3. Provenance Issues Diagnosis
    issues = audit.get("edge_provenance_issues", [])
    prov_counter = {}
    etype_counter = {}
    for iss in issues:
        p = str(iss.get("provenance"))
        et = str(iss.get("edge_type"))
        prov_counter[p] = prov_counter.get(p, 0) + 1
        etype_counter[et] = etype_counter.get(et, 0) + 1

    # Unscopable directed edges count: REQUIRES + UNLOCKS among provenance issues
    unscopable_directed = sum(1 for iss in issues if iss.get("edge_type") in ("REQUIRES", "UNLOCKS"))

    # 4. Detailed Edge Failure Analysis for LoRA and Attention
    edge_failures = {}
    for gkey in ("gold_lora", "gold_attention"):
        gpath, doc_id = gold_files[gkey]
        gdata = load_gold_graph(str(gpath))
        gold_edges_raw = _extract_edges(gdata)
        gold_edges_canon = _canonicalize_edge_set(gold_edges_raw)

        ext_edges_raw = _extract_edges(export, doc_id=doc_id)
        ext_edges_canon = _canonicalize_edge_set(ext_edges_raw)

        # Concept mapping for endpoints
        matched_concept_pairs = eval_results[gkey]["document_scoped"]["concept"]["matched_pairs"]
        concept_align_map = {pred: gold for pred, gold in matched_concept_pairs}

        # Inspect gold edges and why each failed
        gold_edge_status = []
        for u, v in sorted(gold_edges_canon):
            # check if endpoints exist in predicted concepts
            u_in_pred = any(u == _canonical_key(c["name"]) for c in export["concepts"].values() if isinstance(c, dict))
            v_in_pred = any(v == _canonical_key(c["name"]) for c in export["concepts"].values() if isinstance(c, dict))
            gold_edge_status.append({
                "source": u,
                "target": v,
                "source_in_predicted_concepts": u_in_pred,
                "target_in_predicted_concepts": v_in_pred,
                "both_endpoints_exist": u_in_pred and v_in_pred,
            })

        edge_failures[gkey] = {
            "doc_id": doc_id,
            "predicted_edge_count": len(ext_edges_canon),
            "gold_edge_count": len(gold_edges_canon),
            "gold_edges": gold_edge_status,
            "predicted_edges": sorted(list(ext_edges_canon)),
        }

    return {
        "stats": export["stats"],
        "structural_summary": {
            "concept_count": len(export["concepts"]),
            "edge_count": len(export["edges"]),
            "cycles_count": len(cycles),
            "edge_provenance_issues_count": len(issues),
            "unscopable_directed_edges": unscopable_directed,
            "skipped_related_edges": export["stats"].get("related_edges", 0),
        },
        "provenance_breakdown": {
            "by_source_tag": prov_counter,
            "by_edge_type": etype_counter,
        },
        "cycle_details": cycle_details,
        "evaluations": eval_results,
        "edge_failures": edge_failures,
    }


def main() -> int:
    out_dir = ROOT / "research" / "s4-e-graph-diagnosis"
    out_dir.mkdir(parents=True, exist_ok=True)

    db_path = ROOT / "okf_graph.db"
    diag = diagnose_graph(db_path)

    json_out = out_dir / "graph_diagnosis_summary.json"
    json_out.write_text(json.dumps(diag, indent=2) + "\n", encoding="utf-8")
    print(f"✓ Wrote structured diagnosis JSON: {json_out.relative_to(ROOT)}")

    # Print summary to console
    print("\n" + "=" * 60)
    print("S4-E GRAPH EVALUATION DIAGNOSIS SUMMARY")
    print("=" * 60)
    print(f"Concepts in Graph:              {diag['structural_summary']['concept_count']}")
    print(f"Edges in Graph:                 {diag['structural_summary']['edge_count']}")
    print(f"  REQUIRES Edges:               {diag['stats']['requires_edges']}")
    print(f"  UNLOCKS Edges:                {diag['stats']['unlocks_edges']}")
    print(f"  RELATED Edges (Skipped):      {diag['stats']['related_edges']}")
    print(f"Graph Cycles:                   {diag['structural_summary']['cycles_count']}")
    print(f"Edge Provenance Issues:         {diag['structural_summary']['edge_provenance_issues_count']}")
    print(f"Unscopable Directed Edges:      {diag['structural_summary']['unscopable_directed_edges']}")
    print("-" * 60)
    print("Reproduced S1 Gold Metrics (Document-Scoped):")
    lora_e = diag["evaluations"]["gold_lora"]["document_scoped"]["edge"]["directed"]
    lora_c = diag["evaluations"]["gold_lora"]["document_scoped"]["concept"]
    att_e = diag["evaluations"]["gold_attention"]["document_scoped"]["edge"]["directed"]
    att_c = diag["evaluations"]["gold_attention"]["document_scoped"]["concept"]
    print(f"  LoRA Concept F1:              {lora_c['f1']*100:.2f}% (P={lora_c['precision']*100:.2f}%, R={lora_c['recall']*100:.2f}%)")
    print(f"  LoRA Edge F1:                 {lora_e['f1']*100:.2f}% (P={lora_e['precision']*100:.2f}%, R={lora_e['recall']*100:.2f}%)")
    print(f"  Attention Concept F1:         {att_c['f1']*100:.2f}% (P={att_c['precision']*100:.2f}%, R={att_c['recall']*100:.2f}%)")
    print(f"  Attention Edge F1:            {att_e['f1']*100:.2f}% (P={att_e['precision']*100:.2f}%, R={att_e['recall']*100:.2f}%)")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
