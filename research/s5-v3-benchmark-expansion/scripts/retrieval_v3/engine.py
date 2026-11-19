"""High-level S5-v3 retrieval engine and relevance-agnostic diagnostics aggregator."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
import statistics
from typing import Any

from retrieval_v3.config import RetrievalV3Config
from retrieval_v3.corpus_grounding import GroundedGraphIndex, build_corpus_grounded_index
from retrieval_v3.instrumentation import measure_call, summarize_telemetry
from retrieval_v3.lexical import BM25LexicalControl
from retrieval_v3.normalization import ConceptAnchorMatcher
from retrieval_v3.traversal import execute_graph_search
from retrieval_v3.types import (
    CorpusPassage,
    GraphConcept,
    GraphEdge,
    QueryProvenance,
    QueryResult,
    QueryTimingMemory,
    RankedPassage,
)


class RetrievalV3Engine:
    """Single configured S5-v3 retrieval variant with end-to-end telemetry."""

    def __init__(
        self,
        config: RetrievalV3Config,
        passages: Sequence[CorpusPassage],
        concepts: dict[str, GraphConcept],
        edges: Sequence[GraphEdge],
        *,
        shared_lexical: BM25LexicalControl | None = None,
    ) -> None:
        self.config = config
        self.config_sha256 = config.config_sha256()
        self.passages = list(passages)

        def _build_components() -> tuple[
            BM25LexicalControl,
            ConceptAnchorMatcher | None,
            GroundedGraphIndex | None,
        ]:
            lex = shared_lexical or BM25LexicalControl(
                self.passages, k1=config.bm25_k1, b=config.bm25_b
            )
            if config.mode == "lexical":
                return lex, None, None
            concept_names = {cid: c.name for cid, c in concepts.items()}
            matcher = ConceptAnchorMatcher(
                concept_names,
                use_boundary_matching=config.use_boundary_matching,
                use_alias_normalization=config.use_alias_normalization,
            )
            g_index = build_corpus_grounded_index(
                self.passages,
                concepts,
                edges,
                matcher,
                use_corpus_grounded_mapping=config.use_corpus_grounded_mapping,
            )
            return lex, matcher, g_index

        (self.lexical, self.matcher, self.graph_index), self.index_build_telemetry = measure_call(
            _build_components, measure_memory=config.measure_memory
        )

    def search_query(self, query_id: str, query_text: str) -> QueryResult:
        """Execute retrieval for one query and capture full provenance + telemetry."""

        def _run() -> tuple[tuple[RankedPassage, ...], QueryProvenance]:
            if self.config.mode == "lexical":
                hits = self.lexical.search(query_text, top_k=self.config.top_k)
                ranked = tuple(
                    RankedPassage(passage_id=pid, rank=idx, score=sc, source="lexical")
                    for idx, (pid, sc) in enumerate(hits, start=1)
                )
                return ranked, QueryProvenance(
                    routing_decision="lexical_control",
                    graph_route_weight=0.0,
                    lexical_route_weight=1.0,
                )

            assert self.matcher is not None
            assert self.graph_index is not None
            matches = self.matcher.match_text(query_text)
            return execute_graph_search(
                query_text,
                matches,
                self.graph_index,
                self.lexical,
                self.config,
            )

        (results, provenance), telemetry = measure_call(
            _run, measure_memory=self.config.measure_memory
        )
        return QueryResult(
            query_id=query_id,
            query_text=query_text,
            variant_name=self.config.variant_name,
            config_sha256=self.config_sha256,
            results=results,
            provenance=provenance,
            telemetry=telemetry,
        )


def aggregate_variant_diagnostics(
    engine: RetrievalV3Engine,
    query_results: Sequence[QueryResult],
) -> dict[str, Any]:
    """Compute relevance-agnostic technical diagnostics for a variant across all queries."""
    n = len(query_results)
    telemetries: list[QueryTimingMemory] = [qr.telemetry for qr in query_results]
    anchor_hits = sum(1 for qr in query_results if qr.provenance.matched_anchors)
    grounded_hits = sum(1 for qr in query_results if qr.provenance.grounded_anchors)
    fallbacks = sum(1 for qr in query_results if qr.provenance.fallback_triggered)
    short_lists_before = sum(1 for qr in query_results if qr.provenance.short_list_before_backfill)
    short_lists_after = sum(1 for qr in query_results if len(qr.results) < engine.config.top_k)
    zero_results_after = sum(1 for qr in query_results if len(qr.results) == 0)
    total_backfill = sum(qr.provenance.backfill_count for qr in query_results)

    coverage_ratios = [qr.provenance.query_anchor_coverage_ratio for qr in query_results]
    hop_dist = Counter(qr.provenance.observed_hop_depth for qr in query_results)
    route_dist = Counter(qr.provenance.routing_decision for qr in query_results)
    fallback_reasons = Counter(
        qr.provenance.fallback_reason for qr in query_results if qr.provenance.fallback_triggered
    )
    edge_type_totals: Counter[str] = Counter()
    for qr in query_results:
        edge_type_totals.update(qr.provenance.edge_type_counts)

    return {
        "variant_name": engine.config.variant_name,
        "config_sha256": engine.config_sha256,
        "config": engine.config.to_canonical_dict(),
        "effectiveness_evaluation": "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS",
        "index_build_telemetry": engine.index_build_telemetry.to_dict(),
        "corpus_graph_coverage": (
            engine.graph_index.coverage_summary() if engine.graph_index is not None else None
        ),
        "query_count": n,
        "technical_diagnostics": {
            "anchor_hit_count": anchor_hits,
            "anchor_hit_rate": round(anchor_hits / n if n else 0.0, 6),
            "grounded_anchor_query_count": grounded_hits,
            "grounded_anchor_query_rate": round(grounded_hits / n if n else 0.0, 6),
            "fallback_count": fallbacks,
            "fallback_rate": round(fallbacks / n if n else 0.0, 6),
            "fallback_reasons": dict(sorted(fallback_reasons.items())),
            "short_list_before_backfill_count": short_lists_before,
            "short_list_before_backfill_rate": round(short_lists_before / n if n else 0.0, 6),
            "short_list_after_backfill_count": short_lists_after,
            "short_list_after_backfill_rate": round(short_lists_after / n if n else 0.0, 6),
            "zero_result_after_count": zero_results_after,
            "total_backfill_passages": total_backfill,
            "mean_backfill_per_query": round(total_backfill / n if n else 0.0, 4),
            "mean_query_anchor_coverage_ratio": round(
                statistics.mean(coverage_ratios) if coverage_ratios else 0.0, 6
            ),
            "observed_hop_depth_distribution": {str(k): v for k, v in sorted(hop_dist.items())},
            "routing_decision_distribution": dict(sorted(route_dist.items())),
            "traversed_edge_type_totals": dict(sorted(edge_type_totals.items())),
        },
        "telemetry_summary": summarize_telemetry(telemetries),
        "per_query_diagnostics": [qr.to_dict() for qr in query_results],
    }
