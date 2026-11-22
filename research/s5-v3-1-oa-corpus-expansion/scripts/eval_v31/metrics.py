"""Versioned S5-v3.1 D1 evaluation engine (dynamic Top-K, strict/lenient, domain/fallback splits)."""

from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from eval_v31.constants import (
    BENCHMARK_VERSION_V31,
    LENIENT_REL_THRESHOLD,
    METRIC_DECIMALS,
    POOLED_RECALL_DENOMINATOR_DOC,
    STRICT_REL_THRESHOLD,
    SYNTHETIC_BANNER,
    SYSTEM_V31_1HOP,
    SYSTEM_V31_2HOP,
    TOP_K_5,
    TOP_K_10,
)
from eval_v31.preflight import V31PreflightError, V31PreflightResult

SUMMARY_METRICS_K5: tuple[str, ...] = (
    "precision_at_5",
    "pooled_recall_at_5",
    "mrr_at_5",
    "ndcg_at_5",
)
SUMMARY_METRICS_K10: tuple[str, ...] = (
    "precision_at_5",
    "precision_at_10",
    "pooled_recall_at_5",
    "pooled_recall_at_10",
    "mrr_at_10",
    "ndcg_at_5",
    "ndcg_at_10",
)


def _dcg_at_k(grades: list[int], k: int) -> float:
    total = 0.0
    for rank, grade in enumerate(grades[:k], start=1):
        gain = (2**grade) - 1
        total += gain / math.log2(rank + 1)
    return total


def evaluate_v31_query_ranking(
    ranked_passage_ids: list[str],
    query_qrels: dict[str, int],
    *,
    pool_depth_k: int,
    rel_threshold: int,
) -> dict[str, Any]:
    """Compute exact IR metrics at pool_depth_k (5 or 10) without zero-imputing unjudged hits."""
    top_k = ranked_passage_ids[:pool_depth_k]
    unjudged_at_k = sum(1 for p in top_k if p not in query_qrels)
    if unjudged_at_k > 0:
        raise V31PreflightError(
            f"Encountered {unjudged_at_k} unjudged passage(s) in Top-{pool_depth_k}; "
            "unjudged passages are never silently treated as irrelevant."
        )

    top5 = ranked_passage_ids[:TOP_K_5]
    relevant_in_pool = {p for p, g in query_qrels.items() if g >= rel_threshold}
    n_rel = len(relevant_in_pool)

    grades_5 = [query_qrels[p] for p in top5]
    ideal_grades = sorted(query_qrels.values(), reverse=True)
    idcg_5 = _dcg_at_k(ideal_grades, TOP_K_5)
    ndcg_5 = (_dcg_at_k(grades_5, TOP_K_5) / idcg_5) if idcg_5 > 0 else None
    hits_5 = sum(1 for p in top5 if p in relevant_in_pool)

    rr_5 = 0.0
    for rank, p in enumerate(top5, start=1):
        if p in relevant_in_pool:
            rr_5 = 1.0 / rank
            break

    rec: dict[str, Any] = {
        "pool_depth_k": pool_depth_k,
        "rel_threshold": rel_threshold,
        "pooled_recall_denominator": n_rel,
        "returned_at_5": len(top5),
        "returned_at_k": len(top_k),
        "missing_slots_at_5": TOP_K_5 - len(top5),
        "missing_slots_at_k": pool_depth_k - len(top_k),
        "is_short_list_at_k": len(top_k) < pool_depth_k,
        "unjudged_at_k": unjudged_at_k,
        "precision_at_5": round(hits_5 / float(TOP_K_5), METRIC_DECIMALS),
        "pooled_recall_at_5": round(hits_5 / n_rel, METRIC_DECIMALS) if n_rel > 0 else None,
        "mrr_at_5": round(rr_5, METRIC_DECIMALS) if n_rel > 0 else None,
        "ndcg_at_5": round(ndcg_5, METRIC_DECIMALS) if ndcg_5 is not None else None,
        "precision_at_10": None,
        "pooled_recall_at_10": None,
        "mrr_at_10": None,
        "ndcg_at_10": None,
        "max_grade_in_topk": max((query_qrels[p] for p in top_k), default=None),
    }

    if pool_depth_k >= TOP_K_10:
        top10 = ranked_passage_ids[:TOP_K_10]
        grades_10 = [query_qrels[p] for p in top10]
        idcg_10 = _dcg_at_k(ideal_grades, TOP_K_10)
        ndcg_10 = (_dcg_at_k(grades_10, TOP_K_10) / idcg_10) if idcg_10 > 0 else None
        hits_10 = sum(1 for p in top10 if p in relevant_in_pool)
        rr_10 = 0.0
        for rank, p in enumerate(top10, start=1):
            if p in relevant_in_pool:
                rr_10 = 1.0 / rank
                break
        rec["precision_at_10"] = round(hits_10 / float(TOP_K_10), METRIC_DECIMALS)
        rec["pooled_recall_at_10"] = round(hits_10 / n_rel, METRIC_DECIMALS) if n_rel > 0 else None
        rec["mrr_at_10"] = round(rr_10, METRIC_DECIMALS) if n_rel > 0 else None
        rec["ndcg_at_10"] = round(ndcg_10, METRIC_DECIMALS) if ndcg_10 is not None else None

    return rec


