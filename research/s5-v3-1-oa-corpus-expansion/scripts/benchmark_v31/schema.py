"""Typed schema structures for the S5-v3.1 proposed query benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceRef:
    """Metadata-only reference to a verified Corpus v3.1 passage."""

    passage_id: str
    source_doc_id: str
    domain: str
    page_start: int | None
    page_end: int | None
    section_ref: str
    passage_sha256: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EvidenceRef:
        """Deserialize from a dictionary."""
        ps = raw.get("page_start")
        pe = raw.get("page_end")
        return cls(
            passage_id=str(raw["passage_id"]),
            source_doc_id=str(raw["source_doc_id"]),
            domain=str(raw.get("domain", "")),
            page_start=None if ps is None else int(ps),
            page_end=None if pe is None else int(pe),
            section_ref=str(raw.get("section_ref", "")),
            passage_sha256=str(raw["passage_sha256"]),
        )


@dataclass(frozen=True)
class ShortcutCheck:
    """Audit record for single-passage shortcut falsification."""

    shortcut_found: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ShortcutCheck:
        """Deserialize from a dictionary."""
        return cls(
            shortcut_found=bool(raw["shortcut_found"]),
            rationale=str(raw["rationale"]),
        )


@dataclass(frozen=True)
class QuerySpec:
    """One proposed S5-v3.1 query with provisional status and audit fields."""

    query_id: str
    query_text: str
    split: str
    category: str
    category_status: str
    domain: str
    domain_topic: str
    origin_v3_query_id: str | None
    graph_anchor_regime: str
    graph_matched_concepts: tuple[str, ...]
    exact_information_need: str
    supporting_evidence: tuple[EvidenceRef, ...]
    answer_exists_in_eligible_corpus: bool
    answerability_verification_status: str
    minimum_required_evidence_set: tuple[str, ...]
    multi_document_truly_necessary: bool
    necessity_status: str
    single_passage_shortcut_check: ShortcutCheck
    premise_audit_flags: tuple[str, ...]
    provenance_status: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary (metadata-only)."""
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "split": self.split,
            "category": self.category,
            "category_status": self.category_status,
            "domain": self.domain,
            "domain_topic": self.domain_topic,
            "origin_v3_query_id": self.origin_v3_query_id,
            "graph_anchor_regime": self.graph_anchor_regime,
            "graph_matched_concepts": list(self.graph_matched_concepts),
            "exact_information_need": self.exact_information_need,
            "supporting_evidence": [
                ref.to_dict() for ref in self.supporting_evidence
            ],
            "answer_exists_in_eligible_corpus": (
                self.answer_exists_in_eligible_corpus
            ),
            "answerability_verification_status": (
                self.answerability_verification_status
            ),
            "minimum_required_evidence_set": list(
                self.minimum_required_evidence_set
            ),
            "multi_document_truly_necessary": (
                self.multi_document_truly_necessary
            ),
            "necessity_status": self.necessity_status,
            "single_passage_shortcut_check": (
                self.single_passage_shortcut_check.to_dict()
            ),
            "premise_audit_flags": list(self.premise_audit_flags),
            "provenance_status": self.provenance_status,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> QuerySpec:
        """Deserialize from a dictionary."""
        orig = raw.get("origin_v3_query_id")
        return cls(
            query_id=str(raw["query_id"]),
            query_text=str(raw["query_text"]),
            split=str(raw["split"]),
            category=str(raw["category"]),
            category_status=str(raw["category_status"]),
            domain=str(raw["domain"]),
            domain_topic=str(raw["domain_topic"]),
            origin_v3_query_id=None if orig is None else str(orig),
            graph_anchor_regime=str(raw["graph_anchor_regime"]),
            graph_matched_concepts=tuple(
                str(c) for c in raw.get("graph_matched_concepts", [])
            ),
            exact_information_need=str(raw["exact_information_need"]),
            supporting_evidence=tuple(
                EvidenceRef.from_dict(item)
                for item in raw.get("supporting_evidence", [])
            ),
            answer_exists_in_eligible_corpus=bool(
                raw["answer_exists_in_eligible_corpus"]
            ),
            answerability_verification_status=str(
                raw["answerability_verification_status"]
            ),
            minimum_required_evidence_set=tuple(
                str(pid)
                for pid in raw.get("minimum_required_evidence_set", [])
            ),
            multi_document_truly_necessary=bool(
                raw["multi_document_truly_necessary"]
            ),
            necessity_status=str(raw["necessity_status"]),
            single_passage_shortcut_check=ShortcutCheck.from_dict(
                raw["single_passage_shortcut_check"]
            ),
            premise_audit_flags=tuple(
                str(flag) for flag in raw.get("premise_audit_flags", [])
            ),
            provenance_status=str(raw["provenance_status"]),
        )


@dataclass(frozen=True)
class CorpusPassageMeta:
    """Minimal metadata extracted from a Corpus v3.1 JSONL record."""

    passage_id: str
    source_doc_id: str
    domain: str
    page_start: int | None
    page_end: int | None
    section_ref: str
    passage_sha256: str
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationIssue:
    """Single validation error or warning produced during benchmark audit."""

    severity: str
    query_id: str
    code: str
    message: str


@dataclass
class ValidationReport:
    """Aggregated validation results for a proposed S5-v3.1 benchmark."""

    issues: list[ValidationIssue] = field(default_factory=list)
    total_queries: int = 0
    split_counts: dict[str, int] = field(default_factory=dict)
    category_counts: dict[str, int] = field(default_factory=dict)
    domain_counts: dict[str, int] = field(default_factory=dict)
    regime_counts: dict[str, int] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        """Return number of error-level issues."""
        return sum(1 for item in self.issues if item.severity == "ERROR")

    @property
    def is_valid(self) -> bool:
        """Return True when zero error-level issues were found."""
        return self.error_count == 0
