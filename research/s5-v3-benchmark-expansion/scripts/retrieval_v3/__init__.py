"""S5-v3 modular retrieval engineering package (all 9 improvements, frozen v2.1 untouched)."""

from __future__ import annotations

from retrieval_v3.config import (
    EDGE_TYPE_WEIGHTS,
    SCHEMA_VERSION,
    RetrievalV3Config,
    build_standard_v3_variants,
)
from retrieval_v3.corpus_grounding import (
    GroundedGraphIndex,
    build_corpus_grounded_index,
    load_corpus_v3_passages,
    load_okf_graph,
)
from retrieval_v3.engine import RetrievalV3Engine, aggregate_variant_diagnostics
from retrieval_v3.instrumentation import measure_call, summarize_telemetry
from retrieval_v3.lexical import BM25LexicalControl
from retrieval_v3.normalization import (
    CURATED_TECHNICAL_ALIASES,
    AnchorMatch,
    ConceptAnchorMatcher,
    extract_content_tokens,
    normalize_technical_text,
    singularize_token,
    tokenize_alnum,
)
from retrieval_v3.types import (
    ConceptPassageLink,
    CorpusPassage,
    GraphConcept,
    GraphEdge,
    QueryProvenance,
    QueryResult,
    QueryTimingMemory,
    RankedPassage,
    TraversalStep,
)

__all__ = [
    "CURATED_TECHNICAL_ALIASES",
    "EDGE_TYPE_WEIGHTS",
    "SCHEMA_VERSION",
    "AnchorMatch",
    "BM25LexicalControl",
    "ConceptAnchorMatcher",
    "ConceptPassageLink",
    "CorpusPassage",
    "GraphConcept",
    "GraphEdge",
    "GroundedGraphIndex",
    "QueryProvenance",
    "QueryResult",
    "QueryTimingMemory",
    "RankedPassage",
    "RetrievalV3Config",
    "RetrievalV3Engine",
    "TraversalStep",
    "aggregate_variant_diagnostics",
    "build_corpus_grounded_index",
    "build_standard_v3_variants",
    "extract_content_tokens",
    "load_corpus_v3_passages",
    "load_okf_graph",
    "measure_call",
    "normalize_technical_text",
    "singularize_token",
    "summarize_telemetry",
    "tokenize_alnum",
]
