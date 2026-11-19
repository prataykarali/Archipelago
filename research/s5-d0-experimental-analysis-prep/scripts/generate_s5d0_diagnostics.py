"""S5-D0 — Read-Only Six-System Technical Diagnostics & Preservation Verifier.

Reads ONLY frozen S5-B1.1, S5-B2.1, and S5-C2 artifacts without modifying any
corpus, model, retrieval output, annotation pool, or reviewer submission.

Does NOT compute relevance-based retrieval effectiveness metrics (Recall@k, MRR,
nDCG@k, Precision@k) and does NOT read or resolve reviewer grades.

Outputs:
- research/s5-d0-experimental-analysis-prep/reports/s5d0_preservation_manifest.json
- research/s5-d0-experimental-analysis-prep/reports/s5d0_technical_diagnostics.json
"""

from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "research" / "s5-d0-experimental-analysis-prep" / "reports"

SYSTEM_ORDER = [
    "bm25",
    "dense_snowflake_arctic_768d",
    "hybrid_rrf_e2e",
    "baseline_graph_1hop",
    "repaired_graph_1hop_ablation",
    "repaired_graph_2hop_full",
]

# Expected SHA-256 hashes recorded in S5B2_1_FINAL_RELEASE_CHECK.md and s5c2_audit_summary.json
EXPECTED_HASHES: dict[str, str] = {
    "research/s5-b2-benchmark-correction/corpus/s5b2_proposed_blinded_query_specs.json": "011025237209a5432409e7998c350f5c2c4970cf7f9f96c79ff938e2b729af8a",
    "research/s5-b2-benchmark-correction/proposed_package_v2_1/retrieval_query_candidate_pool_blinded.csv": "4c9cb0e58f9f6d32c59eb12804f032be32a6a52c1eeb75055fb5148600f9acd7",
    "research/s5-b2-benchmark-correction/proposed_package_v2_1/retrieval_query_pool_blinded.json": "2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037",
    "research/s5-b2-benchmark-correction/proposed_package_v2_1/RETRIEVAL_ANNOTATION_PROTOCOL.md": "35a7bc0168431b355f49dc100364493b0ef69d5ff680e3308ca5dcb44dcc46e9",
    "research/s5-b2-benchmark-correction/reports/s5b2_negative_control_audit.json": "02e143bfd7b8114ad9652c102248daef36464f521f5b0b3ec1d8b3c4e91199d6",
    "research/s5-b2-benchmark-correction/reports/s5b2_1_passage_necessity_matrix.json": "cc72beff79bcd446401a65b7ed57854f9e82dccca685585a16e79c3bda464921",
    "research/s5-b2-benchmark-correction/reports/s5b2_1_corpus_provenance_registry.json": "e537f4a42b2f89f63a7d640a7f9f796e951b535dec9eb690ca361bcd49fa81fc",
    "research/s5-b2-benchmark-correction/reports/s5b2_1_frozen_ranked_results.json": "e20a9f64272c1afa42d62ea7474cb3d9db8e9472c5cf97b639f680e4942eba86",
    "research/s5-b2-benchmark-correction/reports/s5b2_1_topk_pool_coverage_refreshed.json": "04be54f0574c55ca95d86a95135eba96c6db143cf7185c362e4115f1272d1958",
    "research/s5-b2-benchmark-correction/S5B2_1_APPROVAL_GATE_REPORT.md": "3250006a650c93675eb1dc96e4df1d07048a5370443e4365529a9fad8ad8db4b",
    "data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md": "70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c",
    "data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md": "ca3e6af86c72c20bf6dbd66d71f3c5c79ef7795de5d149d23c0b918304ae80f4",
}

