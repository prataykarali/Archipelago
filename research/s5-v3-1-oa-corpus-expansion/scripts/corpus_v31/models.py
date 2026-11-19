"""Typed immutable data models for S5-v3.1 Corpus v3.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SourceLicenseRecord:
    """Verified provenance and license audit record for one Corpus v3.1 source."""

    doc_id: str
    domain: str
    title: str
    authors: str
    publisher: str
    version_or_commit: str
    license_id: str
    license_url: str
    license_exceptions: str
    redistribution_permission: str
    official_url: str
    download_url: str
    download_timestamp_utc: str
    local_raw_path: str
    source_sha256: str
    source_format: str
    provenance_class: str
    origin_tier: str
    retrieval_status: str
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serialize source license record to JSON-compatible dict."""
        return asdict(self)


@dataclass(frozen=True)
class ExtractedUnit:
    """Atomic extracted section/page unit prior to chunking."""

    section_heading: str
    section_ref: str
    page_number: int | None
    text: str


@dataclass(frozen=True)
class CorpusV31Passage:
    """Canonical Corpus v3.1 passage with honest provenance and zero fabricated pages."""

    passage_id: str
    source_doc_id: str
    source_title: str
    domain: str
    origin_tier: str
    provenance_class: str
    license_id: str
    redistribution_permission: str
    source_sha256: str
    page_start: int | None
    page_end: int | None
    section_ref: str
    section_heading: str
    chunk_index: int
    text: str
    char_count: int
    token_count: int
    normalized_text_sha256: str
    passage_sha256: str
    quality_flags: tuple[str, ...]
    is_usable: bool
    is_exact_duplicate: bool
    is_near_duplicate: bool
    canonical_passage_id: str
    split_assignment: str

    def to_jsonl_dict(self) -> dict[str, object]:
        """Serialize passage record to canonical JSONL dictionary."""
        data = asdict(self)
        data["quality_flags"] = list(self.quality_flags)
        return data


@dataclass(frozen=True)
class DuplicatePair:
    """Exact or near-duplicate link between two passage IDs."""

    passage_id: str
    matched_passage_id: str
    kind: str
    similarity: float


@dataclass(frozen=True)
class ExtractionAuditStats:
    """Per-source extraction and filtering accounting."""

    doc_id: str
    raw_units: int
    candidate_chunks: int
    dropped_boilerplate_or_bib: int
    dropped_malformed_or_short: int
    dropped_exact_duplicates: int
    dropped_near_duplicates: int
    retained_passages: int

    def to_dict(self) -> dict[str, object]:
        """Serialize extraction audit stats."""
        return asdict(self)
