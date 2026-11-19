"""Improvements #5, #6, #7, #8: Controlled traversal, fallback, backfill, and coverage routing."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence

from retrieval_v3.config import (
    DEFAULT_CANDIDATE_POOL_MULTIPLIER,
    EDGE_TYPE_WEIGHTS,
    RetrievalV3Config,
)
from retrieval_v3.corpus_grounding import GroundedGraphIndex
from retrieval_v3.lexical import BM25LexicalControl
from retrieval_v3.normalization import AnchorMatch, extract_content_tokens
from retrieval_v3.types import QueryProvenance, RankedPassage, TraversalStep

ANCHOR_BASE_WEIGHT = 1.0
DEFAULT_EDGE_WEIGHT_FALLBACK = 0.5


def compute_query_coverage(
    query: str,
    matches: Sequence[AnchorMatch],
    grounded_anchors: Sequence[str],
    *,
    normalize: bool,
) -> tuple[int, int, float, float]:
    """Compute non-stopword query token coverage and grounded-anchor ratio."""
    q_tokens = extract_content_tokens(query, normalize=normalize)
    q_token_set = set(q_tokens)
    covered_tokens: set[str] = set()
    for match in matches:
        for tok in match.matched_tokens:
            if tok in q_token_set:
                covered_tokens.add(tok)

    q_count = len(q_token_set)
    cov_count = len(covered_tokens)
    cov_ratio = cov_count / q_count if q_count > 0 else 0.0
    grounded_ratio = len(grounded_anchors) / len(matches) if matches else 0.0
    return q_count, cov_count, cov_ratio, grounded_ratio


def traverse_controlled_graph(
    anchors: Sequence[str],
    index: GroundedGraphIndex,
    config: RetrievalV3Config,
) -> tuple[
    dict[str, float],
    dict[str, set[int]],
    list[TraversalStep],
    dict[str, int],
    int,
]:
    """Perform bounded 0/1/2-hop traversal with hop decay, fanout cap, and cycle guard."""
    concept_weights: dict[str, float] = {}
    concept_hops: dict[str, set[int]] = defaultdict(set)
    steps: list[TraversalStep] = []
    hop_nodes: dict[int, set[str]] = {0: set(), 1: set(), 2: set()}

    visited_depth: dict[str, int] = {}
    frontier: list[tuple[str, float]] = []

    for anchor in sorted(set(anchors)):
        concept_weights[anchor] = max(concept_weights.get(anchor, 0.0), ANCHOR_BASE_WEIGHT)
        concept_hops[anchor].add(0)
        hop_nodes[0].add(anchor)
        visited_depth[anchor] = 0
        frontier.append((anchor, ANCHOR_BASE_WEIGHT))

    for hop in range(1, config.max_hops + 1):
        next_frontier: dict[str, float] = {}
        decay = config.hop_decay**hop
        for src_id, src_weight in sorted(frontier, key=lambda item: (-item[1], item[0])):
            neighbors = index.adjacency.get(src_id, ())
            admitted = 0
            for edge in neighbors:
                if admitted >= config.max_fanout_per_node:
                    break
                target_id = edge.to_id
                if (
                    config.enforce_cycle_guard
                    and target_id in visited_depth
                    and visited_depth[target_id] <= hop
                ):
                    continue
                base_w = EDGE_TYPE_WEIGHTS.get(edge.edge_type, DEFAULT_EDGE_WEIGHT_FALLBACK)
                eff_w = base_w * (edge.confidence if config.use_edge_confidence_weighting else 1.0)
                prop_weight = src_weight * eff_w * decay

                steps.append(
                    TraversalStep(
                        source_concept=src_id,
                        target_concept=target_id,
                        edge_type=edge.edge_type,
                        hop=hop,
                        edge_confidence=edge.confidence,
                        propagated_weight=round(prop_weight, 6),
                        edge_source=edge.source,
                    )
                )
                admitted += 1
                concept_weights[target_id] = max(concept_weights.get(target_id, 0.0), prop_weight)
                concept_hops[target_id].add(hop)
                hop_nodes.setdefault(hop, set()).add(target_id)
                if target_id not in visited_depth:
                    visited_depth[target_id] = hop
                if prop_weight > next_frontier.get(target_id, 0.0):
                    next_frontier[target_id] = prop_weight

        frontier = list(next_frontier.items())
        if not frontier:
            break

    observed_hop = 0
    for hop_level in sorted(hop_nodes):
        if hop_level > 0 and hop_nodes[hop_level]:
            observed_hop = hop_level

    hop_counts = {f"hop_{h}": len(nodes) for h, nodes in sorted(hop_nodes.items()) if nodes}
    return concept_weights, concept_hops, steps, hop_counts, observed_hop


def score_graph_passages(
    concept_weights: dict[str, float],
    concept_hops: dict[str, set[int]],
    index: GroundedGraphIndex,
) -> list[tuple[str, float, tuple[str, ...], tuple[int, ...]]]:
    """Aggregate concept weights into deterministic passage rankings with attribution."""
    pid_scores: dict[str, float] = defaultdict(float)
    pid_concepts: dict[str, set[str]] = defaultdict(set)
    pid_hops: dict[str, set[int]] = defaultdict(set)

    for cid, weight in sorted(concept_weights.items()):
        c_hops = concept_hops.get(cid, set())
        for pid in index.concept_to_passages.get(cid, ()):
            pid_scores[pid] += weight
            pid_concepts[pid].add(cid)
            pid_hops[pid].update(c_hops)

    ranked = [
        (
            pid,
            score,
            tuple(sorted(pid_concepts[pid])),
            tuple(sorted(pid_hops[pid])),
        )
        for pid, score in pid_scores.items()
    ]
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked


def decide_coverage_route(
    coverage_ratio: float,
    grounded_ratio: float,
    config: RetrievalV3Config,
) -> tuple[str, float, float]:
    """Determine coverage-aware routing weights strictly from measured anchor coverage."""
    if grounded_ratio <= 0.0 or coverage_ratio < config.min_coverage_for_graph:
        return "lexical_only", 0.0, 1.0
    if coverage_ratio >= config.high_coverage_threshold:
        g_w = config.graph_heavy_weight
        return "graph_heavy", g_w, 1.0 - g_w
    g_w = config.balanced_graph_weight
    return "balanced_hybrid", g_w, 1.0 - g_w


def weighted_rrf_fuse(
    graph_ranked: Sequence[tuple[str, float, tuple[str, ...], tuple[int, ...]]],
    lexical_ranked: Sequence[tuple[str, float]],
    *,
    graph_weight: float,
    lexical_weight: float,
    rrf_k: int,
    top_k: int,
) -> list[RankedPassage]:
    """Deterministically fuse graph and lexical rankings using weighted RRF."""
    fused_scores: dict[str, float] = defaultdict(float)
    concepts_by_pid: dict[str, tuple[str, ...]] = {}
    hops_by_pid: dict[str, tuple[int, ...]] = {}

    for rank_idx, (pid, _score, concepts, hops) in enumerate(graph_ranked, start=1):
        fused_scores[pid] += graph_weight / (rrf_k + rank_idx)
        concepts_by_pid[pid] = concepts
        hops_by_pid[pid] = hops

    for rank_idx, (pid, _score) in enumerate(lexical_ranked, start=1):
        fused_scores[pid] += lexical_weight / (rrf_k + rank_idx)

    ordered = sorted(fused_scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
    source_tag = "lexical" if graph_weight <= 0.0 else "routed"
    return [
        RankedPassage(
            passage_id=pid,
            rank=idx,
            score=score,
            source=source_tag,
            contributing_concepts=concepts_by_pid.get(pid, ()),
            hop_attribution=hops_by_pid.get(pid, ()),
        )
        for idx, (pid, score) in enumerate(ordered, start=1)
    ]


def execute_graph_search(
    query: str,
    matches: Sequence[AnchorMatch],
    index: GroundedGraphIndex,
    lexical_control: BM25LexicalControl,
    config: RetrievalV3Config,
) -> tuple[tuple[RankedPassage, ...], QueryProvenance]:
    """Run full S5-v3 graph retrieval pipeline (traversal, fallback, backfill, routing)."""
    matched_anchors = tuple(m.concept_id for m in matches)
    matched_surfaces = tuple(m.matched_surface for m in matches)
    grounded_anchors = tuple(cid for cid in matched_anchors if index.concept_to_passages.get(cid))
    q_tok_cnt, cov_tok_cnt, cov_ratio, grounded_ratio = compute_query_coverage(
        query,
        matches,
        grounded_anchors,
        normalize=config.use_alias_normalization,
    )

    # Zero-anchor case
    if not matched_anchors:
        if config.enable_zero_anchor_fallback:
            fb_hits = lexical_control.search(query, top_k=config.top_k)
            ranked_hits = tuple(
                RankedPassage(passage_id=pid, rank=idx, score=sc, source="fallback")
                for idx, (pid, sc) in enumerate(fb_hits, start=1)
            )
            return ranked_hits, QueryProvenance(
                query_token_count=q_tok_cnt,
                covered_query_token_count=cov_tok_cnt,
                query_anchor_coverage_ratio=cov_ratio,
                grounded_anchor_ratio=grounded_ratio,
                fallback_triggered=True,
                fallback_reason="zero_anchors_matched",
                routing_decision="lexical_only" if config.enable_coverage_routing else "fallback",
                graph_route_weight=0.0,
                lexical_route_weight=1.0,
            )
        return (), QueryProvenance(
            query_token_count=q_tok_cnt,
            covered_query_token_count=cov_tok_cnt,
            query_anchor_coverage_ratio=cov_ratio,
            grounded_anchor_ratio=grounded_ratio,
            fallback_triggered=False,
            fallback_reason="fallback_disabled_zero_anchors",
            short_list_before_backfill=True,
            routing_decision="not_applicable",
        )

    # Controlled 0/1/2-hop traversal
    concept_weights, concept_hops, steps, hop_counts, observed_hop = traverse_controlled_graph(
        matched_anchors, index, config
    )
    graph_scored = score_graph_passages(concept_weights, concept_hops, index)
    edge_type_counts = dict(sorted(Counter(s.edge_type for s in steps).items()))
    mean_edge_conf = sum(s.edge_confidence for s in steps) / len(steps) if steps else 0.0

    # Zero grounded passages after traversal
    if not graph_scored:
        if config.enable_zero_anchor_fallback:
            fb_hits = lexical_control.search(query, top_k=config.top_k)
            ranked_hits = tuple(
                RankedPassage(passage_id=pid, rank=idx, score=sc, source="fallback")
                for idx, (pid, sc) in enumerate(fb_hits, start=1)
            )
            return ranked_hits, QueryProvenance(
                matched_anchors=matched_anchors,
                matched_surfaces=matched_surfaces,
                grounded_anchors=grounded_anchors,
                query_token_count=q_tok_cnt,
                covered_query_token_count=cov_tok_cnt,
                query_anchor_coverage_ratio=cov_ratio,
                grounded_anchor_ratio=grounded_ratio,
                traversed_concepts_count=len(concept_weights),
                observed_hop_depth=observed_hop,
                hop_concept_counts=hop_counts,
                edge_type_counts=edge_type_counts,
                mean_edge_confidence=mean_edge_conf,
                fallback_triggered=True,
                fallback_reason="zero_grounded_passages",
                routing_decision="lexical_only" if config.enable_coverage_routing else "fallback",
                graph_route_weight=0.0,
                lexical_route_weight=1.0,
                paths_traversed=tuple(steps),
            )
        return (), QueryProvenance(
            matched_anchors=matched_anchors,
            matched_surfaces=matched_surfaces,
            grounded_anchors=grounded_anchors,
            query_token_count=q_tok_cnt,
            covered_query_token_count=cov_tok_cnt,
            query_anchor_coverage_ratio=cov_ratio,
            grounded_anchor_ratio=grounded_ratio,
            traversed_concepts_count=len(concept_weights),
            observed_hop_depth=observed_hop,
            hop_concept_counts=hop_counts,
            edge_type_counts=edge_type_counts,
            mean_edge_confidence=mean_edge_conf,
            fallback_triggered=False,
            fallback_reason="fallback_disabled_zero_grounded_passages",
            short_list_before_backfill=True,
            paths_traversed=tuple(steps),
        )

    # Coverage-aware routing (Improvement #8)
    if config.enable_coverage_routing:
        route_label, g_w, l_w = decide_coverage_route(cov_ratio, grounded_ratio, config)
        pool_k = config.top_k * DEFAULT_CANDIDATE_POOL_MULTIPLIER
        lex_pool = lexical_control.search(query, top_k=pool_k)
        fused = weighted_rrf_fuse(
            graph_scored[:pool_k],
            lex_pool,
            graph_weight=g_w,
            lexical_weight=l_w,
            rrf_k=config.rrf_k,
            top_k=config.top_k,
        )
        return tuple(fused), QueryProvenance(
            matched_anchors=matched_anchors,
            matched_surfaces=matched_surfaces,
            grounded_anchors=grounded_anchors,
            query_token_count=q_tok_cnt,
            covered_query_token_count=cov_tok_cnt,
            query_anchor_coverage_ratio=cov_ratio,
            grounded_anchor_ratio=grounded_ratio,
            traversed_concepts_count=len(concept_weights),
            observed_hop_depth=observed_hop,
            hop_concept_counts=hop_counts,
            edge_type_counts=edge_type_counts,
            mean_edge_confidence=mean_edge_conf,
            fallback_triggered=False,
            fallback_reason="none",
            short_list_before_backfill=len(graph_scored) < config.top_k,
            graph_result_count=min(len(graph_scored), config.top_k),
            backfill_count=0,
            routing_decision=route_label,
            graph_route_weight=g_w,
            lexical_route_weight=l_w,
            paths_traversed=tuple(steps),
        )

    # Standard graph ranking + optional partial-list backfill (Improvement #6)
    graph_top = graph_scored[: config.top_k]
    ranked_list: list[RankedPassage] = [
        RankedPassage(
            passage_id=pid,
            rank=idx,
            score=score,
            source="graph",
            contributing_concepts=concepts,
            hop_attribution=hops,
        )
        for idx, (pid, score, concepts, hops) in enumerate(graph_top, start=1)
    ]

    short_list = len(ranked_list) < config.top_k
    backfill_count = 0
    if short_list and config.enable_partial_backfill:
        seen_pids = {r.passage_id for r in ranked_list}
        lex_candidates = lexical_control.search(
            query, top_k=config.top_k * DEFAULT_CANDIDATE_POOL_MULTIPLIER
        )
        for pid, lex_score in lex_candidates:
            if len(ranked_list) >= config.top_k:
                break
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            backfill_count += 1
            ranked_list.append(
                RankedPassage(
                    passage_id=pid,
                    rank=len(ranked_list) + 1,
                    score=lex_score,
                    source="backfill",
                )
            )

    return tuple(ranked_list), QueryProvenance(
        matched_anchors=matched_anchors,
        matched_surfaces=matched_surfaces,
        grounded_anchors=grounded_anchors,
        query_token_count=q_tok_cnt,
        covered_query_token_count=cov_tok_cnt,
        query_anchor_coverage_ratio=cov_ratio,
        grounded_anchor_ratio=grounded_ratio,
        traversed_concepts_count=len(concept_weights),
        observed_hop_depth=observed_hop,
        hop_concept_counts=hop_counts,
        edge_type_counts=edge_type_counts,
        mean_edge_confidence=mean_edge_conf,
        fallback_triggered=False,
        fallback_reason="none",
        short_list_before_backfill=short_list,
        graph_result_count=len(graph_top),
        backfill_count=backfill_count,
        routing_decision="graph_only_with_backfill"
        if config.enable_partial_backfill
        else "graph_only",
        graph_route_weight=1.0,
        lexical_route_weight=0.0,
        paths_traversed=tuple(steps),
    )