ADDITIONAL_PRESERVED_PATHS: list[str] = [
    "research/s5-b1-integrity-repair/corpus/s5b1_corpus_manifest.json",
    "research/s5-b1-integrity-repair/models/s5b1_model_manifest.json",
    "research/s5-b1-integrity-repair/reports/retrieval_timing_report.json",
    "research/s5-b1-integrity-repair/reports/retrieval_technical_evaluation_report.json",
    "research/s5-b1-integrity-repair/reports/graph_information_access_audit.json",
    "research/s5-c2-annotation-audit/reports/s5c2_audit_summary.json",
    "research/s5-c2-annotation-audit/reports/S5C2_ANNOTATION_VALIDATION_REPORT.md",
    "research/s5-c2-annotation-audit/reports/S5C2_INTER_ANNOTATOR_AGREEMENT.md",
    "research/s5-c2-annotation-audit/reports/S5C2_NEGATIVE_CONTROL_VERIFICATION.md",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_preserved_artifacts(root: Path = ROOT) -> dict[str, Any]:
    """Verify integrity of all preserved frozen artifacts and local originals."""
    records: list[dict[str, Any]] = []
    mismatches: list[str] = []

    all_paths = list(EXPECTED_HASHES.keys()) + ADDITIONAL_PRESERVED_PATHS
    for rel_path in all_paths:
        full_path = root / rel_path
        is_local = rel_path.startswith("data/annotation_local/")
        expected = EXPECTED_HASHES.get(rel_path)

        if not full_path.exists():
            status = "MISSING_LOCAL_GITIGNORED" if is_local else "MISSING_REQUIRED"
            if not is_local:
                mismatches.append(f"{rel_path}: {status}")
            records.append(
                {
                    "path": rel_path,
                    "scope": "local_gitignored" if is_local else "tracked_frozen",
                    "exists": False,
                    "byte_size": None,
                    "actual_sha256": None,
                    "expected_sha256": expected,
                    "status": status,
                }
            )
            continue

        actual = sha256_file(full_path)
        if expected is not None:
            if actual == expected:
                status = "VERIFIED_EXACT_MATCH"
            else:
                status = "HASH_MISMATCH"
                mismatches.append(f"{rel_path}: expected {expected}, got {actual}")
        else:
            status = "RECORDED_UNMODIFIED"

        records.append(
            {
                "path": rel_path,
                "scope": "local_gitignored" if is_local else "tracked_frozen",
                "exists": True,
                "byte_size": full_path.stat().st_size,
                "actual_sha256": actual,
                "expected_sha256": expected,
                "status": status,
            }
        )

    return {
        "manifest_name": "S5-D0 Frozen Artifact Preservation Manifest",
        "base_commit": "6450585f60b3c1bea7bef2f411458800552cea0b",
        "total_artifacts_checked": len(records),
        "verified_exact_matches": sum(1 for r in records if r["status"] == "VERIFIED_EXACT_MATCH"),
        "recorded_unmodified": sum(1 for r in records if r["status"] == "RECORDED_UNMODIFIED"),
        "mismatches": mismatches,
        "all_checks_passed": len(mismatches) == 0,
        "artifacts": records,
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def compute_diagnostics(root: Path = ROOT) -> dict[str, Any]:
    """Compute reproducible six-system technical diagnostics from frozen JSON artifacts."""
    frozen_path = root / "research" / "s5-b2-benchmark-correction" / "reports" / "s5b2_1_frozen_ranked_results.json"
    pool_path = root / "research" / "s5-b2-benchmark-correction" / "proposed_package_v2_1" / "retrieval_query_pool_blinded.json"
    specs_path = root / "research" / "s5-b2-benchmark-correction" / "corpus" / "s5b2_proposed_blinded_query_specs.json"
    timing_path = root / "research" / "s5-b1-integrity-repair" / "reports" / "retrieval_timing_report.json"
    s5b1_tech_path = root / "research" / "s5-b1-integrity-repair" / "reports" / "retrieval_technical_evaluation_report.json"

    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    specs = json.loads(specs_path.read_text(encoding="utf-8"))
    timing_s5b1 = json.loads(timing_path.read_text(encoding="utf-8"))
    tech_s5b1 = json.loads(s5b1_tech_path.read_text(encoding="utf-8"))

    # Map query metadata
    query_meta: dict[str, dict[str, Any]] = {}
    for q in specs["queries"]:
        query_meta[q["query_id"]] = {
            "legacy_query_id": q["legacy_query_id"],
            "domain": q["domain"],
            "query_text": q["query_text"],
            "investigator_seed_candidates": sorted(q["candidate_passage_ids"]),
        }
    query_ids = [q["query_id"] for q in specs["queries"]]

    # Map pooled pairs by query
    pool_by_query: dict[str, set[str]] = {}
    for q in pool["queries"]:
        pool_by_query[q["query_id"]] = {c["candidate_passage_id"] for c in q["candidates"]}

    # Index system outputs: sys_q[sys_name][qid] = query entry
    sys_q: dict[str, dict[str, dict[str, Any]]] = {}
    for sys_name in SYSTEM_ORDER:
        sys_q[sys_name] = {q["query_id"]: q for q in frozen["systems"][sys_name]["queries"]}

    # -----------------------------------------------------------------------
    # 1. Retrieval-Result Overlap Across Systems
    # -----------------------------------------------------------------------
    overlap_top5_jaccard: dict[str, dict[str, float]] = {s: {} for s in SYSTEM_ORDER}
    overlap_top10_jaccard: dict[str, dict[str, float]] = {s: {} for s in SYSTEM_ORDER}
    overlap_top5_shared_mean: dict[str, dict[str, float]] = {s: {} for s in SYSTEM_ORDER}
    overlap_top10_shared_mean: dict[str, dict[str, float]] = {s: {} for s in SYSTEM_ORDER}
    rank1_exact_agreement: dict[str, dict[str, int]] = {s: {} for s in SYSTEM_ORDER}

    for s1 in SYSTEM_ORDER:
        for s2 in SYSTEM_ORDER:
            j5_vals, j10_vals, c5_vals, c10_vals = [], [], [], []
            r1_matches = 0
            for qid in query_ids:
                r1 = [item["passage_id"] for item in sys_q[s1][qid]["ranked_top10"]]
                r2 = [item["passage_id"] for item in sys_q[s2][qid]["ranked_top10"]]
                set1_5, set2_5 = set(r1[:5]), set(r2[:5])
                set1_10, set2_10 = set(r1[:10]), set(r2[:10])
                j5_vals.append(_jaccard(set1_5, set2_5))
                j10_vals.append(_jaccard(set1_10, set2_10))
                c5_vals.append(len(set1_5 & set2_5))
                c10_vals.append(len(set1_10 & set2_10))
                if r1 and r2 and r1[0] == r2[0]:
                    r1_matches += 1
            overlap_top5_jaccard[s1][s2] = round(sum(j5_vals) / len(query_ids), 4)
            overlap_top10_jaccard[s1][s2] = round(sum(j10_vals) / len(query_ids), 4)
            overlap_top5_shared_mean[s1][s2] = round(sum(c5_vals) / len(query_ids), 2)
            overlap_top10_shared_mean[s1][s2] = round(sum(c10_vals) / len(query_ids), 2)
            rank1_exact_agreement[s1][s2] = r1_matches

    # Non-fallback overlap between graph systems and bm25
    non_fallback_overlap_with_bm25: dict[str, dict[str, Any]] = {}
    for gsys in ["baseline_graph_1hop", "repaired_graph_1hop_ablation", "repaired_graph_2hop_full"]:
        nf_qids = [qid for qid in query_ids if not sys_q[gsys][qid]["meta"].get("is_fallback", False)]
        j10_nf = []
        c10_nf = []
        for qid in nf_qids:
            g_set = {item["passage_id"] for item in sys_q[gsys][qid]["ranked_top10"]}
            b_set = {item["passage_id"] for item in sys_q["bm25"][qid]["ranked_top10"]}
            j10_nf.append(_jaccard(g_set, b_set))
            c10_nf.append(len(g_set & b_set))
        non_fallback_overlap_with_bm25[gsys] = {
            "non_fallback_queries": nf_qids,
            "non_fallback_count": len(nf_qids),
            "mean_top10_jaccard_with_bm25": round(sum(j10_nf) / len(nf_qids), 4) if nf_qids else None,
            "mean_top10_shared_with_bm25": round(sum(c10_nf) / len(nf_qids), 2) if nf_qids else None,
        }

    # Exclusive passages per system across all 10 queries (query_id, passage_id) pairs
    pair_to_systems: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for sys_name in SYSTEM_ORDER:
        for qid in query_ids:
            for item in sys_q[sys_name][qid]["ranked_top10"]:
                pair_to_systems[(qid, item["passage_id"])].append(sys_name)

    system_exclusivity: dict[str, dict[str, int]] = {}
    for sys_name in SYSTEM_ORDER:
        total_ret = sum(len(sys_q[sys_name][qid]["ranked_top10"]) for qid in query_ids)
        excl = sum(1 for pair, syss in pair_to_systems.items() if syss == [sys_name])
        shared = total_ret - excl
        system_exclusivity[sys_name] = {
            "total_retrieved_top10_pairs": total_ret,
            "exclusive_to_system": excl,
            "shared_with_at_least_one_other": shared,
        }

    # -----------------------------------------------------------------------
    # 2. Graph 1-Hop vs 2-Hop Retrieval Behavior
    # -----------------------------------------------------------------------
    graph_1hop_vs_2hop_per_query: list[dict[str, Any]] = []
    for qid in query_ids:
        b1 = sys_q["baseline_graph_1hop"][qid]
        r1 = sys_q["repaired_graph_1hop_ablation"][qid]
        r2 = sys_q["repaired_graph_2hop_full"][qid]

        r1_pids = [x["passage_id"] for x in r1["ranked_top10"]]
        r2_pids = [x["passage_id"] for x in r2["ranked_top10"]]
        r1_set, r2_set = set(r1_pids), set(r2_pids)

        r1_paths = r1["meta"].get("paths_traversed", [])
        r2_paths = r2["meta"].get("paths_traversed", [])
        r2_hop1_paths = sum(1 for p in r2_paths if p.get("hop") == 1)
        r2_hop2_paths = sum(1 for p in r2_paths if p.get("hop") == 2)

        rank_changes: list[dict[str, Any]] = []
        for idx1, pid in enumerate(r1_pids, start=1):
            if pid in r2_set:
                idx2 = r2_pids.index(pid) + 1
                if idx1 != idx2:
                    rank_changes.append({"passage_id": pid, "rank_1hop": idx1, "rank_2hop": idx2, "delta": idx1 - idx2})

        graph_1hop_vs_2hop_per_query.append(
            {
                "query_id": qid,
                "domain": query_meta[qid]["domain"],
                "baseline_1hop": {
                    "returned_count": len(b1["ranked_top10"]),
                    "is_fallback": b1["meta"].get("is_fallback"),
                    "matched_anchors": b1["meta"].get("matched_anchors", []),
                    "traversed_concepts_count": b1["meta"].get("traversed_concepts_count", 0),
                    "actual_hop_count": b1["meta"].get("actual_hop_count", 0),
                    "paths_traversed_count": len(b1["meta"].get("paths_traversed", [])),
                    "traversal_errors_count": len(b1["meta"].get("traversal_errors", [])),
                },
                "repaired_1hop": {
                    "returned_count": len(r1["ranked_top10"]),
                    "is_fallback": r1["meta"].get("is_fallback"),
                    "matched_anchors": r1["meta"].get("matched_anchors", []),
                    "traversed_concepts_count": r1["meta"].get("traversed_concepts_count", 0),
                    "actual_hop_count": r1["meta"].get("actual_hop_count", 0),
                    "paths_traversed_count": len(r1_paths),
                },
                "repaired_2hop": {
                    "returned_count": len(r2["ranked_top10"]),
                    "is_fallback": r2["meta"].get("is_fallback"),
                    "matched_anchors": r2["meta"].get("matched_anchors", []),
                    "traversed_concepts_count": r2["meta"].get("traversed_concepts_count", 0),
                    "actual_hop_count": r2["meta"].get("actual_hop_count", 0),
                    "paths_traversed_count": len(r2_paths),
                    "hop1_paths_count": r2_hop1_paths,
                    "hop2_paths_count": r2_hop2_paths,
                },
                "repaired_1hop_vs_2hop_diff": {
                    "exact_top10_order_identical": r1_pids == r2_pids,
                    "top5_jaccard": round(_jaccard(set(r1_pids[:5]), set(r2_pids[:5])), 4),
                    "top10_jaccard": round(_jaccard(r1_set, r2_set), 4),
                    "added_by_2hop_in_top10": sorted(r2_set - r1_set),
                    "dropped_by_2hop_from_top10": sorted(r1_set - r2_set),
                    "shared_rank_changes_count": len(rank_changes),
                    "shared_rank_changes": rank_changes,
                },
            }
        )

    # -----------------------------------------------------------------------
    # 3. BM25 Fallback Frequency and Trigger Reasons
    # -----------------------------------------------------------------------
    fallback_summary: dict[str, Any] = {}
    for sys_name in SYSTEM_ORDER:
        fb_events: list[dict[str, Any]] = []
        for qid in query_ids:
            q_entry = sys_q[sys_name][qid]
            meta = q_entry["meta"]
            if meta.get("is_fallback", False):
                bm25_pids = [x["passage_id"] for x in sys_q["bm25"][qid]["ranked_top10"]]
                sys_pids = [x["passage_id"] for x in q_entry["ranked_top10"]]
                bm25_scores = [x["score"] for x in sys_q["bm25"][qid]["ranked_top10"]]
                sys_scores = [x["score"] for x in q_entry["ranked_top10"]]
                fb_events.append(
                    {
                        "query_id": qid,
                        "domain": query_meta[qid]["domain"],
                        "anchor_found": meta.get("anchor_found"),
                        "matched_anchors": meta.get("matched_anchors", []),
                        "fallback_strategy": meta.get("fallback_strategy"),
                        "trigger_reason": "ZERO_ANCHOR_MATCH_IN_CONCEPT_INDEX"
                        if not meta.get("anchor_found")
                        else "OTHER",
                        "exact_bm25_top10_match": (sys_pids == bm25_pids and sys_scores == bm25_scores),
                    }
                )
        fallback_summary[sys_name] = {
            "fallback_count": len(fb_events),
            "total_queries": len(query_ids),
            "fallback_rate": round(len(fb_events) / len(query_ids), 4),
            "events": fb_events,
        }

    # -----------------------------------------------------------------------
    # 4. Query-Level Retrieval Coverage and Missing Results
    # -----------------------------------------------------------------------
    query_coverage: list[dict[str, Any]] = []
    total_missing_slots_by_system: dict[str, int] = {s: 0 for s in SYSTEM_ORDER}

    for qid in query_ids:
        per_sys_counts: dict[str, int] = {}
        union_retrieved: set[str] = set()
        for sys_name in SYSTEM_ORDER:
            ranked = sys_q[sys_name][qid]["ranked_top10"]
            per_sys_counts[sys_name] = len(ranked)
            total_missing_slots_by_system[sys_name] += max(0, 10 - len(ranked))
            for item in ranked:
                union_retrieved.add(item["passage_id"])

        pooled_set = pool_by_query[qid]
        seed_set = set(query_meta[qid]["investigator_seed_candidates"])
        retrieved_not_in_pool = sorted(union_retrieved - pooled_set)
        pool_only_from_seeds = sorted(pooled_set - union_retrieved)

        query_coverage.append(
            {
                "query_id": qid,
                "legacy_query_id": query_meta[qid]["legacy_query_id"],
                "domain": query_meta[qid]["domain"],
                "returned_counts_by_system": per_sys_counts,
                "systems_with_shortfall_lt_10": [s for s, c in per_sys_counts.items() if c < 10],
                "unique_retrieved_union_top10": len(union_retrieved),
                "pooled_pairs_count": len(pooled_set),
                "investigator_seed_candidates_count": len(seed_set),
                "seed_candidates_not_in_any_top10": pool_only_from_seeds,
                "retrieved_top10_not_in_pool": retrieved_not_in_pool,
            }
        )

    # -----------------------------------------------------------------------
    # 5. Existing Measured Latency and Runtime Diagnostics
    # -----------------------------------------------------------------------
    # From S5-B1.1 (12-query timing benchmark, 5 warm repetitions)
    # Plus hybrid_rrf_e2e single-pass timing_breakdown recorded in S5-B2.1 (10 active queries)
    hybrid_s5b2_breakdowns: list[dict[str, Any]] = []
    for qid in query_ids:
        tb = sys_q["hybrid_rrf_e2e"][qid]["meta"].get("timing_breakdown", {})
        hybrid_s5b2_breakdowns.append({"query_id": qid, **tb})

    s5b1_per_query_warm: dict[str, dict[str, float]] = {}
    for sys_name in SYSTEM_ORDER:
        s5b1_per_query_warm[sys_name] = {
            qr["query_id"]: qr["warm_latency_mean_ms"]
            for qr in tech_s5b1["systems"][sys_name]["query_results"]
        }

    return {
        "report_name": "S5-D0 Reproducible Six-System Technical Diagnostics (Pre-Gold-Label)",
        "base_commit": "6450585f60b3c1bea7bef2f411458800552cea0b",
        "active_queries_count": len(query_ids),
        "total_pooled_pairs": pool["total_candidate_pairs"],
        "relevance_metrics_computed": False,
        "overlap_diagnostics": {
            "top5_mean_jaccard": overlap_top5_jaccard,
            "top10_mean_jaccard": overlap_top10_jaccard,
            "top5_mean_shared_count": overlap_top5_shared_mean,
            "top10_mean_shared_count": overlap_top10_shared_mean,
            "rank1_exact_agreement_out_of_10": rank1_exact_agreement,
            "non_fallback_overlap_with_bm25": non_fallback_overlap_with_bm25,
            "system_exclusivity_top10": system_exclusivity,
        },
        "graph_1hop_vs_2hop_diagnostics": {
            "per_query": graph_1hop_vs_2hop_per_query,
            "summary": {
                "repaired_1hop_total_paths": sum(
                    x["repaired_1hop"]["paths_traversed_count"] for x in graph_1hop_vs_2hop_per_query
                ),
                "repaired_2hop_total_paths": sum(
                    x["repaired_2hop"]["paths_traversed_count"] for x in graph_1hop_vs_2hop_per_query
                ),
                "repaired_2hop_hop1_paths": sum(
                    x["repaired_2hop"]["hop1_paths_count"] for x in graph_1hop_vs_2hop_per_query
                ),
                "repaired_2hop_hop2_paths": sum(
                    x["repaired_2hop"]["hop2_paths_count"] for x in graph_1hop_vs_2hop_per_query
                ),
                "baseline_1hop_total_paths": sum(
                    x["baseline_1hop"]["paths_traversed_count"] for x in graph_1hop_vs_2hop_per_query
                ),
                "queries_with_observed_2hop_depth": [
                    x["query_id"]
                    for x in graph_1hop_vs_2hop_per_query
                    if x["repaired_2hop"]["actual_hop_count"] == 2
                ],
                "queries_where_2hop_changed_top10_order": [
                    x["query_id"]
                    for x in graph_1hop_vs_2hop_per_query
                    if not x["repaired_1hop_vs_2hop_diff"]["exact_top10_order_identical"]
                ],
                "queries_where_2hop_changed_top10_set": [
                    x["query_id"]
                    for x in graph_1hop_vs_2hop_per_query
                    if x["repaired_1hop_vs_2hop_diff"]["top10_jaccard"] < 1.0
                ],
            },
        },
        "fallback_diagnostics": fallback_summary,
        "query_coverage_diagnostics": {
            "total_missing_slots_out_of_100_by_system": total_missing_slots_by_system,
            "per_query": query_coverage,
        },
        "latency_and_runtime_diagnostics": {
            "s5b1_timing_source": "research/s5-b1-integrity-repair/reports/retrieval_timing_report.json",
            "s5b1_timing_scope_note": (
                "Measured on the 12-query S5-B1.1 set (5 warm repetitions per query). "
                "Q-S5B2-02 and Q-S5B2-10 were reworded in S5-B2.1 and Q-S5A-09/Q-S5A-12 were held; "
                "multi-repetition timing was not re-run in S5-B2.1."
            ),
            "application_cold_start_ms": timing_s5b1["application_cold_start_ms"],
            "s5b1_system_timing_summary_ms": timing_s5b1["systems"],
            "s5b1_per_query_warm_mean_ms": s5b1_per_query_warm,
            "s5b2_1_hybrid_rrf_single_pass_breakdown_ms": hybrid_s5b2_breakdowns,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    preservation = verify_preserved_artifacts(ROOT)
    preservation_path = OUT_DIR / "s5d0_preservation_manifest.json"
    preservation_path.write_text(json.dumps(preservation, indent=2) + "\n", encoding="utf-8")

    diagnostics = compute_diagnostics(ROOT)
    diagnostics_path = OUT_DIR / "s5d0_technical_diagnostics.json"
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")

    print(f"Preservation check passed: {preservation['all_checks_passed']} "
          f"({preservation['verified_exact_matches']} exact SHA-256 matches, "
          f"{preservation['recorded_unmodified']} additional recorded)")
    if not preservation["all_checks_passed"]:
        raise SystemExit(f"Preservation mismatches detected: {preservation['mismatches']}")
    print(f"Wrote {preservation_path.relative_to(ROOT)}")
    print(f"Wrote {diagnostics_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
