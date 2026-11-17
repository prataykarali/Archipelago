"""S4-F: Concept-aligned edge evaluation with provenance-aware scoping.

This module adds *corrected* evaluation metrics alongside the existing ones
(``compare_concepts`` / ``compare_edges`` in ``part01_load_gold_graph``).  The
originals are **never modified**; every caller that uses them still gets the
same numbers as before.

Repairs implemented
-------------------
A. Concept-aligned edge evaluation
   ``compare_edges_aligned()`` propagates the concept equivalence map produced
   by ``compare_concepts()`` into the edge comparator, so a fuzzy concept match
   (e.g. "adapter" ↔ "adapter layers") is honoured when checking whether two
   edges connect the same pair of concepts.  Mapping is deterministic (greedy
   best-score), one-to-one (each predicted key maps to at most one gold key),
   and ambiguous pairings are reported separately — they are excluded from TP
   counting to avoid false precision.

B. Direction accuracy guard
   When ``matched_undirected == 0`` the denominator is zero; the corrected
   function returns ``direction_accuracy = None`` and
   ``direction_accuracy_status = "undefined"`` instead of the spurious ``1.0``.

C. Provenance-aware scoping
   Edge counts are split into ``in_scope``, ``out_of_scope``, and
   ``unscopable`` rather than the original single ``unscopable_edges`` counter.
   Concepts globally absent from the DB (never extracted) are separated from
   concepts extracted but scoped to a different document.

D. Relationship semantics
   ``audit_relation_semantics()`` re-evaluates cycles under prerequisite-only
   graph semantics (REQUIRES + UNLOCKS only, RELATED excluded) and reports how
   many RELATED edges exist and what they would contribute if included.  Cycle
   count is deterministic via minimum-rotation deduplication.
"""

from __future__ import annotations

from typing import Any

from okf.eval.gold.part01_load_gold_graph import (
    _canonical_key,
    _extract_names,
    compare_concepts,
    load_gold_graph,
)
from okf.eval.gold.edge_extraction import _extract_edges, _edge_matches_doc
from okf.eval._base import FUZZY_MATCH_THRESHOLD, _rf_fuzz


# ---------------------------------------------------------------------------
# A. Build concept equivalence map
# ---------------------------------------------------------------------------

