"""Typed data models for S5-v3 Corpus v3 extraction, auditing, and manifests."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SourceDocumentSpec:
    """Verified metadata and eligibility policy for one candidate source."""

    doc_id: str
    path: str
    title: str
    source_format: str
    domain: str
    provenance_class: str
    license_id: str
    redistribution_permission: str
    expected_sha256: str
    source_url: str
    eligible: bool = True
    exclusion_reason: str = ""


@dataclass(frozen=True)
class PageText:
    """Extracted text for a single 1-based page (or markdown logical page)."""

    page_number: int
    raw_text: str
    cleaned_text: str
    char_count: int
    had_ligature_repairs: bool
    had_encoding_artifacts: bool


@dataclass(frozen=True)
class DocumentCompleteness:
    """Extraction completeness metrics for one source document."""

    doc_id: str
    source_format: str
    total_pages: int
    non_empty_pages: int
    empty_pages: tuple[int, ...]
    total_chars: int
    mean_chars_per_non_empty_page: float
    pages_with_ligature_repairs: int
    pages_with_encoding_artifacts: int


@dataclass(frozen=True)
class QualityAssessment:
    """Deterministic extraction-quality verdict for a single passage."""

    flags: tuple[str, ...]
    quality_score: float
    is_usable: bool


@dataclass(frozen=True)
class PassageRecord:
    """Canonical Corpus v3 passage with page-level provenance and audit metadata."""

    passage_id: str
    source_doc_id: str
    source_title: str
    domain: str
    provenance_class: str
    license_id: str
    redistribution_permission: str
    source_sha256: str
    page_start: int
    page_end: int
    chunk_index: int
    section_heading: str
    text: str
    char_count: int
    token_count: int
    normalized_text_sha256: str
    passage_sha256: str
    quality_flags: tuple[str, ...]
    quality_score: float
    is_usable: bool
    is_exact_duplicate: bool
    canonical_passage_id: str
    split_assignment: str

    def to_jsonl_dict(self) -> dict[str, object]:
        """Serialize passage record to JSON-compatible dict."""
        data = asdict(self)
        data["quality_flags"] = list(self.quality_flags)
        return data


@dataclass(frozen=True)
class DuplicatePair:
    """Exact or near-duplicate relationship between two passages."""

    passage_id: str
    matched_passage_id: str
    kind: str
    similarity: float


@dataclass(frozen=True)
class DeduplicationReport:
    """Summary of exact and near-duplicate analysis over a passage list."""

    total_passages: int
    unique_normalized_hashes: int
    exact_duplicate_count: int
    exact_duplicate_pairs: tuple[DuplicatePair, ...]
    near_duplicate_count: int
    near_duplicate_pairs: tuple[DuplicatePair, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize deduplication report for manifest output."""
        return {
            "total_passages": self.total_passages,
            "unique_normalized_hashes": self.unique_normalized_hashes,
            "exact_duplicate_count": self.exact_duplicate_count,
            "exact_duplicate_pairs": [asdict(p) for p in self.exact_duplicate_pairs],
            "near_duplicate_count": self.near_duplicate_count,
            "near_duplicate_pairs": [asdict(p) for p in self.near_duplicate_pairs],
        }


@dataclass(frozen=True)
class LeakageCheckResult:
    """Result of train/dev/test and forbidden-hash leakage enforcement."""

    passed: bool
    violations: tuple[str, ...]
    split_counts: dict[str, int]
    cross_split_exact_hash_overlaps: int
    cross_split_near_dup_overlaps: int
    cross_split_doc_overlaps: int
    forbidden_hash_overlaps: int

    def to_dict(self) -> dict[str, object]:
        """Serialize leakage check result for manifest output."""
        return {
            "passed": self.passed,
            "violations": list(self.violations),
            "split_counts": dict(self.split_counts),
            "cross_split_exact_hash_overlaps": self.cross_split_exact_hash_overlaps,
            "cross_split_near_dup_overlaps": self.cross_split_near_dup_overlaps,
            "cross_split_doc_overlaps": self.cross_split_doc_overlaps,
            "forbidden_hash_overlaps": self.forbidden_hash_overlaps,
        }
