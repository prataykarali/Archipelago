"""S4-G1: Audit of problematic heuristics in the baseline graph and extraction pipeline.

Investigates:
1. Direction inferred from order of mention (co_occur_score / text.index)
2. Difficulty-based ordering (foundational < intermediate < advanced)
3. Alphabetical fallback (name_a < name_b)
4. Reciprocal / dual REQUIRES/UNLOCKS insertion (causing length-2 cycles)
5. Missing intermediate concepts (caused by 'one central concept' prompt constraint)
6. Concept aliases incorrectly classified as absent
7. Conflation of relationship types (dependency vs usage vs part-of vs co-occurrence)
"""

from __future__ import annotations

import collections
import re
from typing import Any

from okf.canonicalize import _concept_key, canonicalize_name
from okf.query_rows import query_rows
from okf.eval.gold.part01_load_gold_graph import _canonical_key


def audit_baseline_heuristics(db_conn: Any) -> dict[str, Any]:
    """Inspect the baseline okf_graph.db for evidence of problematic heuristics.

    Returns structured findings and quantitative metrics.
    """
    findings: dict[str, Any] = {}

    # 1. Reciprocal / dual insertion causing length-2 cycles
    # Query all REQUIRES and UNLOCKS edges
    rows_req = list(
        query_rows(
            db_conn,
            "MATCH (a:Concept)-[r:REQUIRES]->(b:Concept) RETURN a.id, b.id, a.name, b.name, r.source",
        )
    )
    rows_unl = list(
        query_rows(
            db_conn,
            "MATCH (a:Concept)-[r:UNLOCKS]->(b:Concept) RETURN a.id, b.id, a.name, b.name, r.source",
        )
    )

    req_pairs = {(r[0], r[1]): {"src": r[2], "dst": r[3], "source": r[4]} for r in rows_req}
    unl_pairs = {(r[0], r[1]): {"src": r[2], "dst": r[3], "source": r[4]} for r in rows_unl}

    # In baseline: REQUIRES (a -> b) means a depends on b (learning order b -> a).
    # UNLOCKS (a -> b) means a enables b (learning order a -> b).
    # A reciprocal 2-cycle occurs when a REQUIRES b AND b REQUIRES a, OR
    # when a REQUIRES b (order b->a) and a UNLOCKS b (order a->b).
    reciprocal_conflicts = []
    for (u, v), req_info in req_pairs.items():
        if (v, u) in req_pairs:
            reciprocal_conflicts.append(
                {
                    "type": "mutual_REQUIRES",
                    "concept_a": req_info["src"],
                    "concept_b": req_info["dst"],
                    "source_a": req_info["source"],
                    "source_b": req_pairs[(v, u)]["source"],
                }
            )
        if (u, v) in unl_pairs:
            # a REQUIRES b AND a UNLOCKS b (opposite learning direction)
            reciprocal_conflicts.append(
                {
                    "type": "simultaneous_REQUIRES_and_UNLOCKS",
                    "concept_a": req_info["src"],
                    "concept_b": req_info["dst"],
                    "req_source": req_info["source"],
                    "unl_source": unl_pairs[(u, v)]["source"],
                }
            )

    findings["reciprocal_conflicts"] = {
        "count": len(reciprocal_conflicts),
        "examples": reciprocal_conflicts[:8],
    }

    # 2. Check relation type distribution in baseline
    rel_counts = collections.Counter()
    for r in query_rows(db_conn, "MATCH ()-[r:REQUIRES]->() RETURN count(r)"):
        rel_counts["REQUIRES"] = int(r[0])
    for r in query_rows(db_conn, "MATCH ()-[r:UNLOCKS]->() RETURN count(r)"):
        rel_counts["UNLOCKS"] = int(r[0])
    for r in query_rows(db_conn, "MATCH ()-[r:RELATED]->() RETURN count(r)"):
        rel_counts["RELATED"] = int(r[0])

    findings["relation_type_distribution"] = dict(rel_counts)

    # 3. Audit RELATED edges subtypes
    subtypes = collections.Counter()
    for r in query_rows(db_conn, "MATCH ()-[r:RELATED]->() RETURN r.relation_type"):
        subtypes[str(r[0])] += 1
    findings["related_subtypes"] = dict(subtypes)

    # 4. Provenance audit of directed edges
    invalid_prov_count = 0
    prov_sources = collections.Counter()
    for row in rows_req + rows_unl:
        source_val = row[4]
        if not source_val or ":" not in str(source_val):
            invalid_prov_count += 1
        prov_sources[str(source_val).split(":")[0] if source_val else "None"] += 1

    findings["directed_edge_provenance"] = {
        "total_directed_edges": len(rows_req) + len(rows_unl),
        "invalid_provenance_count": invalid_prov_count,
        "unscopable_rate": (
            invalid_prov_count / (len(rows_req) + len(rows_unl))
            if (rows_req or rows_unl)
            else 0.0
        ),
        "top_sources": prov_sources.most_common(5),
    }

    # 5. Check missing intermediate concepts in LoRA & Attention
    # Concepts in gold but missing from DB
    from okf.eval.gold.part01_load_gold_graph import load_gold_graph
    from okf.graph_db import export_graph

    export = export_graph(db_conn)
    concepts_dict = export.get("concepts", {})
    all_db_concepts = set()
    if isinstance(concepts_dict, dict):
        for cid, cinfo in concepts_dict.items():
            all_db_concepts.add(_canonical_key(cinfo.get("name", cid)))
    elif isinstance(concepts_dict, list):
        for c in concepts_dict:
            if isinstance(c, dict):
                all_db_concepts.add(_canonical_key(c.get("name") or c.get("concept_name", "")))
            elif isinstance(c, str):
                all_db_concepts.add(_canonical_key(c))

    gold_missing_analysis = {}
    for label, gold_file in [
        ("LoRA", "pilot_corpus/gold/gold_lora.json"),
        ("Attention", "pilot_corpus/gold/gold_attention.json"),
    ]:
        try:
            gold = load_gold_graph(gold_file)
            gold_concepts = gold.get("concepts", [])
            missing = [gc for gc in gold_concepts if _canonical_key(gc) not in all_db_concepts]
            present = [gc for gc in gold_concepts if _canonical_key(gc) in all_db_concepts]
            gold_missing_analysis[label] = {
                "total_gold_concepts": len(gold_concepts),
                "missing_count": len(missing),
                "present_count": len(present),
                "missing_rate": len(missing) / len(gold_concepts) if gold_concepts else 0.0,
                "missing_sample": missing[:8],
                "present_sample": present,
            }
        except Exception as e:
            gold_missing_analysis[label] = {"error": str(e)}

    findings["missing_intermediate_concepts"] = gold_missing_analysis

    # 6. Audit alphabetical and order-of-mention heuristic risk
    # In okf/relations/part03_direction.py, lines 63-87:
    # Any tie in co-occurrence or chunk position falls back to difficulty, then alphabetical.
    # Count how many directed edges in okf_graph.db have from_name < to_name alphabetically.
    alpha_aligned = 0
    total_edges = 0
    for row in rows_req + rows_unl:
        name_a = str(row[2]).strip().lower()
        name_b = str(row[3]).strip().lower()
        if name_a and name_b and name_a != name_b:
            total_edges += 1
            if name_a < name_b:
                alpha_aligned += 1

    findings["alphabetical_ordering_correlation"] = {
        "total_directed_edges_evaluated": total_edges,
        "alphabetically_ordered": alpha_aligned,
        "ratio": alpha_aligned / total_edges if total_edges > 0 else 0.0,
        "interpretation": (
            "Ratio significantly above 50% indicates alphabetical bias from fallback heuristic"
        ),
    }

    return findings
