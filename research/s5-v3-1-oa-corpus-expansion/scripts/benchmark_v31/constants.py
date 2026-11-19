"""Named constants for the S5-v3.1 multi-domain proposed query benchmark."""

from __future__ import annotations

SCHEMA_VERSION: str = "s5v31_query_benchmark_proposed_v1"
PROVISIONAL_STATUS: str = "PROVISIONAL_PENDING_HUMAN_VERIFICATION"
PROVENANCE_STATUS_PROPOSED: str = (
    "AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION"
)
ANSWERABILITY_STATUS_UNVERIFIED: str = (
    "CANDIDATE_UNVERIFIED_REQUIRES_HUMAN_AUDIT"
)

AUDIT_SCHEMA_VERSION: str = "s5v31_human_query_audit_v1"
WORKBOOK_STATUS_BLANK: str = "BLANK_AWAITING_INDEPENDENT_HUMAN_AUDIT"
WORKBOOK_STATUS_SUBMITTED: str = "SUBMITTED_INDEPENDENT_HUMAN_AUDIT"
BLINDING_SALT: str = "s5v31-query-audit-blind-v1"

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

DECISION_ACCEPT: str = "ACCEPT"
DECISION_REVISE: str = "REVISE"
DECISION_REJECT: str = "REJECT"
VALID_HUMAN_DECISIONS: frozenset[str] = frozenset(
    {DECISION_ACCEPT, DECISION_REVISE, DECISION_REJECT}
)
VALID_TRI_STATE: frozenset[str] = frozenset({"YES", "NO", "NA"})
VALID_NC_CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "CONFIRMED_UNANSWERABLE",
        "PARTIALLY_ANSWERABLE_IN_CORPUS",
        "ANSWERABLE_IN_CORPUS",
        "NOT_APPLICABLE_POSITIVE_QUERY",
    }
)

MIN_QUERY_COUNT: int = 48
MAX_QUERY_COUNT: int = 96
MIN_MULTI_PASSAGE_EVIDENCE: int = 2
MIN_CROSS_DOC_SOURCES: int = 2
GRAPH_RICH_MIN_ANCHORS: int = 2
MIN_CONCEPT_MATCH_CHARS: int = 4
MIN_QUERY_TOKENS: int = 4
SHA256_HEX_LENGTH: int = 64
HASH_READ_CHUNK_BYTES: int = 65536
EXCERPT_MAX_CHARS: int = 700
MIN_RATIONALE_CHARS: int = 8

DEV_TEST_JACCARD_THRESHOLD: float = 0.65
V21_REUSE_JACCARD_THRESHOLD: float = 0.55

FORBIDDEN_PUBLIC_TEXT_KEYS: frozenset[str] = frozenset(
    {
        "text",
        "passage_text",
        "passage_excerpt",
        "raw_text",
        "chunk_text",
        "full_text",
    }
)
FORBIDDEN_RELEVANCE_GRADE_KEYS: frozenset[str] = frozenset(
    {
        "relevance_grade",
        "grade",
        "final_grade",
        "reviewer_a_grade",
        "reviewer_b_grade",
        "reviewer_c_grade",
        "relevance_score",
        "human_grade",
    }
)
BLINDED_HIDDEN_KEYS: frozenset[str] = frozenset(
    {"split", "graph_anchor_regime", "graph_matched_concepts"}
)

DEFAULT_CORPUS_V31_JSONL: str = (
    "data/annotation_local/s5v3_1/corpus_v31/s5v31_corpus_passages.jsonl"
)
DEFAULT_GRAPH_JSON: str = "okf_graph.json"
DEFAULT_V21_SPECS_JSON: str = (
    "research/s5-b2-benchmark-correction/corpus/"
    "s5b2_proposed_blinded_query_specs.json"
)
DEFAULT_V3_PROPOSED_JSON: str = (
    "research/s5-v3-benchmark-expansion/manifests/"
    "s5v3_query_benchmark_proposed.json"
)
DEFAULT_MANIFEST_OUTPUT: str = (
    "research/s5-v3-1-oa-corpus-expansion/manifests/"
    "s5v31_query_benchmark_proposed.json"
)
DEFAULT_AUDIT_SCHEMA_OUTPUT: str = (
    "research/s5-v3-1-oa-corpus-expansion/manifests/"
    "s5v31_query_audit_schema.json"
)
DEFAULT_PRIVATE_AUDIT_DIR: str = "data/annotation_local/s5v3_1/query_audit"
