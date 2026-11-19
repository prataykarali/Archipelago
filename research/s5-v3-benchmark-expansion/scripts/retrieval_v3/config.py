"""Versioned configuration, ablation toggles, and SHA-256 hashing for S5-v3 retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

# Named constants — no magic numbers
SCHEMA_VERSION = "s5v3-retrieval-v3.0"
DEFAULT_TOP_K = 10
DEFAULT_BM25_K1 = 1.5
DEFAULT_BM25_B = 0.75
DEFAULT_RRF_K = 60
DEFAULT_MAX_HOPS = 2
DEFAULT_HOP_DECAY = 0.5
DEFAULT_MAX_FANOUT_PER_NODE = 8
DEFAULT_MIN_COVERAGE_FOR_GRAPH = 0.15
DEFAULT_HIGH_COVERAGE_THRESHOLD = 0.50
DEFAULT_GRAPH_HEAVY_WEIGHT = 0.65
DEFAULT_BALANCED_GRAPH_WEIGHT = 0.35
DEFAULT_CANDIDATE_POOL_MULTIPLIER = 3
DEFAULT_MIN_CONCEPT_NAME_LEN = 2

# Canonical edge type weights
EDGE_TYPE_WEIGHTS: dict[str, float] = {
    "REQUIRES": 1.0,
    "PART_OF": 0.9,
    "ENABLES": 0.85,
    "USES": 0.8,
    "CONTRASTS_WITH": 0.7,
    "RELATED": 0.5,
}

# Edge confidence priors when okf_graph.json omits explicit numeric confidence
EDGE_CONFIDENCE_WITH_SOURCE = 0.85
EDGE_CONFIDENCE_NO_SOURCE = 0.50
EDGE_CONFIDENCE_CO_MENTION = 0.60


@dataclass(frozen=True)
class RetrievalV3Config:
    """Explicit, hashable configuration for a single S5-v3 retrieval variant."""

    variant_name: str
    mode: str = "graph"  # "lexical" | "graph"
    top_k: int = DEFAULT_TOP_K
    bm25_k1: float = DEFAULT_BM25_K1
    bm25_b: float = DEFAULT_BM25_B
    rrf_k: int = DEFAULT_RRF_K
    # Improvement 1: Token-boundary-aware graph anchor matching
    use_boundary_matching: bool = True
    # Improvement 2: Concept aliases and technical-term normalization
    use_alias_normalization: bool = True
    # Improvement 3: Corpus-grounded concept-to-passage mapping
    use_corpus_grounded_mapping: bool = True
    # Improvement 4: Graph edge provenance, confidence & coverage instrumentation
    use_edge_confidence_weighting: bool = True
    # Improvement 5: Deterministic zero-anchor fallback
    enable_zero_anchor_fallback: bool = True
    # Improvement 6: Partial-list backfill when fewer than Top-K passages returned
    enable_partial_backfill: bool = True
    # Improvement 7: Controlled 1-hop / 2-hop graph traversal
    max_hops: int = DEFAULT_MAX_HOPS
    hop_decay: float = DEFAULT_HOP_DECAY
    max_fanout_per_node: int = DEFAULT_MAX_FANOUT_PER_NODE
    enforce_cycle_guard: bool = True
    # Improvement 8: Coverage-aware retrieval routing
    enable_coverage_routing: bool = False
    min_coverage_for_graph: float = DEFAULT_MIN_COVERAGE_FOR_GRAPH
    high_coverage_threshold: float = DEFAULT_HIGH_COVERAGE_THRESHOLD
    graph_heavy_weight: float = DEFAULT_GRAPH_HEAVY_WEIGHT
    balanced_graph_weight: float = DEFAULT_BALANCED_GRAPH_WEIGHT
    # Improvement 9: End-to-end timing and memory instrumentation
    measure_memory: bool = True
    schema_version: str = SCHEMA_VERSION

    def to_canonical_dict(self) -> dict[str, Any]:
        """Return sorted dictionary representation for deterministic hashing."""
        data = asdict(self)
        return dict(sorted(data.items()))

    def config_sha256(self) -> str:
        """Compute deterministic SHA-256 hash over canonical JSON serialization."""
        payload = json.dumps(
            self.to_canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def build_standard_v3_variants() -> list[RetrievalV3Config]:
    """Return the canonical suite of S5-v3 variants and ablation controls."""
    return [
        # Control 0: Pure lexical BM25 on Corpus v3
        RetrievalV3Config(
            variant_name="v3_lexical_bm25_control",
            mode="lexical",
            use_boundary_matching=False,
            use_alias_normalization=False,
            use_corpus_grounded_mapping=False,
            use_edge_confidence_weighting=False,
            enable_zero_anchor_fallback=False,
            enable_partial_backfill=False,
            max_hops=0,
            enable_coverage_routing=False,
        ),
        # Control 1: Naive substring matching, no aliases, no fallback, no backfill (v2.1-style defect baseline)
        RetrievalV3Config(
            variant_name="v3_graph_naive_substring_ablation",
            mode="graph",
            use_boundary_matching=False,
            use_alias_normalization=False,
            use_corpus_grounded_mapping=True,
            use_edge_confidence_weighting=False,
            enable_zero_anchor_fallback=False,
            enable_partial_backfill=False,
            max_hops=1,
            enable_coverage_routing=False,
        ),
        # Variant 2: Boundary matching + alias normalization + grounded mapping + fallback, NO backfill (1-hop)
        RetrievalV3Config(
            variant_name="v3_graph_1hop_no_backfill",
            mode="graph",
            use_boundary_matching=True,
            use_alias_normalization=True,
            use_corpus_grounded_mapping=True,
            use_edge_confidence_weighting=True,
            enable_zero_anchor_fallback=True,
            enable_partial_backfill=False,
            max_hops=1,
            enable_coverage_routing=False,
        ),
        # Variant 3: Full controlled 1-hop with boundary, aliases, fallback, and backfill
        RetrievalV3Config(
            variant_name="v3_graph_1hop_backfill",
            mode="graph",
            use_boundary_matching=True,
            use_alias_normalization=True,
            use_corpus_grounded_mapping=True,
            use_edge_confidence_weighting=True,
            enable_zero_anchor_fallback=True,
            enable_partial_backfill=True,
            max_hops=1,
            enable_coverage_routing=False,
        ),
        # Variant 4: Full controlled 2-hop with boundary, aliases, fallback, and backfill
        RetrievalV3Config(
            variant_name="v3_graph_2hop_backfill",
            mode="graph",
            use_boundary_matching=True,
            use_alias_normalization=True,
            use_corpus_grounded_mapping=True,
            use_edge_confidence_weighting=True,
            enable_zero_anchor_fallback=True,
            enable_partial_backfill=True,
            max_hops=2,
            enable_coverage_routing=False,
        ),
        # Variant 5: Coverage-aware routed hybrid (graph 2-hop + lexical weighted by measured coverage)
        RetrievalV3Config(
            variant_name="v3_graph_2hop_coverage_routed",
            mode="graph",
            use_boundary_matching=True,
            use_alias_normalization=True,
            use_corpus_grounded_mapping=True,
            use_edge_confidence_weighting=True,
            enable_zero_anchor_fallback=True,
            enable_partial_backfill=True,
            max_hops=2,
            enable_coverage_routing=True,
        ),
    ]
