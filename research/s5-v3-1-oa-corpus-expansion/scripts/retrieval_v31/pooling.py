"""Relevance-agnostic depth-5 and depth-10 pooling statistics across S5-v3.1 systems."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import statistics
from typing import Any

from retrieval_v3.types import QueryResult

POOL_DEPTHS: tuple[int, int] = (5, 10)


def compute_pool_sizes_at_depth(
    results_by_system: Mapping[str, Sequence[QueryResult]],
    depth: int,
    *,
    system_subset: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compute unique passage pool sizes per query at a fixed rank depth (relevance-agnostic)."""
    selected_systems = (
        list(system_subset) if system_subset is not None else sorted(results_by_system.keys())
    )
    if not selected_systems:
        return {
            "depth": depth,
            "system_count": 0,
            "systems": [],
            "query_count": 0,
            "total_unique_query_passage_pairs": 0,
            "per_query_pool_size": {},
            "summary": {"mean": 0.0, "std": 0.0, "min": 0, "max": 0},
        }

    # Group ranked passage IDs by query_id
    pools_by_qid: dict[str, set[str]] = {}
    ordered_qids: list[str] = []
    seen_qids: set[str] = set()

    for sys_name in selected_systems:
        for qr in results_by_system[sys_name]:
            if qr.query_id not in seen_qids:
                seen_qids.add(qr.query_id)
                ordered_qids.append(qr.query_id)
            pool = pools_by_qid.setdefault(qr.query_id, set())
            for hit in qr.results[:depth]:
                pool.add(hit.passage_id)

    per_query_counts = {qid: len(pools_by_qid[qid]) for qid in ordered_qids}
    sizes = list(per_query_counts.values())
    std_val = statistics.stdev(sizes) if len(sizes) > 1 else 0.0

    return {
        "depth": depth,
        "system_count": len(selected_systems),
        "systems": selected_systems,
        "query_count": len(ordered_qids),
        "total_unique_query_passage_pairs": sum(sizes),
        "per_query_pool_size": per_query_counts,
        "summary": {
            "mean": round(statistics.mean(sizes) if sizes else 0.0, 4),
            "std": round(std_val, 4),
            "min": min(sizes) if sizes else 0,
            "max": max(sizes) if sizes else 0,
        },
    }


def compute_all_pool_diagnostics(
    results_by_system: Mapping[str, Sequence[QueryResult]],
    *,
    control_systems: Sequence[str],
    graph_v3_systems: Sequence[str],
) -> dict[str, Any]:
    """Compute depth-5 and depth-10 unique pools for all systems, controls, and graph variants."""
    all_systems = sorted(results_by_system.keys())
    active_controls = [s for s in control_systems if s in results_by_system]
    active_graph = [s for s in graph_v3_systems if s in results_by_system]

    report: dict[str, Any] = {}
    for depth in POOL_DEPTHS:
        report[f"depth_{depth}"] = {
            "all_systems": compute_pool_sizes_at_depth(
                results_by_system, depth, system_subset=all_systems
            ),
            "controls_only": compute_pool_sizes_at_depth(
                results_by_system, depth, system_subset=active_controls
            ),
            "graph_v3_only": compute_pool_sizes_at_depth(
                results_by_system, depth, system_subset=active_graph
            ),
        }
    return report
