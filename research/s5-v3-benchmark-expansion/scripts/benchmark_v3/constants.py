"""Named constants for the S5-v3 proposed query benchmark."""

from __future__ import annotations

SCHEMA_VERSION: str = "s5v3_query_benchmark_proposed_v1"
PROVENANCE_STATUS_PROPOSED: str = (
    "AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION"
)
ANSWERABILITY_STATUS_UNVERIFIED: str = (
    "CANDIDATE_UNVERIFIED_REQUIRES_HUMAN_AUDIT"
)
DEFERRED_DOMAIN_STATUS: str = "DEFERRED_PENDING_OA_SOURCE_INGESTION"

SPLIT_DEV: str = "dev"
SPLIT_TEST: str = "test"
VALID_SPLITS: frozenset[str] = frozenset({SPLIT_DEV, SPLIT_TEST})

CAT_SINGLE_PASSAGE: str = "single_passage_fact_concept"
CAT_SAME_DOC_MULTI: str = "same_doc_multi_passage"
CAT_CROSS_DOC_MULTI: str = "cross_doc_multi_passage"
CAT_TECH_PARAPHRASE: str = "technical_terminology_paraphrase"
CAT_NEGATIVE_CONTROL: str = "negative_control"
VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        CAT_SINGLE_PASSAGE,
        CAT_SAME_DOC_MULTI,
        CAT_CROSS_DOC_MULTI,
        CAT_TECH_PARAPHRASE,
        CAT_NEGATIVE_CONTROL,
    }
)

REGIME_SPARSE: str = "sparse"
REGIME_RICH: str = "rich"
VALID_GRAPH_REGIMES: frozenset[str] = frozenset({REGIME_SPARSE, REGIME_RICH})

DEFERRED_CS_DOMAINS: tuple[str, ...] = (
    "Operating Systems",
    "Databases",
    "Computer Networks",
    "Distributed Systems",
)

MIN_QUERY_COUNT: int = 40
MAX_QUERY_COUNT: int = 60
TARGET_QUERY_COUNT: int = 48
MIN_MULTI_PASSAGE_EVIDENCE: int = 2
MIN_CROSS_DOC_SOURCES: int = 2
GRAPH_RICH_MIN_ANCHORS: int = 2
MIN_CONCEPT_MATCH_CHARS: int = 4
MIN_QUERY_TOKENS: int = 4
SHA256_HEX_LENGTH: int = 64
HASH_READ_CHUNK_BYTES: int = 65536

DEV_TEST_JACCARD_THRESHOLD: float = 0.65
V21_REUSE_JACCARD_THRESHOLD: float = 0.55

FORBIDDEN_PUBLIC_TEXT_KEYS: frozenset[str] = frozenset(
    {"text", "passage_text", "raw_text", "chunk_text", "full_text"}
)

DEFAULT_CORPUS_JSONL: str = (
    "data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl"
)
DEFAULT_GRAPH_JSON: str = "okf_graph.json"
DEFAULT_V21_SPECS_JSON: str = (
    "research/s5-b2-benchmark-correction/corpus/"
    "s5b2_proposed_blinded_query_specs.json"
)
DEFAULT_MANIFEST_OUTPUT: str = (
    "research/s5-v3-benchmark-expansion/manifests/"
    "s5v3_query_benchmark_proposed.json"
)
