"""S5-v3.1 Corpus v3.1 expansion package (Stages A & B)."""

from __future__ import annotations

from .builder import (
    CorpusV31BuildError,
    build_corpus_v31,
    build_default_new_oa_source_records,
    load_prior_v3_eligible_passages,
)
from .extractors import (
    ForbiddenSourceError,
    check_not_forbidden,
    compute_directory_sha256,
    compute_file_sha256,
    extract_epub_units,
    extract_latex_units,
    extract_libretexts_html_units,
    extract_pdf_units,
)
from .models import (
    CorpusV31Passage,
    DuplicatePair,
    ExtractedUnit,
    ExtractionAuditStats,
    SourceLicenseRecord,
)
from .quality_dedup import (
    CandidateChunk,
    chunk_extracted_units,
    classify_chunk_rejection,
    compute_normalized_sha256,
    compute_passage_sha256,
    find_near_duplicates,
)

__all__ = [
    "CandidateChunk",
    "CorpusV31BuildError",
    "CorpusV31Passage",
    "DuplicatePair",
    "ExtractedUnit",
    "ExtractionAuditStats",
    "ForbiddenSourceError",
    "SourceLicenseRecord",
    "build_corpus_v31",
    "build_default_new_oa_source_records",
    "check_not_forbidden",
    "chunk_extracted_units",
    "classify_chunk_rejection",
    "compute_directory_sha256",
    "compute_file_sha256",
    "compute_normalized_sha256",
    "compute_passage_sha256",
    "extract_epub_units",
    "extract_latex_units",
    "extract_libretexts_html_units",
    "extract_pdf_units",
    "find_near_duplicates",
    "load_prior_v3_eligible_passages",
]
