"""Read-only effectiveness evaluation engine for S5-D1."""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from d1_pipeline.constants import (
    LENIENT_REL_THRESHOLD,
    METRIC_DECIMALS,
    STRICT_REL_THRESHOLD,
    SYNTHETIC_BANNER,
    SYSTEM_BASELINE_1HOP,
    SYSTEM_REPAIRED_1HOP,
    SYSTEM_REPAIRED_2HOP,
    TOP_K_5,
    TOP_K_10,
)
from d1_pipeline.preflight import PreflightError, PreflightResult

SUMMARY_METRIC_KEYS = (
    "precision_at_5",
    "precision_at_10",
    "pooled_recall_at_5",
    "pooled_recall_at_10",
    "mrr_at_10",
    "ndcg_at_5",
    "ndcg_at_10",
)

POOLED_RECALL_DENOMINATOR_DOC = (
    "Total number of pooled passages for this query whose adjudicated final_grade "
    "meets or exceeds the active relevance threshold (strict: grade == 2; lenient: grade >= 1). "
    "This is a pooled recall denominator, NOT full-corpus recall."
)


def _dcg_at_k(grades: list[int], k: int) -> float:
    total = 0.0
    for rank, grade in enumerate(grades[:k], start=1):
        gain = (2**grade) - 1
        total += gain / math.log2(rank + 1)
    return total


def evaluate_query_ranking_extended(
    ranked_passage_ids: list[str],
    query_qrels: dict[str, int],
    *,
    rel_threshold: int,
) -> dict[str, Any]:
    """Compute exact IR metrics for one query ranking without treating unjudged items as 0."""
    top5 = ranked_passage_ids[:TOP_K_5]
    top10 = ranked_passage_ids[:TOP_K_10]

    unjudged_at_5 = sum(1 for p in top5 if p not in query_qrels)
    unjudged_at_10 = sum(1 for p in top10 if p not in query_qrels)
    if unjudged_at_10 > 0:
        raise PreflightError(
            f"Encountered {unjudged_at_10} unjudged passage(s) in Top-10; "
            "unjudged passages are never silently treated as irrelevant."
        )

    relevant_in_pool = {p for p, g in query_qrels.items() if g >= rel_threshold}
    n_rel = len(relevant_in_pool)

    grades_10 = [query_qrels[p] for p in top10]
    ideal_grades = sorted(query_qrels.values(), reverse=True)

    idcg_5 = _dcg_at_k(ideal_grades, TOP_K_5)
    idcg_10 = _dcg_at_k(ideal_grades, TOP_K_10)
    ndcg_5 = (_dcg_at_k(grades_10, TOP_K_5) / idcg_5) if idcg_5 > 0 else None
    ndcg_10 = (_dcg_at_k(grades_10, TOP_K_10) / idcg_10) if idcg_10 > 0 else None

    hits_5 = sum(1 for p in top5 if p in relevant_in_pool)
    hits_10 = sum(1 for p in top10 if p in relevant_in_pool)

    rr_10 = 0.0
    for rank, p in enumerate(top10, start=1):
        if p in relevant_in_pool:
            rr_10 = 1.0 / rank
            break

    returned_count = len(top10)
    returned_at_5 = len(top5)

    return {
        "rel_threshold": rel_threshold,
        "pooled_recall_denominator": n_rel,
        "returned_count": returned_count,
        "returned_at_5": returned_at_5,
        "missing_slots_at_5": TOP_K_5 - returned_at_5,
        "missing_slots_at_10": TOP_K_10 - returned_count,
        "is_short_list": returned_count < TOP_K_10,
        "unjudged_at_5": unjudged_at_5,
        "unjudged_at_10": unjudged_at_10,
        "precision_at_5": round(hits_5 / float(TOP_K_5), METRIC_DECIMALS),
        "precision_at_10": round(hits_10 / float(TOP_K_10), METRIC_DECIMALS),
        "pooled_recall_at_5": round(hits_5 / n_rel, METRIC_DECIMALS) if n_rel > 0 else None,
        "pooled_recall_at_10": round(hits_10 / n_rel, METRIC_DECIMALS) if n_rel > 0 else None,
        "mrr_at_10": round(rr_10, METRIC_DECIMALS) if n_rel > 0 else None,
        "ndcg_at_5": round(ndcg_5, METRIC_DECIMALS) if ndcg_5 is not None else None,
        "ndcg_at_10": round(ndcg_10, METRIC_DECIMALS) if ndcg_10 is not None else None,
        "max_grade_in_top10": max(grades_10) if grades_10 else None,
    }


