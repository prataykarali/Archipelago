"""Typed data structures for S5-v3 retrieval variants and diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CorpusPassage:
    """Normalized passage record loaded from Corpus v3 JSONL."""

    passage_id: str
    source_doc_id: str
    text: str
    page_start: int = 0
    page_end: int = 0
    provenance_class: str = "unknown"
    source_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize passage metadata (excluding raw text for public manifests)."""
        return {
            "passage_id": self.passage_id,
            "source_doc_id": self.source_doc_id,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "provenance_class": self.provenance_class,
            "source_sha256": self.source_sha256,
        }


@dataclass(frozen=True)
class GraphConcept:
    """Concept node loaded from okf_graph.json."""

    concept_id: str
    name: str
    concept_type: str = "unknown"
    difficulty: str = "unknown"
    summary: str = ""
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class GraphEdge:
    """Directed typed edge loaded from okf_graph.json with provenance and confidence."""

    from_id: str
    from_name: str
    to_id: str
    to_name: str
    edge_type: str
    raw_relation: str
    source: str
    confidence: float


@dataclass(frozen=True)
class ConceptPassageLink:
    """Provenance record linking a graph concept to a Corpus v3 passage."""

    concept_id: str
    passage_id: str
    source_doc_id: str
    page_start: int
    matched_surface: str
    match_kind: str


@dataclass(frozen=True)
class RankedPassage:
    """Single ranked retrieval hit with per-rank provenance."""

    passage_id: str
    rank: int
    score: float
    source: str
    contributing_concepts: tuple[str, ...] = ()
    hop_attribution: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "passage_id": self.passage_id,
            "rank": self.rank,
            "score": round(self.score, 6),
            "source": self.source,
            "contributing_concepts": list(self.contributing_concepts),
            "hop_attribution": list(self.hop_attribution),
        }


@dataclass(frozen=True)
class TraversalStep:
    """Single traversed graph edge recorded during controlled multi-hop expansion."""

    source_concept: str
    target_concept: str
    edge_type: str
    hop: int
    edge_confidence: float
    propagated_weight: float
    edge_source: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class QueryProvenance:
    """Detailed per-query instrumentation for S5-v3 diagnostics."""

    matched_anchors: tuple[str, ...] = ()
    matched_surfaces: tuple[str, ...] = ()
    grounded_anchors: tuple[str, ...] = ()
    query_token_count: int = 0
    covered_query_token_count: int = 0
    query_anchor_coverage_ratio: float = 0.0
    grounded_anchor_ratio: float = 0.0
    traversed_concepts_count: int = 0
    observed_hop_depth: int = 0
    hop_concept_counts: dict[str, int] = field(default_factory=dict)
    edge_type_counts: dict[str, int] = field(default_factory=dict)
    mean_edge_confidence: float = 0.0
    fallback_triggered: bool = False
    fallback_reason: str = "none"
    short_list_before_backfill: bool = False
    graph_result_count: int = 0
    backfill_count: int = 0
    routing_decision: str = "not_applicable"
    graph_route_weight: float = 1.0
    lexical_route_weight: float = 0.0
    paths_traversed: tuple[TraversalStep, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "matched_anchors": list(self.matched_anchors),
            "matched_surfaces": list(self.matched_surfaces),
            "grounded_anchors": list(self.grounded_anchors),
            "query_token_count": self.query_token_count,
            "covered_query_token_count": self.covered_query_token_count,
            "query_anchor_coverage_ratio": round(self.query_anchor_coverage_ratio, 6),
            "grounded_anchor_ratio": round(self.grounded_anchor_ratio, 6),
            "traversed_concepts_count": self.traversed_concepts_count,
            "observed_hop_depth": self.observed_hop_depth,
            "hop_concept_counts": dict(self.hop_concept_counts),
            "edge_type_counts": dict(self.edge_type_counts),
            "mean_edge_confidence": round(self.mean_edge_confidence, 6),
            "fallback_triggered": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "short_list_before_backfill": self.short_list_before_backfill,
            "graph_result_count": self.graph_result_count,
            "backfill_count": self.backfill_count,
            "routing_decision": self.routing_decision,
            "graph_route_weight": round(self.graph_route_weight, 6),
            "lexical_route_weight": round(self.lexical_route_weight, 6),
            "paths_traversed_count": len(self.paths_traversed),
        }


@dataclass(frozen=True)
class QueryTimingMemory:
    """End-to-end latency and memory telemetry for a single query."""

    latency_ns: int
    latency_ms: float
    peak_memory_bytes: int
    current_memory_bytes: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "latency_ns": self.latency_ns,
            "latency_ms": round(self.latency_ms, 4),
            "peak_memory_bytes": self.peak_memory_bytes,
            "current_memory_bytes": self.current_memory_bytes,
        }


@dataclass(frozen=True)
class QueryResult:
    """Complete retrieval output for one query under one system variant."""

    query_id: str
    query_text: str
    variant_name: str
    config_sha256: str
    results: tuple[RankedPassage, ...]
    provenance: QueryProvenance
    telemetry: QueryTimingMemory

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "query_id": self.query_id,
            "variant_name": self.variant_name,
            "config_sha256": self.config_sha256,
            "result_count": len(self.results),
            "results": [r.to_dict() for r in self.results],
            "provenance": self.provenance.to_dict(),
            "telemetry": self.telemetry.to_dict(),
        }