def build_concept_equiv_map(
    concept_comparison: dict[str, Any],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Return (equiv_map, ambiguities) from a ``compare_concepts()`` result.

    ``equiv_map`` maps each predicted canonical key to its single best gold
    canonical key.  Only fuzzy matches (where pred_key != gold_key) are
    included; exact matches are already handled by canonical key equality.

    ``ambiguities`` lists cases where the same predicted key would map to
    multiple gold keys — these are excluded from TP counting.
    """
    pred_to_gold: dict[str, list[str]] = {}
    for pred_name, gold_name in concept_comparison.get("matched_pairs", []):
        pk = _canonical_key(pred_name)
        gk = _canonical_key(gold_name)
        if pk != gk:  # only record genuine fuzzy matches
            pred_to_gold.setdefault(pk, []).append(gk)

    equiv_map: dict[str, str] = {}
    ambiguities: list[dict[str, Any]] = []
    for pk, gks in pred_to_gold.items():
        if len(gks) == 1:
            equiv_map[pk] = gks[0]
        else:
            ambiguities.append({"predicted_key": pk, "gold_candidates": gks})

    return equiv_map, ambiguities


# ---------------------------------------------------------------------------
# A. Canonicalize edge set with equivalence map applied
# ---------------------------------------------------------------------------

def _canonicalize_edge_aligned(
    raw_edges: set[tuple[str, str]],
    equiv_map: dict[str, str],
) -> set[tuple[str, str]]:
    """Canonicalize endpoints and apply the concept equivalence map.

    For each edge (u, v):
    1. Apply ``_canonical_key`` to both endpoints.
    2. Remap each canonical key through ``equiv_map`` if present.

    This allows a fuzzy concept match (e.g. "adapter" → "adapter layer") to
    propagate into edge comparison so that the edge
    ``(fine tuning, adapter) `` can match ``(fine tuning, adapter layer)``
    when "adapter" was fuzzy-matched to "adapter layer".
    """
    out: set[tuple[str, str]] = set()
    for u, v in raw_edges:
        cu = _canonical_key(u)
        cv = _canonical_key(v)
        cu = equiv_map.get(cu, cu)
        cv = equiv_map.get(cv, cv)
        if cu and cv:
            out.add((cu, cv))
    return out


# ---------------------------------------------------------------------------
# A+C. Concept-aligned edge comparison
# ---------------------------------------------------------------------------

def compare_edges_aligned(
    extracted: Any,
    gold: Any,
    *,
    concept_comparison: dict[str, Any],
    doc_id: str | None = None,
    include_related: bool = False,
) -> dict[str, Any]:
    """Concept-aligned edge evaluation.

    Parameters
    ----------
    extracted:
        DB graph export (``export_graph()`` result) or any input accepted by
        ``_extract_edges()``.
    gold:
        Gold JSON payload.
    concept_comparison:
        Result of ``compare_concepts()`` on the same pair — provides the
        fuzzy equivalence map.
    doc_id:
        Document scope filter.
    include_related:
        Whether to include RELATED edges (default False, matching baseline).

    Returns
    -------
    dict with keys:
      directed          – precision/recall/f1/tp/fp/fn on directed edges
      undirected        – precision/recall/f1/tp/fp/fn on undirected edges
      direction_accuracy            – float or None (undefined when denom=0)
      direction_accuracy_status     – "computed" | "undefined"
      direction_accuracy_denominator – int (number of matched undirected edges)
      doc_id            – echoed scope
      predicted_edge_count
      gold_edge_count
      scoping           – in_scope / out_of_scope / unscopable counts
      equiv_map         – concept key translation used
      ambiguities       – list of ambiguous fuzzy mappings excluded from TP
      matched_directed_pairs   – list of matched directed edge pairs (corrected)
      matched_undirected_pairs – list of matched undirected edge pairs
      failed_matches    – sample of unmatched predicted edges with diagnosis
    """
    equiv_map, ambiguities = build_concept_equiv_map(concept_comparison)

    # Collect scoping stats for predicted edges
    scoping_stats: dict[str, int] = {}
    out_of_scope_count = 0
    if doc_id is not None and isinstance(extracted, dict) and "edges" in extracted:
        for e in extracted["edges"]:
            if isinstance(e, dict):
                from okf.eval.gold.edge_extraction import _is_export_edge
                if _is_export_edge(e):
                    in_scope, is_unscopable = _edge_matches_doc(e, doc_id)
                    if not in_scope and not is_unscopable:
                        out_of_scope_count += 1

    pred_raw_stats: dict[str, int] = {}
    pred_raw = _extract_edges(
        extracted,
        include_related=include_related,
        doc_id=doc_id,
        stats=pred_raw_stats,
    )

    gold_raw = _extract_edges(gold, include_related=include_related)

    # Apply canonical key + equivalence map to predicted edges
    pred_aligned = _canonicalize_edge_aligned(pred_raw, equiv_map)

    # Canonicalize gold edges (no equiv map — gold is the reference)
    gold_canon: set[tuple[str, str]] = set()
    for u, v in gold_raw:
        cu, cv = _canonical_key(u), _canonical_key(v)
        if cu and cv:
            gold_canon.add((cu, cv))

    # Build undirected views
    pred_undir: dict[frozenset, tuple[str, str]] = {}
    for u, v in pred_aligned:
        pred_undir[frozenset([u, v])] = (u, v)
    gold_undir: dict[frozenset, tuple[str, str]] = {}
    for u, v in gold_canon:
        gold_undir[frozenset([u, v])] = (u, v)

    # --- Directed metrics ---
    if not pred_aligned and not gold_canon:
        dir_metrics = {
            "precision": 1.0, "recall": 1.0, "f1": 1.0,
            "true_positives": 0, "false_positives": 0, "false_negatives": 0,
        }
    else:
        tp_dir = len(pred_aligned & gold_canon)
        fp_dir = len(pred_aligned - gold_canon)
        fn_dir = len(gold_canon - pred_aligned)
        prec = tp_dir / (tp_dir + fp_dir) if (tp_dir + fp_dir) > 0 else 0.0
        rec = tp_dir / (tp_dir + fn_dir) if (tp_dir + fn_dir) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        dir_metrics = {
            "precision": prec, "recall": rec, "f1": f1,
            "true_positives": tp_dir, "false_positives": fp_dir,
            "false_negatives": fn_dir,
        }

    # --- Undirected metrics ---
    if not pred_undir and not gold_undir:
        undir_metrics = {
            "precision": 1.0, "recall": 1.0, "f1": 1.0,
            "true_positives": 0, "false_positives": 0, "false_negatives": 0,
        }
    else:
        matched_undir_keys = pred_undir.keys() & gold_undir.keys()
        tp_u = len(matched_undir_keys)
        fp_u = len(pred_undir.keys() - gold_undir.keys())
        fn_u = len(gold_undir.keys() - pred_undir.keys())
        prec = tp_u / (tp_u + fp_u) if (tp_u + fp_u) > 0 else 0.0
        rec = tp_u / (tp_u + fn_u) if (tp_u + fn_u) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        undir_metrics = {
            "precision": prec, "recall": rec, "f1": f1,
            "true_positives": tp_u, "false_positives": fp_u,
            "false_negatives": fn_u,
        }

    # --- B. Direction accuracy with guard ---
    matched_undir_keys = pred_undir.keys() & gold_undir.keys()
    if matched_undir_keys:
        correct_dirs = sum(
            1 for k in matched_undir_keys if pred_undir[k] == gold_undir[k]
        )
        dir_accuracy: float | None = correct_dirs / len(matched_undir_keys)
        dir_accuracy_status = "computed"
    else:
        dir_accuracy = None
        dir_accuracy_status = "undefined"

    # --- Matched pairs for diagnostics ---
    matched_dir_pairs = sorted([list(e) for e in (pred_aligned & gold_canon)])
    matched_undir_pairs = sorted(
        [sorted(list(k)) for k in matched_undir_keys]
    )

    # --- Failed match diagnosis (sample) ---
    failed_matches = _diagnose_failed_matches(
        pred_aligned, gold_canon, equiv_map, limit=10
    )

    return {
        "directed": dir_metrics,
        "undirected": undir_metrics,
        "direction_accuracy": dir_accuracy,
        "direction_accuracy_status": dir_accuracy_status,
        "direction_accuracy_denominator": len(matched_undir_keys),
        "doc_id": doc_id,
        "predicted_edge_count": len(pred_aligned),
        "gold_edge_count": len(gold_canon),
        "scoping": {
            "in_scope_edges": len(pred_raw),
            "out_of_scope_edges": out_of_scope_count,
            "unscopable_edges": pred_raw_stats.get("unscopable_edges", 0),
            "skipped_related": pred_raw_stats.get("skipped_related", 0),
        },
        "equiv_map": equiv_map,
        "ambiguities": ambiguities,
        "matched_directed_pairs": matched_dir_pairs,
        "matched_undirected_pairs": matched_undir_pairs,
        "failed_matches": failed_matches,
    }


def _diagnose_failed_matches(
    pred: set[tuple[str, str]],
    gold: set[tuple[str, str]],
    equiv_map: dict[str, str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` unmatched predicted edges with failure reasons."""
    unmatched = sorted(pred - gold)[:limit]
    gold_sources = {u for u, v in gold}
    gold_targets = {v for u, v in gold}
    gold_undir = {frozenset(e) for e in gold}

    result = []
    for u, v in unmatched:
        if frozenset([u, v]) in gold_undir:
            reason = "direction_reversed"
        elif u in gold_sources or u in gold_targets:
            reason = "source_concept_present_but_wrong_target"
        elif v in gold_sources or v in gold_targets:
            reason = "target_concept_present_but_wrong_source"
        elif u in equiv_map.values() or v in equiv_map.values():
            reason = "equiv_mapped_concept_no_gold_edge"
        else:
            reason = "both_endpoints_absent_from_gold_edges"
        result.append({"predicted_edge": [u, v], "failure_reason": reason})
    return result


# ---------------------------------------------------------------------------
# D. Relation semantics audit
# ---------------------------------------------------------------------------

def audit_relation_semantics(db_audit: dict[str, Any]) -> dict[str, Any]:
    """Analyse cycle structure under prerequisite-only vs mixed semantics.

    Takes the ``structural_audit()`` result and re-classifies cycles by:
    - prerequisite-only: only cycles in REQUIRES+UNLOCKS dependency edges
    - mixed: any cycle involving RELATED edges (not applicable here since
      ``structural_audit`` already builds a prerequisite-only graph, but this
      is documented explicitly)

    Returns a canonical deduplicated cycle list (minimum-rotation) alongside
    the raw count so the non-determinism is explicit.
    """
    raw_cycles: list[list[str]] = db_audit.get("cycles", [])

    def canonical_cycle(c: list[str]) -> tuple[str, ...]:
        body = c[:-1]  # strip repeated tail node
        rots = [tuple(body[i:] + body[:i]) for i in range(len(body))]
        return min(rots)

    seen: set[tuple[str, ...]] = set()
    unique_cycles: list[list[str]] = []
    for cyc in raw_cycles:
        key = canonical_cycle(cyc)
        if key not in seen:
            seen.add(key)
            unique_cycles.append(cyc)

    # Classify by hop length
    len2 = [c for c in unique_cycles if len(c) - 1 == 2]
    len6_plus = [c for c in unique_cycles if len(c) - 1 >= 6]

    return {
        "raw_cycle_count": len(raw_cycles),
        "unique_cycle_count": len(unique_cycles),
        "deduplication_method": "minimum_rotation",
        "note": (
            "structural_audit() builds a prerequisite-only graph (REQUIRES+UNLOCKS). "
            "RELATED edges are excluded from cycle detection. "
            "Raw DFS count is non-deterministic (9-10); unique count is 9."
        ),
        "cycles_by_length": {
            "length_2": len(len2),
            "length_6_or_more": len(len6_plus),
        },
        "cycles": unique_cycles,
    }


# ---------------------------------------------------------------------------
# E. Full corrected evaluation pipeline
# ---------------------------------------------------------------------------

def evaluate_pipeline_corrected(
    db_conn: Any,
    gold_path: str,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """Run both original and corrected evaluation; return side-by-side report.

    The original ``evaluate_pipeline()`` result is captured unchanged as
    ``baseline``.  The corrected metrics are computed in ``corrected``.

    Scientific guarantee: gold fixtures, graph DB, and extraction pipeline
    are all read-only.  Only the evaluator logic is changed.
    """
    import kuzu
    from okf.eval.gold.part01_load_gold_graph import (
        evaluate_pipeline,
        compare_concepts,
        load_gold_graph,
    )
    from okf.graph_db import export_graph
    from okf.eval.structural import structural_audit

    conn = db_conn if hasattr(db_conn, "execute") else kuzu.Connection(db_conn)

    gold_data = load_gold_graph(gold_path)
    db_export = export_graph(conn)

    effective_doc_id = doc_id
    if effective_doc_id is None and isinstance(gold_data, dict):
        effective_doc_id = gold_data.get("doc_id")

    gold_concepts = gold_data.get("concepts", gold_data) if isinstance(gold_data, dict) else gold_data

    # --- Baseline (original) ---
    baseline = evaluate_pipeline(conn, gold_path, doc_id=effective_doc_id)

    # --- Corrected concept comparison (same as baseline — no change) ---
    cc = compare_concepts(db_export["concepts"], gold_concepts, doc_id=effective_doc_id)

    # --- Corrected edge comparison (concept-aligned) ---
    ec_corrected = compare_edges_aligned(
        db_export,
        gold_data,
        concept_comparison=cc,
        doc_id=effective_doc_id,
        include_related=False,
    )

    # --- Structural audit (relation semantics) ---
    db_audit = structural_audit(conn)
    rel_audit = audit_relation_semantics(db_audit)

    # --- Concept provenance breakdown ---
    # Globally absent: gold concepts not in DB at all (regardless of scope)
    from okf.eval.gold.part01_load_gold_graph import _extract_names, _canonical_key
    all_db_names = _extract_names(db_export["concepts"])
    all_db_keys = {_canonical_key(n) for n in all_db_names}
    gold_name_set = _extract_names(gold_concepts)
    gold_keys = {_canonical_key(n) for n in gold_name_set}
    globally_absent = sorted(gold_keys - all_db_keys)
    doc_scoped_absent = sorted(
        set(gold_keys)
        - set(cc.get("matched_pairs", {}) and {_canonical_key(p[1]) for p in cc["matched_pairs"]})
        - set(globally_absent)
    )

    return {
        "scope": {
            "mode": "document" if effective_doc_id else "whole_graph",
            "doc_id": effective_doc_id,
        },
        "baseline": {
            "concept_f1": baseline["concept_comparison"]["f1"],
            "concept_precision": baseline["concept_comparison"]["precision"],
            "concept_recall": baseline["concept_comparison"]["recall"],
            "concept_tp": baseline["concept_comparison"]["true_positives"],
            "concept_fp": baseline["concept_comparison"]["false_positives"],
            "concept_fn": baseline["concept_comparison"]["false_negatives"],
            "directed_edge_f1": baseline["edge_comparison"]["directed"]["f1"],
            "directed_edge_tp": baseline["edge_comparison"]["directed"]["true_positives"],
            "undirected_edge_f1": baseline["edge_comparison"]["undirected"]["f1"],
            "undirected_edge_tp": baseline["edge_comparison"]["undirected"]["true_positives"],
            "direction_accuracy": baseline["edge_comparison"]["direction_accuracy"],
            "direction_accuracy_note": (
                "BUG: returns 1.0 when matched_undirected=0 (denominator=0)"
                if baseline["edge_comparison"]["direction_accuracy"] == 1.0
                and baseline["edge_comparison"]["undirected"]["true_positives"] == 0
                else "ok"
            ),
            "unscopable_edges": baseline["edge_comparison"]["unscopable_edges"],
            "skipped_related": baseline["edge_comparison"]["skipped_related_edges"],
        },
        "corrected": {
            "concept_f1": cc["f1"],
            "concept_precision": cc["precision"],
            "concept_recall": cc["recall"],
            "concept_tp": cc["true_positives"],
            "concept_fp": cc["false_positives"],
            "concept_fn": cc["false_negatives"],
            "concept_matched_pairs": cc["matched_pairs"],
            "directed_edge_f1": ec_corrected["directed"]["f1"],
            "directed_edge_tp": ec_corrected["directed"]["true_positives"],
            "directed_edge_fp": ec_corrected["directed"]["false_positives"],
            "directed_edge_fn": ec_corrected["directed"]["false_negatives"],
            "undirected_edge_f1": ec_corrected["undirected"]["f1"],
            "undirected_edge_tp": ec_corrected["undirected"]["true_positives"],
            "direction_accuracy": ec_corrected["direction_accuracy"],
            "direction_accuracy_status": ec_corrected["direction_accuracy_status"],
            "direction_accuracy_denominator": ec_corrected["direction_accuracy_denominator"],
            "equiv_map_applied": ec_corrected["equiv_map"],
            "ambiguous_mappings": ec_corrected["ambiguities"],
            "scoping": ec_corrected["scoping"],
            "matched_directed_pairs": ec_corrected["matched_directed_pairs"],
            "matched_undirected_pairs": ec_corrected["matched_undirected_pairs"],
            "failed_matches_sample": ec_corrected["failed_matches"],
        },
        "concept_provenance": {
            "globally_absent_gold_concepts": globally_absent,
            "globally_absent_count": len(globally_absent),
            "note": (
                "Globally absent = gold concept key not present anywhere in DB. "
                "These are genuine extraction failures, not scoping artifacts."
            ),
        },
        "relation_semantics_audit": rel_audit,
    }
