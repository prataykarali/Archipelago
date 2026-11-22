"""Relationship prediction evaluation for Archipelago D5.1/D5.2.

Separated from d5_1_evaluation_suite.py to keep files under 500 lines.
P0-3 fix: exact (source, predicate, destination) triple equality required.
The engine graph stores only: REQUIRES, RELATED, UNLOCKS.
Queries expecting USES, CONTRASTS_WITH, APPLIES_TO are explicitly disclosed
as PREDICATE_ABSENT_IN_GRAPH rather than silently counted as misses.

ACM SIGIR 2027 Demonstrations Track — D5.2 P0 audit fixes
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.answer import Engine

# Predicates the engine graph actually stores
GRAPH_PREDICATES: frozenset[str] = frozenset({"REQUIRES", "RELATED", "UNLOCKS"})
# Predicates referenced in queries but absent from the engine graph
ABSENT_PREDICATES: frozenset[str] = frozenset({"USES", "CONTRASTS_WITH", "APPLIES_TO"})


def evaluate_relationship_predictions(
    queries: list[dict[str, Any]], engine: Engine
) -> dict[str, Any]:
    """Experiment C: Evaluate relationship triples ACTUALLY returned by Archipelago.

    P0-3 fix: Requires exact (source, predicate, destination) triple equality.
    The engine graph contains only: REQUIRES, RELATED, UNLOCKS.
    Queries expecting USES, CONTRASTS_WITH, APPLIES_TO will never match because
    those predicates do not exist in the engine graph. This gap is reported
    explicitly rather than hidden by label relaxation.

    Args:
        queries: Loaded from queries_heldout_50.json.
        engine: Initialized Engine instance.

    Returns:
        Dict with per-predicate breakdown, assessable precision/recall/F1,
        and per-query detail records.
    """
    rel_queries = [
        q for q in queries if q.get("category") == "relational" and "expected_relation" in q
    ]
    total_rel = len(rel_queries)

    true_positives = 0
    inverted_directions = 0
    missing_predictions = 0
    no_anchor_resolved = 0
    predicate_absent_in_graph = 0

    detailed_cases: list[dict[str, Any]] = []
    per_predicate: dict[str, dict[str, int]] = {}

    for q in rel_queries:
        qid: str = q["query_id"]
        qtext: str = q["query"]
        exp: dict[str, str] = q["expected_relation"]
        f_exp: str = exp["from"]
        t_exp: str = exp["to"]
        r_exp: str = exp["rel"]

        per_predicate.setdefault(
            r_exp, {"total": 0, "tp": 0, "inverted": 0, "missing": 0, "no_anchor": 0}
        )
        per_predicate[r_exp]["total"] += 1

        resp = engine.answer(qtext)
        p = resp["payload"]
        anchor = p.get("anchor_concept")
        anchor_id: str | None = anchor.get("id") if isinstance(anchor, dict) else None

        predicted_triples: set[tuple[str, str, str]] = set()
        if anchor_id is None:
            no_anchor_resolved += 1
            per_predicate[r_exp]["no_anchor"] += 1
            verdict = "NO_ANCHOR_RESOLVED"
        else:
            # Read edge triples directly from live graph (payload lists lose rel_type)
            for rel_type, neighbor_id in engine.graph.out.get(anchor_id, []):
                predicted_triples.add((anchor_id, rel_type, neighbor_id))
            for rel_type, source_id in engine.graph.inn.get(anchor_id, []):
                predicted_triples.add((source_id, rel_type, anchor_id))

            # P0-3: exact triple equality — all 3 fields must match
            forward_triple = (f_exp, r_exp, t_exp)
            inverted_triple = (t_exp, r_exp, f_exp)

            tp_found = forward_triple in predicted_triples
            inverted_found = (not tp_found) and (inverted_triple in predicted_triples)

            if tp_found:
                true_positives += 1
                per_predicate[r_exp]["tp"] += 1
                verdict = "CORRECT_DIRECTION"
            elif inverted_found:
                inverted_directions += 1
                per_predicate[r_exp]["inverted"] += 1
                verdict = "INVERTED_DIRECTION"
            elif r_exp in ABSENT_PREDICATES:
                predicate_absent_in_graph += 1
                missing_predictions += 1
                per_predicate[r_exp]["missing"] += 1
                verdict = "PREDICATE_ABSENT_IN_GRAPH"
            else:
                missing_predictions += 1
                per_predicate[r_exp]["missing"] += 1
                verdict = "MISSING_PREDICTION"

        detailed_cases.append(
            {
                "query_id": qid,
                "query": qtext,
                "anchor_resolved": anchor_id,
                "expected_triple": f"({f_exp}, {r_exp}, {t_exp})",
                "expected_predicate_in_graph": r_exp in GRAPH_PREDICATES,
                "verdict": verdict,
                "triples_surfaced_count": len(predicted_triples),
            }
        )

    # Denominator for precision: total triples surfaced from anchor nodes
    total_surfaced = sum(
        len(engine.graph.out.get(c["anchor_resolved"] or "", [])) for c in detailed_cases
    )
    # Denominator for recall: only assessable queries (anchor resolved + predicate in graph)
    assessable = total_rel - no_anchor_resolved - predicate_absent_in_graph
    precision = round(true_positives / total_surfaced, 4) if total_surfaced else 0.0
    recall_assessable = round(true_positives / assessable, 4) if assessable else 0.0
    f1 = (
        round(2 * precision * recall_assessable / (precision + recall_assessable), 4)
        if (precision + recall_assessable)
        else 0.0
    )

    return {
        "total_relational_queries": total_rel,
        "assessable_queries": assessable,
        "true_positives": true_positives,
        "inverted_directions": inverted_directions,
        "missing_predictions": missing_predictions,
        "no_anchor_resolved": no_anchor_resolved,
        "predicate_absent_in_graph": predicate_absent_in_graph,
        "graph_predicates_available": sorted(GRAPH_PREDICATES),
        "query_predicates_absent_from_graph": sorted(ABSENT_PREDICATES),
        "precision_over_all_surfaced_triples": precision,
        "recall_over_assessable_queries": recall_assessable,
        "f1_assessable": f1,
        "per_predicate_breakdown": per_predicate,
        "detailed_cases": detailed_cases,
        "disclosure": (
            "Precision denominator is the total triples surfaced from engine.graph.out for each "
            "resolved anchor. USES, CONTRASTS_WITH, and APPLIES_TO predicates are absent from "
            "the engine graph; queries expecting those predicates are counted under "
            "predicate_absent_in_graph and excluded from the assessable recall denominator."
        ),
    }