def _summarize(records: dict[str, dict[str, Any]], metric_keys: tuple[str, ...]) -> dict[str, Any]:
    means: dict[str, float | None] = {}
    stats: dict[str, dict[str, float | int | None]] = {}
    for key in metric_keys:
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


def compute_v31_d1_evaluation(
    *,
    gold_labels_path: Path,
    retrieval_diagnostics_path: Path,
    preflight: V31PreflightResult,
    query_manifest_path: Path | None = None,
    authorization_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute full S5-v3.1 D1 evaluation report from preflight-validated inputs."""
    if not preflight.passed:
        raise V31PreflightError("Cannot compute S5-v3.1 D1 metrics when preflight has not passed.")

    gold = json.loads(gold_labels_path.read_text(encoding="utf-8"))
    diag = json.loads(retrieval_diagnostics_path.read_text(encoding="utf-8"))
    cfg = gold["benchmark_config"]
    depth_k = int(cfg["pool_depth_k"])
    approved_qids = list(cfg["approved_query_ids"])
    metric_keys = SUMMARY_METRICS_K10 if depth_k >= TOP_K_10 else SUMMARY_METRICS_K5

    domain_by_qid: dict[str, str] = {}
    if query_manifest_path is not None and query_manifest_path.exists():
        qm = json.loads(query_manifest_path.read_text(encoding="utf-8"))
        for row in qm.get("queries") or []:
            qid = str(row["query_id"])
            domain_by_qid[qid] = str(row.get("domain") or row.get("primary_domain") or "unspecified")

    qrels_by_qid: dict[str, dict[str, int]] = {}
    for row in gold["judgments"]:
        qrels_by_qid.setdefault(str(row["query_id"]), {})[str(row["passage_id"])] = int(
            row["final_grade"]
        )

    verified_ncs = set(preflight.verified_negative_controls)
    reclassified_ncs = set(preflight.reclassified_answerable_controls)
    excluded_ncs = set(preflight.excluded_negative_controls)

    systems_report: dict[str, Any] = {}
    answerable_qids_global: set[str] = set()

    for sys_name in sorted(cfg["system_hashes"].keys()):
        vdata = diag["variants"][sys_name]
        by_qid = {str(e["query_id"]): e for e in vdata["per_query_diagnostics"]}

        per_q_strict: dict[str, dict[str, Any]] = {}
        per_q_lenient: dict[str, dict[str, Any]] = {}
        nc_behavior: dict[str, dict[str, Any]] = {}
        excluded_behavior: dict[str, dict[str, Any]] = {}

        for qid in approved_qids:
            q_entry = by_qid[qid]
            ranked_pids = [str(r["passage_id"]) for r in q_entry["results"]]
            prov = q_entry.get("provenance") or {}
            is_fb = bool(prov.get("fallback_triggered", False))
            obs_hops = int(prov.get("observed_hop_depth", 0))
            dom = domain_by_qid.get(qid, "unspecified")
            q_qrels = qrels_by_qid[qid]

            m_strict = evaluate_v31_query_ranking(
                ranked_pids, q_qrels, pool_depth_k=depth_k, rel_threshold=STRICT_REL_THRESHOLD
            )
            m_lenient = evaluate_v31_query_ranking(
                ranked_pids, q_qrels, pool_depth_k=depth_k, rel_threshold=LENIENT_REL_THRESHOLD
            )
            for rec in (m_strict, m_lenient):
                rec["domain"] = dom
                rec["is_fallback"] = is_fb
                rec["observed_hop_depth"] = obs_hops
                rec["reclassified_from_nc"] = qid in reclassified_ncs

            if qid in verified_ncs:
                nc_behavior[qid] = {
                    "classification": preflight.nc_classifications[qid],
                    "returned_at_k": len(ranked_pids[:depth_k]),
                    "is_fallback": is_fb,
                    "observed_hop_depth": obs_hops,
                    "max_grade_in_topk": m_strict["max_grade_in_topk"],
                    "any_grade_ge_1": any(
                        q_qrels[p] >= LENIENT_REL_THRESHOLD for p in ranked_pids[:depth_k]
                    ),
                    "any_grade_eq_2": any(
                        q_qrels[p] >= STRICT_REL_THRESHOLD for p in ranked_pids[:depth_k]
                    ),
                }
            elif qid in excluded_ncs:
                excluded_behavior[qid] = {
                    "classification": preflight.nc_classifications[qid],
                    "returned_at_k": len(ranked_pids[:depth_k]),
                    "is_fallback": is_fb,
                    "max_grade_in_topk": m_strict["max_grade_in_topk"],
                }
            else:
                per_q_strict[qid] = m_strict
                per_q_lenient[qid] = m_lenient
                answerable_qids_global.add(qid)

        # Domain-level stratification
        strict_by_dom: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        lenient_by_dom: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for qid, rec in per_q_strict.items():
            strict_by_dom[rec["domain"]][qid] = rec
            lenient_by_dom[rec["domain"]][qid] = per_q_lenient[qid]

        domain_breakdown = {
            dom: {
                "query_count": len(strict_by_dom[dom]),
                "strict_macro_mean": _summarize(strict_by_dom[dom], metric_keys)["macro_mean"],
                "lenient_macro_mean": _summarize(lenient_by_dom[dom], metric_keys)["macro_mean"],
            }
            for dom in sorted(strict_by_dom)
        }

        # Fallback vs non-fallback stratification
        fb_strict = {q: r for q, r in per_q_strict.items() if r["is_fallback"]}
        non_fb_strict = {q: r for q, r in per_q_strict.items() if not r["is_fallback"]}
        fb_lenient = {q: r for q, r in per_q_lenient.items() if r["is_fallback"]}
        non_fb_lenient = {q: r for q, r in per_q_lenient.items() if not r["is_fallback"]}

        systems_report[sys_name] = {
            "config_sha256": cfg["system_hashes"][sys_name],
            "answerable_query_count": len(per_q_strict),
            "verified_negative_control_count": len(nc_behavior),
            "excluded_negative_control_count": len(excluded_behavior),
            "strict_summary": _summarize(per_q_strict, metric_keys),
            "lenient_summary": _summarize(per_q_lenient, metric_keys),
            "domain_breakdown": domain_breakdown,
            "fallback_stratification": {
                "fallback_count": len(fb_strict),
                "non_fallback_count": len(non_fb_strict),
                "fallback_query_ids": sorted(fb_strict),
                "non_fallback_query_ids": sorted(non_fb_strict),
                "fallback_strict_mean": _summarize(fb_strict, metric_keys)["macro_mean"],
                "non_fallback_strict_mean": _summarize(non_fb_strict, metric_keys)["macro_mean"],
                "fallback_lenient_mean": _summarize(fb_lenient, metric_keys)["macro_mean"],
                "non_fallback_lenient_mean": _summarize(non_fb_lenient, metric_keys)["macro_mean"],
            },
            "per_query_strict": per_q_strict,
            "per_query_lenient": per_q_lenient,
            "negative_control_behavior": nc_behavior,
            "excluded_negative_control_behavior": excluded_behavior,
        }

    # 1-hop vs 2-hop descriptive comparison
    hop_comparison: dict[str, Any] = {"available": False}
    if SYSTEM_V31_1HOP in systems_report and SYSTEM_V31_2HOP in systems_report:
        s1 = systems_report[SYSTEM_V31_1HOP]
        s2 = systems_report[SYSTEM_V31_2HOP]
        hop_comparison = {
            "available": True,
            "one_hop_system": SYSTEM_V31_1HOP,
            "two_hop_system": SYSTEM_V31_2HOP,
            "macro_strict_delta_2hop_minus_1hop": {
                k: (
                    round(
                        s2["strict_summary"]["macro_mean"][k] - s1["strict_summary"]["macro_mean"][k],
                        METRIC_DECIMALS,
                    )
                    if s1["strict_summary"]["macro_mean"][k] is not None
                    and s2["strict_summary"]["macro_mean"][k] is not None
                    else None
                )
                for k in metric_keys
            },
            "macro_lenient_delta_2hop_minus_1hop": {
                k: (
                    round(
                        s2["lenient_summary"]["macro_mean"][k]
                        - s1["lenient_summary"]["macro_mean"][k],
                        METRIC_DECIMALS,
                    )
                    if s1["lenient_summary"]["macro_mean"][k] is not None
                    and s2["lenient_summary"]["macro_mean"][k] is not None
                    else None
                )
                for k in metric_keys
            },
        }

    return {
        "schema_version": "s5v31_d1_evaluation_report_v1",
        "benchmark_version": BENCHMARK_VERSION_V31,
        "is_synthetic": preflight.is_synthetic,
        "synthetic_watermark": SYNTHETIC_BANNER if preflight.is_synthetic else None,
        "split": preflight.split,
        "pool_depth_k": depth_k,
        "active_metric_keys": list(metric_keys),
        "pooled_recall_denominator_definition": POOLED_RECALL_DENOMINATOR_DOC,
        "expected_hashes": dict(preflight.expected_hashes),
        "authorization_verified": authorization_record is not None,
        "answerable_query_ids": sorted(answerable_qids_global),
        "verified_negative_controls": sorted(verified_ncs),
        "reclassified_answerable_controls": sorted(reclassified_ncs),
        "excluded_negative_controls": sorted(excluded_ncs),
        "nc_classifications": dict(preflight.nc_classifications),
        "hop_comparison": hop_comparison,
        "systems": systems_report,
    }
