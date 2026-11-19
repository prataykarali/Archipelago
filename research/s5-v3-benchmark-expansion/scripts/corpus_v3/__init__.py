"""S5-v3 Corpus v3 deterministic extraction, audit, and manifest package."""

from __future__ import annotations

from .builder import LeakageGuardError, build_corpus_v3, load_default_source_specs
from .chunking import RawChunk, chunk_pages
from .dedup import (
    compute_jaccard_similarity,
    compute_normalized_sha256,
    compute_passage_sha256,
    detect_duplicates,
    normalize_for_dedup,
)
from .extractors import (
    SourceEligibilityError,
    clean_extracted_text,
    compute_file_sha256,
    extract_document,
    validate_source_eligibility,
)
from .leakage import verify_leakage_guard
from .models import (
    DeduplicationReport,
    DocumentCompleteness,
    DuplicatePair,
    LeakageCheckResult,
    PageText,
    PassageRecord,
    QualityAssessment,
    SourceDocumentSpec,
)
from .quality import assess_passage_quality, count_tokens

__all__ = [
    "DeduplicationReport",
    "DocumentCompleteness",
    "DuplicatePair",
    "LeakageCheckResult",
    "LeakageGuardError",
    "PageText",
    "PassageRecord",
    "QualityAssessment",
    "RawChunk",
    "SourceDocumentSpec",
    "SourceEligibilityError",
    "assess_passage_quality",
    "build_corpus_v3",
    "chunk_pages",
    "clean_extracted_text",
    "compute_file_sha256",
    "compute_jaccard_similarity",
    "compute_normalized_sha256",
    "compute_passage_sha256",
    "count_tokens",
    "detect_duplicates",
    "extract_document",
    "load_default_source_specs",
    "normalize_for_dedup",
    "validate_source_eligibility",
    "verify_leakage_guard",
]
