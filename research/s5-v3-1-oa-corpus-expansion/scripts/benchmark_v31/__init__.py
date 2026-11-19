"""S5-v3.1 Stage D multi-domain benchmark & human query-audit package."""

from __future__ import annotations

from .audit_validator import (
    AuditValidationIssue,
    AuditValidationResult,
    validate_blank_workbook,
    validate_completed_submission,
)
from .audit_workbook import (
    build_audit_json_schema,
    generate_private_audit_workbooks,
)
from .builder import QueryDraft, build_benchmark_manifest, write_manifest
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
    "AuditValidationIssue",
    "AuditValidationResult",
    "CorpusPassageMeta",
    "EvidenceRef",
    "GraphAnchorIndex",
    "QueryDraft",
    "QuerySpec",
    "ShortcutCheck",
    "ValidationIssue",
    "ValidationReport",
    "build_audit_json_schema",
    "build_benchmark_manifest",
    "check_dev_test_leakage",
    "check_v21_reuse",
    "compute_file_sha256",
    "generate_private_audit_workbooks",
    "load_corpus_metadata",
    "load_v21_queries",
    "normalize_phrase",
    "token_jaccard",
    "validate_benchmark",
    "validate_blank_workbook",
    "validate_completed_submission",
    "write_manifest",
]
