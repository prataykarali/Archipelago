"""Data models and provenance helpers for the frozen eligible corpus."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .constants import (
    ELIGIBILITY_ELIGIBLE,
    ELIGIBILITY_OUT_OF_CORPUS,
    TIER_CONSTRUCTED_PILOT_CARD,
    TIER_PAPER_OR_UPLOAD_CHUNK,
    TIER_SEED_CHUNK,
    TIER_TRUNCATED_TEXTBOOK_STUB,
)

_INDEX_DOC_RE = re.compile(
    r"(?:^|/)(?:index|about[-_]the[-_]authors|table[-_]of[-_]contents)[_/-]",
    re.IGNORECASE,
)
_INDEX_LINE_NUM_RE = re.compile(r"\b\d{1,4}(?:,\s*\d{1,4}){4,}")
_INDEX_SECTION_TITLES: frozenset[str] = frozenset(
    {
        "index",
        "subject index",
        "author index",
        "about the authors",
        "table of contents",
    }
)
_INDEX_LINE_MIN_MATCHES = 3
_INDEX_TEXT_MAX_CHARS = 2500


class CorpusEligibilityError(ValueError):
    """Raised when an operation references an excluded or out-of-corpus passage/doc."""

    def __init__(self, message: str, *, status: str = ELIGIBILITY_OUT_OF_CORPUS) -> None:
        super().__init__(message)
        self.status = status


def is_index_only_passage(doc_id: str, section_title: str, text: str) -> bool:
    """Return True if a passage matches the frozen S5 index/frontmatter exclusion rule."""
    if _INDEX_DOC_RE.search(doc_id):
        return True
    if section_title.strip().lower() in _INDEX_SECTION_TITLES:
        return True
    return (
        len(_INDEX_LINE_NUM_RE.findall(text)) >= _INDEX_LINE_MIN_MATCHES
        and len(text) < _INDEX_TEXT_MAX_CHARS
    )


def derive_source_title(doc_id: str, section_title: str) -> str:
    """Derive a clean human-readable source title from canonical doc_id/section."""
    base = doc_id.rsplit("/", maxsplit=1)[-1]
    if base.endswith((".pdf", ".txt")):
        base = base.rsplit(".", maxsplit=1)[0]
    cleaned = base.replace("_", " ").strip()
    if section_title.strip():
        return f"{cleaned} — {section_title.strip()}"
    return cleaned or doc_id


def compute_text_sha256(text: str) -> str:
    """Return SHA-256 hex digest of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_provenance_tier_map(registry_path: Path | None) -> dict[str, str]:
    """Load passage_id -> provenance_tier mapping from the corpus provenance registry."""
    if registry_path is None or not registry_path.exists():
        return {}
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    tier_map: dict[str, str] = {}
    for pid in data.get("source_verified_constructed_pilot_cards", []):
        tier_map[str(pid)] = TIER_CONSTRUCTED_PILOT_CARD
    for pid in data.get("source_verified_truncated_textbook_stubs", []):
        tier_map[str(pid)] = TIER_TRUNCATED_TEXTBOOK_STUB
    for pid in data.get("convention_inferred_seed_chunks", []):
        tier_map[str(pid)] = TIER_SEED_CHUNK
    return tier_map


@dataclass(frozen=True)
class EligiblePassage:
    """A single provenance-verified passage belonging strictly to the frozen eligible corpus."""

    passage_id: str
    doc_id: str
    chunk_id: str
    page_number: int
    section_title: str
    text: str
    content_sha256: str
    source_title: str
    provenance_tier: str = TIER_PAPER_OR_UPLOAD_CHUNK
    corpus_eligibility_status: str = ELIGIBILITY_ELIGIBLE

    def to_canonical_dict(self) -> dict[str, Any]:
        """Return canonical 7-field dict matching s5a_eval_corpus_v1 hash contract."""
        return {
            "passage_id": self.passage_id,
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "text": self.text,
            "content_sha256": self.content_sha256,
        }

    def to_metadata_dict(self) -> dict[str, Any]:
        """Return full metadata dict including provenance and eligibility."""
        return asdict(self)


@dataclass(frozen=True)
class SearchHit:
    """A single corpus-restricted search hit with full provenance."""

    passage_id: str
    doc_id: str
    source_title: str
    content_sha256: str
    chunk_id: str
    page_number: int
    corpus_eligibility_status: str
    provenance_tier: str
    matched_excerpt: str
    full_text: str
    match_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchResult:
    """Structured result of a corpus-wide search strictly over eligible passages."""

    query_used: str
    mode: str
    doc_filter: str | None
    corpus_version: str
    corpus_sha256: str
    total_hits: int
    hits: tuple[SearchHit, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_used": self.query_used,
            "mode": self.mode,
            "doc_filter": self.doc_filter,
            "corpus_version": self.corpus_version,
            "corpus_sha256": self.corpus_sha256,
            "total_hits": self.total_hits,
            "hits": [h.to_dict() for h in self.hits],
        }


def compute_corpus_sha256(passages: Sequence[EligiblePassage]) -> str:
    """Compute canonical SHA-256 matching build_s5c3_private_packages.py."""
    payload = [p.to_canonical_dict() for p in passages]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
