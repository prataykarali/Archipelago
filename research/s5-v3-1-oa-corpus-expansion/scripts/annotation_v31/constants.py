"""Named constants for the S5-v3.1 versioned annotation workbench."""

from __future__ import annotations

BENCHMARK_VERSION: str = "s5v3.1"
SUBMISSION_SCHEMA_VERSION: str = "s5v31_human_annotation_submission_v1"
PROVENANCE_INDEPENDENT_HUMAN: str = "INDEPENDENT_HUMAN"
ASSISTANCE_NONE_HUMAN: str = "NONE_INDEPENDENT_HUMAN"

VALID_GRADES: frozenset[int] = frozenset({0, 1, 2})
GRADE_REQUIRES_QUOTE_MIN: int = 1
MIN_QUOTATION_CHARS: int = 8
HASH_READ_CHUNK_BYTES: int = 65536

DOMAIN_GROUP_MATH_ML: str = "math_ml"
DOMAIN_GROUP_CS_SYSTEMS: str = "cs_systems"
DOMAIN_GROUP_ALL: str = "all"
VALID_DOMAIN_GROUPS: frozenset[str] = frozenset(
    {DOMAIN_GROUP_MATH_ML, DOMAIN_GROUP_CS_SYSTEMS, DOMAIN_GROUP_ALL}
)

MATH_ML_DOMAINS: frozenset[str] = frozenset(
    {
        "Machine Learning",
        "Math for ML",
        "Mathematics for ML",
        "NLP / LLMs",
        "Robotics / Control",
        "Cross-Domain (ML/Math/NLP/Robotics)",
    }
)
CS_SYSTEMS_DOMAINS: frozenset[str] = frozenset(
    {
        "Operating Systems",
        "Databases",
        "Computer Networks",
        "Distributed Systems",
        "Cross-Domain (CS Systems)",
    }
)

BLINDED_FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "system_id",
        "system_name",
        "systems",
        "rank",
        "ranks",
        "score",
        "scores",
        "rrf_score",
        "bm25_score",
        "dense_score",
        "ai_hint",
        "ai_grade",
        "expected_grade",
        "fallback_triggered",
    }
)

LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost"})
DEFAULT_BIND_HOST: str = "127.0.0.1"
DEFAULT_BIND_PORT: int = 8766

DEFAULT_CORPUS_V31_JSONL: str = (
    "data/annotation_local/s5v3_1/corpus_v31/s5v31_corpus_passages.jsonl"
)
DEFAULT_WORKBENCH_DIR: str = "data/annotation_local/s5v3_1/workbench"
