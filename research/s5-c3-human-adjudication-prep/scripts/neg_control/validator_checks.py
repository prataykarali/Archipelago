"""Helper checks for negative-control provenance and evidence validation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .constants import (
    ELIGIBILITY_ELIGIBLE,
    MIN_ATTESTATION_LENGTH,
    PROVENANCE_AI_ASSISTED,
    VALID_PROVENANCE_CLASSES,
)
from .corpus import CorpusEligibilityError, CorpusIndex

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"


@dataclass(frozen=True)
class ValidationIssue:
    """Single validation finding tied to a query or top-level worksheet."""

    severity: str
    query_id: str | None
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_valid_iso_utc(value: str) -> bool:
    """Return True if value parses as an ISO-8601 timestamp with timezone info."""
    cleaned = value.strip()
    if not cleaned:
        return False
    normalized = cleaned[:-1] + "+00:00" if cleaned.endswith("Z") else cleaned
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_provenance_block(
    query_id: str,
    prov: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    """Validate explicit human provenance and non-auto-signed attestation."""
    if not str(prov.get("verifier_id") or "").strip():
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                query_id,
                "MISSING_VERIFIER_ID",
                "human_provenance.verifier_id must be explicitly filled by the human verifier.",
            )
        )

    prov_class = prov.get("provenance_class")
    if prov_class not in VALID_PROVENANCE_CLASSES:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                query_id,
                "INVALID_PROVENANCE_CLASS",
                f"human_provenance.provenance_class must be one of "
                f"{sorted(VALID_PROVENANCE_CLASSES)}, got {prov_class!r}.",
            )
        )
    elif prov_class == PROVENANCE_AI_ASSISTED:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                query_id,
                "AI_ASSISTED_PROVENANCE_DISALLOWED",
                "AI_ASSISTED_OR_GENERATED verification cannot satisfy independent human "
                "negative-control verification.",
            )
        )

    if prov.get("human_attestation_confirmed") is not True:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                query_id,
                "UNSIGNED_HUMAN_ATTESTATION",
                "human_provenance.human_attestation_confirmed must be explicitly True.",
            )
        )

    att_text = str(prov.get("human_attestation_text") or "").strip()
    if len(att_text) < MIN_ATTESTATION_LENGTH:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                query_id,
                "MISSING_ATTESTATION_TEXT",
                f"human_provenance.human_attestation_text must be at least "
                f"{MIN_ATTESTATION_LENGTH} characters.",
            )
        )

    if not str(prov.get("ai_assistance_disclosure") or "").strip():
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                query_id,
                "MISSING_AI_DISCLOSURE",
                "human_provenance.ai_assistance_disclosure must be explicitly recorded.",
            )
        )

    if not is_valid_iso_utc(str(prov.get("verification_date_utc") or "")):
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                query_id,
                "INVALID_VERIFICATION_DATE",
                "human_provenance.verification_date_utc must be a valid ISO-8601 UTC timestamp.",
            )
        )


def validate_evidence_items(
    query_id: str,
    evidence_list: Sequence[dict[str, Any]],
    corpus: CorpusIndex,
    issues: list[ValidationIssue],
) -> None:
    """Validate corpus eligibility, SHA-256, and verbatim excerpts for all cited evidence."""
    for idx, ev in enumerate(evidence_list):
        pid = str(ev.get("passage_id") or "").strip()
        excerpt = str(ev.get("verbatim_excerpt") or "")
        expected_sha = str(ev.get("content_sha256") or "").strip() or None
        search_used = str(ev.get("search_query_used") or "").strip()
        declared_status = str(ev.get("corpus_eligibility_status") or "").strip()

        if declared_status and declared_status != ELIGIBILITY_ELIGIBLE:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    query_id,
                    "INELIGIBLE_EVIDENCE_STATUS",
                    f"Evidence[{idx}] '{pid}' has non-eligible status '{declared_status}'.",
                )
            )
        if not search_used:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    query_id,
                    "MISSING_SEARCH_QUERY_PROVENANCE",
                    f"Evidence[{idx}] '{pid}' must record search_query_used.",
                )
            )
        try:
            passage = corpus.verify_evidence_citation(
                pid,
                excerpt,
                expected_passage_sha256=expected_sha,
            )
            if ev.get("doc_id") and str(ev["doc_id"]) != passage.doc_id:
                issues.append(
                    ValidationIssue(
                        SEVERITY_ERROR,
                        query_id,
                        "EVIDENCE_DOC_ID_MISMATCH",
                        f"Evidence[{idx}] doc_id '{ev['doc_id']}' does not match "
                        f"canonical doc_id '{passage.doc_id}'.",
                    )
                )
        except CorpusEligibilityError as exc:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    query_id,
                    "OUT_OF_CORPUS_EVIDENCE",
                    f"Evidence[{idx}] rejected: {exc}",
                )
            )
        except ValueError as exc:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    query_id,
                    "INVALID_EVIDENCE_CITATION",
                    f"Evidence[{idx}] invalid: {exc}",
                )
            )
