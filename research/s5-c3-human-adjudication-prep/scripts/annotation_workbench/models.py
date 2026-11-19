"""Data models and deterministic hashing helpers for the S5-C3 annotation workbench."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import re
from typing import Any

from .constants import (
    DEFAULT_EVIDENCE_SOURCE_LABEL,
    HUMAN_ATTESTATION_STATEMENT,
    SESSION_SCHEMA_VERSION,
)


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with second precision."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_timestamp_compact() -> str:
    """Return a filesystem-safe UTC timestamp with microsecond precision."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def content_hash(text: str) -> str:
    """Deterministic SHA-256 over whitespace-normalized lowercase text.

    Matches `archipelago.eval.retrieval_baselines.content_hash` exactly.
    """
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return lowercase hex SHA-256 digest for raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return lowercase hex SHA-256 digest for a file on disk."""
    return sha256_bytes(path.read_bytes())


@dataclass(frozen=True)
class CandidatePair:
    """Immutable blinded candidate query-passage pair loaded from the frozen pool."""

    pair_id: str
    pair_index: int
    presentation_order: int
    query_id: str
    domain: str
    query_text: str
    candidate_passage_id: str
    candidate_doc_id: str
    candidate_chunk_id: str
    candidate_page_number: int
    passage_sha256: str
    passage_text: str

    def to_public_dict(self) -> dict[str, Any]:
        """Serialize pair metadata and read-only passage text for local UI rendering."""
        return {
            "pair_id": self.pair_id,
            "pair_index": self.pair_index,
            "presentation_order": self.presentation_order,
            "query_id": self.query_id,
            "domain": self.domain,
            "query_text": self.query_text,
            "candidate_passage_id": self.candidate_passage_id,
            "candidate_doc_id": self.candidate_doc_id,
            "candidate_chunk_id": self.candidate_chunk_id,
            "candidate_page_number": self.candidate_page_number,
            "passage_sha256": self.passage_sha256,
            "passage_text": self.passage_text,
        }


@dataclass(frozen=True)
class LoadedPool:
    """Frozen blinded pool plus hydrated, hash-verified candidate pairs."""

    pool_path: Path
    pool_version: str
    pool_sha256: str
    randomization_seed: int
    passage_source: str
    pairs: tuple[CandidatePair, ...]
    pairs_by_id: dict[str, CandidatePair]
    query_order: tuple[str, ...]


@dataclass
class JudgmentRecord:
    """Human judgment entered for a single blinded candidate pair."""

    pair_id: str
    relevance_grade: int | None = None
    supporting_quotation: str = ""
    confidence: str = ""
    reviewer_notes: str = ""
    flagged: bool = False
    updated_at_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize judgment fields to JSON-compatible dictionary."""
        return {
            "pair_id": self.pair_id,
            "relevance_grade": self.relevance_grade,
            "supporting_quotation": self.supporting_quotation,
            "confidence": self.confidence,
            "reviewer_notes": self.reviewer_notes,
            "flagged": self.flagged,
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def from_dict(cls, pair_id: str, payload: dict[str, Any]) -> JudgmentRecord:
        """Deserialize judgment record from stored JSON."""
        raw_grade = payload.get("relevance_grade")
        grade: int | None
        if raw_grade is None or raw_grade == "" or isinstance(raw_grade, bool):
            grade = None
        else:
            grade = int(raw_grade)
        return cls(
            pair_id=pair_id,
            relevance_grade=grade,
            supporting_quotation=str(payload.get("supporting_quotation") or ""),
            confidence=str(payload.get("confidence") or "").strip().upper(),
            reviewer_notes=str(payload.get("reviewer_notes") or ""),
            flagged=bool(payload.get("flagged", False)),
            updated_at_utc=str(payload.get("updated_at_utc") or ""),
        )


@dataclass
class ProvenanceDeclaration:
    """Truthful human provenance declaration. Never auto-populated or auto-signed."""

    reviewer_identity_or_pseudonym: str = ""
    provenance_class: str = ""
    assistance_declaration: str = ""
    human_attestation_confirmed: bool = False
    attestation_statement: str = HUMAN_ATTESTATION_STATEMENT
    review_start_date_utc: str = ""
    review_completion_date_utc: str = ""
    signed_by_human_at_utc: str = ""
    evidence_source_used: str = DEFAULT_EVIDENCE_SOURCE_LABEL

    def to_dict(self) -> dict[str, Any]:
        """Serialize provenance declaration to JSON-compatible dictionary."""
        return {
            "reviewer_identity_or_pseudonym": self.reviewer_identity_or_pseudonym,
            "provenance_class": self.provenance_class,
            "assistance_declaration": self.assistance_declaration,
            "human_attestation_confirmed": self.human_attestation_confirmed,
            "attestation_statement": self.attestation_statement,
            "review_start_date_utc": self.review_start_date_utc,
            "review_completion_date_utc": self.review_completion_date_utc,
            "signed_by_human_at_utc": self.signed_by_human_at_utc,
            "evidence_source_used": self.evidence_source_used,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProvenanceDeclaration:
        """Deserialize provenance declaration without auto-filling or auto-signing."""
        return cls(
            reviewer_identity_or_pseudonym=str(
                payload.get("reviewer_identity_or_pseudonym") or ""
            ).strip(),
            provenance_class=str(payload.get("provenance_class") or "").strip(),
            assistance_declaration=str(
                payload.get("assistance_declaration") or ""
            ).strip(),
            human_attestation_confirmed=bool(
                payload.get("human_attestation_confirmed", False)
            ),
            attestation_statement=str(
                payload.get("attestation_statement") or HUMAN_ATTESTATION_STATEMENT
            ),
            review_start_date_utc=str(
                payload.get("review_start_date_utc") or ""
            ).strip(),
            review_completion_date_utc=str(
                payload.get("review_completion_date_utc") or ""
            ).strip(),
            signed_by_human_at_utc=str(
                payload.get("signed_by_human_at_utc") or ""
            ).strip(),
            evidence_source_used=str(
                payload.get("evidence_source_used") or DEFAULT_EVIDENCE_SOURCE_LABEL
            ).strip(),
        )


@dataclass
class AnnotationSession:
    """Persistent private annotation session for a single human reviewer."""

    schema_version: str = SESSION_SCHEMA_VERSION
    pool_version: str = ""
    pool_sha256: str = ""
    created_at_utc: str = field(default_factory=utc_now_iso)
    updated_at_utc: str = field(default_factory=utc_now_iso)
    provenance: ProvenanceDeclaration = field(default_factory=ProvenanceDeclaration)
    judgments: dict[str, JudgmentRecord] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize full session state for atomic disk persistence."""
        return {
            "schema_version": self.schema_version,
            "pool_version": self.pool_version,
            "pool_sha256": self.pool_sha256,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "provenance": self.provenance.to_dict(),
            "judgments": {
                pid: rec.to_dict() for pid, rec in sorted(self.judgments.items())
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AnnotationSession:
        """Deserialize session state from JSON."""
        raw_judgments = payload.get("judgments") or {}
        judgments = {
            pid: JudgmentRecord.from_dict(pid, rec)
            for pid, rec in raw_judgments.items()
            if isinstance(rec, dict)
        }
        raw_prov = payload.get("provenance")
        prov = (
            ProvenanceDeclaration.from_dict(raw_prov)
            if isinstance(raw_prov, dict)
            else ProvenanceDeclaration()
        )
        return cls(
            schema_version=str(payload.get("schema_version") or SESSION_SCHEMA_VERSION),
            pool_version=str(payload.get("pool_version") or ""),
            pool_sha256=str(payload.get("pool_sha256") or ""),
            created_at_utc=str(payload.get("created_at_utc") or utc_now_iso()),
            updated_at_utc=str(payload.get("updated_at_utc") or utc_now_iso()),
            provenance=prov,
            judgments=judgments,
        )