def _summarize_metric_records(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compute descriptive summary stats (mean, median, min, max, n) across query records."""
    means: dict[str, float | None] = {}
    stats: dict[str, dict[str, float | int | None]] = {}
    for key in SUMMARY_METRIC_KEYS:
        vals = [float(r[key]) for r in records.values() if r.get(key) is not None]
        if vals:
            mean_val = round(sum(vals) / len(vals), METRIC_DECIMALS)
            means[key] = mean_val
            stats[key] = {
                "mean": mean_val,
                "median": round(float(median(vals)), METRIC_DECIMALS),
                "min": round(min(vals), METRIC_DECIMALS),
                "max": round(max(vals), METRIC_DECIMALS),
                "n_queries": len(vals),
            }
        else:
            means[key] = None
            stats[key] = {"mean": None, "median": None, "min": None, "max": None, "n_queries": 0}
    return {"macro_mean": means, "descriptive_stats": stats}


def _compute_fallback_split(
    per_query_strict: dict[str, dict[str, Any]],
    per_query_lenient: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Stratify answerable query metrics by fallback vs non-fallback execution."""
    fb_strict = {q: r for q, r in per_query_strict.items() if r["is_fallback"]}
    non_fb_strict = {q: r for q, r in per_query_strict.items() if not r["is_fallback"]}
    fb_lenient = {q: r for q, r in per_query_lenient.items() if r["is_fallback"]}
    non_fb_lenient = {q: r for q, r in per_query_lenient.items() if not r["is_fallback"]}

    return {
        "fallback_query_ids": sorted(fb_strict.keys()),
        "non_fallback_query_ids": sorted(non_fb_strict.keys()),
        "fallback_count": len(fb_strict),
        "non_fallback_count": len(non_fb_strict),
        "fallback_strict_mean": _summarize_metric_records(fb_strict)["macro_mean"],
        "non_fallback_strict_mean": _summarize_metric_records(non_fb_strict)["macro_mean"],
        "fallback_lenient_mean": _summarize_metric_records(fb_lenient)["macro_mean"],
        "non_fallback_lenient_mean": _summarize_metric_records(non_fb_lenient)["macro_mean"],
    }


def _compute_short_list_accounting(all_query_entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Account for returned list lengths and missing slots out of Top-5 and Top-10."""
    per_query_lengths: dict[str, int] = {}
    short_list_qids: list[str] = []
    missing_at_5 = 0
    missing_at_10 = 0
    total_returned = 0

    for entry in all_query_entries:
        qid = entry["query_id"]
        n_ret = min(len(entry["ranked_top10"]), TOP_K_10)
        per_query_lengths[qid] = n_ret
        total_returned += n_ret
        missing_at_5 += max(0, TOP_K_5 - min(n_ret, TOP_K_5))
        missing_at_10 += max(0, TOP_K_10 - n_ret)
        if n_ret < TOP_K_10:
            short_list_qids.append(qid)

    total_queries = len(all_query_entries)
    return {
        "total_queries": total_queries,
        "short_list_queries_count": len(short_list_qids),
        "short_list_query_ids": sorted(short_list_qids),
        "total_returned_slots_top10": total_returned,
        "total_possible_slots_top10": total_queries * TOP_K_10,
        "missing_slots_at_5": missing_at_5,
        "missing_slots_at_10": missing_at_10,
        "per_query_returned_count": per_query_lengths,
    }


def _compute_hop_comparison(systems_report: dict[str, Any]) -> dict[str, Any]:
    """Compute descriptive 1-hop vs 2-hop comparison on answerable queries."""
    if SYSTEM_REPAIRED_1HOP not in systems_report or SYSTEM_REPAIRED_2HOP not in systems_report:
        return {"available": False, "reason": "Repaired 1-hop or 2-hop system not present in rankings"}

    s1 = systems_report[SYSTEM_REPAIRED_1HOP]
    s2 = systems_report[SYSTEM_REPAIRED_2HOP]
    qids = sorted(set(s1["per_query_strict"].keys()) & set(s2["per_query_strict"].keys()))

    per_query_deltas: dict[str, Any] = {}
    for qid in qids:
        r1_s, r2_s = s1["per_query_strict"][qid], s2["per_query_strict"][qid]
        r1_l, r2_l = s1["per_query_lenient"][qid], s2["per_query_lenient"][qid]

        def _delta(a: float | None, b: float | None) -> float | None:
            if a is None or b is None:
                return None
            return round(b - a, METRIC_DECIMALS)

        per_query_deltas[qid] = {
            "hop_1_actual_hops": r1_s.get("actual_hop_count"),
            "hop_2_actual_hops": r2_s.get("actual_hop_count"),
            "is_fallback_1hop": r1_s["is_fallback"],
            "is_fallback_2hop": r2_s["is_fallback"],
            "strict_delta_2hop_minus_1hop": {k: _delta(r1_s[k], r2_s[k]) for k in SUMMARY_METRIC_KEYS},
            "lenient_delta_2hop_minus_1hop": {k: _delta(r1_l[k], r2_l[k]) for k in SUMMARY_METRIC_KEYS},
        }

    macro_strict_delta = {
        k: (
            round(s2["strict_summary"]["macro_mean"][k] - s1["strict_summary"]["macro_mean"][k], METRIC_DECIMALS)
            if s1["strict_summary"]["macro_mean"][k] is not None
            and s2["strict_summary"]["macro_mean"][k] is not None
            else None
        )
        for k in SUMMARY_METRIC_KEYS
    }
    macro_lenient_delta = {
        k: (
            round(s2["lenient_summary"]["macro_mean"][k] - s1["lenient_summary"]["macro_mean"][k], METRIC_DECIMALS)
            if s1["lenient_summary"]["macro_mean"][k] is not None
            and s2["lenient_summary"]["macro_mean"][k] is not None
            else None
        )
        for k in SUMMARY_METRIC_KEYS
    }

    return {
        "available": True,
        "one_hop_system": SYSTEM_REPAIRED_1HOP,
        "two_hop_system": SYSTEM_REPAIRED_2HOP,
        "baseline_one_hop_included": SYSTEM_BASELINE_1HOP in systems_report,
        "answerable_queries_compared": len(qids),
        "macro_strict_delta_2hop_minus_1hop": macro_strict_delta,
        "macro_lenient_delta_2hop_minus_1hop": macro_lenient_delta,
        "per_query_deltas": per_query_deltas,
    }


def compute_d1_evaluation(
    *,
    frozen_rankings_path: Path,
    gold_labels_path: Path,
    preflight: PreflightResult,
    authorization_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute complete read-only S5-D1 evaluation report from preflight-validated inputs."""
    if not preflight.passed:
        raise PreflightError("Cannot compute S5-D1 metrics when preflight validation has not passed.")

    gold = json.loads(gold_labels_path.read_text(encoding="utf-8"))
    frozen = json.loads(frozen_rankings_path.read_text(encoding="utf-8"))

    qrels_by_query: dict[str, dict[str, int]] = {}
    for row in gold["judgments"]:
        qrels_by_query.setdefault(row["query_id"], {})[row["passage_id"]] = int(row["final_grade"])

    verified_neg_set = set(preflight.verified_negative_controls)
    reclassified_ans_set = set(preflight.reclassified_answerable_controls)
    excluded_neg_set = set(preflight.excluded_negative_controls)

    systems_report: dict[str, Any] = {}
    answerable_qids_global: set[str] = set()

    for sys_name, sys_data in frozen["systems"].items():
        per_query_strict: dict[str, dict[str, Any]] = {}
        per_query_lenient: dict[str, dict[str, Any]] = {}
        neg_control_behavior: dict[str, dict[str, Any]] = {}
        excluded_behavior: dict[str, dict[str, Any]] = {}

        for q_entry in sys_data["queries"]:
            qid = q_entry["query_id"]
            ranked_pids = [item["passage_id"] for item in q_entry["ranked_top10"]]
            q_qrels = qrels_by_query[qid]
            meta = q_entry.get("meta", {})
            is_fb = bool(meta.get("is_fallback", False))
            actual_hops = meta.get("actual_hop_count", "N/A")

            m_strict = evaluate_query_ranking_extended(
                ranked_pids, q_qrels, rel_threshold=STRICT_REL_THRESHOLD
            )
            m_lenient = evaluate_query_ranking_extended(
                ranked_pids, q_qrels, rel_threshold=LENIENT_REL_THRESHOLD
            )
            for rec in (m_strict, m_lenient):
                rec["is_fallback"] = is_fb
                rec["actual_hop_count"] = actual_hops
                rec["reclassified_from_provisional_neg_control"] = qid in reclassified_ans_set

            if qid in verified_neg_set:
                neg_control_behavior[qid] = {
                    "classification": preflight.negative_control_classifications[qid],
                    "returned_count": len(ranked_pids),
                    "is_fallback": is_fb,
                    "actual_hop_count": actual_hops,
                    "max_grade_in_top10": m_strict["max_grade_in_top10"],
                    "any_grade_ge_1_in_top10": any(q_qrels[p] >= LENIENT_REL_THRESHOLD for p in ranked_pids),
                    "any_grade_eq_2_in_top10": any(q_qrels[p] >= STRICT_REL_THRESHOLD for p in ranked_pids),
                }
            elif qid in excluded_neg_set:
                excluded_behavior[qid] = {
                    "classification": preflight.negative_control_classifications[qid],
                    "returned_count": len(ranked_pids),
                    "is_fallback": is_fb,
                    "max_grade_in_top10": m_strict["max_grade_in_top10"],
                }
            else:
                answerable_qids_global.add(qid)
                per_query_strict[qid] = m_strict
                per_query_lenient[qid] = m_lenient

        systems_report[sys_name] = {
            "answerable_queries_count": len(per_query_strict),
            "verified_negative_controls_count": len(neg_control_behavior),
            "excluded_negative_controls_count": len(excluded_behavior),
            "strict_summary": _summarize_metric_records(per_query_strict),
            "lenient_summary": _summarize_metric_records(per_query_lenient),
            "fallback_analysis": _compute_fallback_split(per_query_strict, per_query_lenient),
            "short_list_accounting": _compute_short_list_accounting(sys_data["queries"]),
            "per_query_strict": per_query_strict,
            "per_query_lenient": per_query_lenient,
            "negative_control_behavior": neg_control_behavior,
            "excluded_negative_control_behavior": excluded_behavior,
        }

    return {
        "pipeline_name": "S5-D1 Read-Only Effectiveness Evaluation Pipeline",
        "is_synthetic": preflight.is_synthetic,
        "watermark": SYNTHETIC_BANNER if preflight.is_synthetic else None,
        "schema_mode": preflight.schema_mode,
        "pool_version": preflight.pool_version,
        "pool_sha256": preflight.pool_sha256,
        "rankings_sha256": preflight.rankings_sha256,
        "gold_labels_sha256": preflight.gold_labels_sha256,
        "neg_control_sha256": preflight.neg_control_sha256,
        "authorization": authorization_record,
        "metric_definitions": {
            "strict_threshold": f"grade == {STRICT_REL_THRESHOLD}",
            "lenient_threshold": f"grade >= {LENIENT_REL_THRESHOLD}",
            "pooled_recall_denominator": POOLED_RECALL_DENOMINATOR_DOC,
            "ndcg_gain_formula": "2**grade - 1 over raw adjudicated grades {0, 1, 2}, normalized by ideal pool DCG@K",
            "precision_denominator": f"Fixed K ({TOP_K_5} or {TOP_K_10}); short lists are reported explicitly.",
        },
        "query_stratification": {
            "answerable_queries": sorted(answerable_qids_global),
            "verified_negative_controls": sorted(verified_neg_set),
            "reclassified_as_answerable": sorted(reclassified_ans_set),
            "excluded_negative_controls": sorted(excluded_neg_set),
            "negative_control_classifications": preflight.negative_control_classifications,
        },
        "statistical_scope_disclaimer": (
            "Descriptive pilot metrics only (N=10 active queries). "
            "No statistical significance, superiority, or generalizable performance claims are authorized."
        ),
        "one_hop_vs_two_hop_comparison": _compute_hop_comparison(systems_report),
        "systems": systems_report,
    }
