"""S5-v3 Module C benchmark builder and validation package."""

from __future__ import annotations

from .corpus_index import compute_file_sha256, load_corpus_metadata
from .graph_anchors import GraphAnchorIndex, normalize_phrase
from .leakage import (
    check_dev_test_leakage,
    check_v21_reuse,
    load_v21_queries,
    token_jaccard,
)
from .schema import (
    CorpusPassageMeta,
    EvidenceRef,
    QuerySpec,
    ShortcutCheck,
    ValidationIssue,
    ValidationReport,
)
from .validator import validate_benchmark

__all__ = [
    "CorpusPassageMeta",
    "EvidenceRef",
    "GraphAnchorIndex",
    "QuerySpec",
    "ShortcutCheck",
    "ValidationIssue",
    "ValidationReport",
    "check_dev_test_leakage",
    "check_v21_reuse",
    "compute_file_sha256",
    "load_corpus_metadata",
    "load_v21_queries",
    "normalize_phrase",
    "token_jaccard",
    "validate_benchmark",
]
