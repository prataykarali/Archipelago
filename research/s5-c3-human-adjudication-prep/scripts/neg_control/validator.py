"""Strict validator for S5-C3 negative-control human verification worksheets.

Enforces completeness, corpus-hash alignment, corpus eligibility of every cited
or checked passage, verbatim quotation accuracy, classification/impact consistency,
and explicit non-automated human provenance attestation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .constants import (
    ALLOWED_IMPACT_BY_CLASSIFICATION,
    CLASS_AMBIGUOUS_OR_UNSUPPORTED,
    CLASS_ANSWERABLE_IN_FROZEN_CORPUS,
    CLASS_NO_ANSWER_IN_FROZEN_CORPUS,
    CLASS_REQUIRES_REVISION,
    CORPUS_WIDE_SCOPES,
    ELIGIBILITY_ELIGIBLE,
    ELIGIBLE_HUMAN_PROVENANCE_CLASSES,
    IMPACT_HOLD_UNVERIFIED,
    MIN_RATIONALE_LENGTH,
    NEGATIVE_CONTROL_QUERY_IDS,
    SCHEMA_VERSION,
    VALID_CANDIDATE_DECISIONS,
    VALID_CLASSIFICATIONS,
    VALID_CORPUS_SCOPES,
    VALID_D1_IMPACTS,
    VALID_PREMISE_ASSESSMENTS,
)
from .corpus import CorpusIndex
from .validator_checks import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    ValidationIssue,
    validate_evidence_items,
    validate_provenance_block,
)


@dataclass(frozen=True)
class ValidationReport:
    """Full validation report for a negative-control verification worksheet."""

    valid: bool
    ready_for_d1: bool
    schema_version: str
    corpus_version: str
    corpus_sha256: str
    error_count: int
    warning_count: int
    query_statuses: dict[str, dict[str, Any]]
    issues: tuple[ValidationIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "ready_for_d1": self.ready_for_d1,
            "schema_version": self.schema_version,
            "corpus_version": self.corpus_version,
            "corpus_sha256": self.corpus_sha256,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "query_statuses": self.query_statuses,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _validate_single_query(
    record: dict[str, Any],
    corpus: CorpusIndex,
    issues: list[ValidationIssue],
) -> dict[str, Any]:
    """Validate one negative-control query verification record."""
    qid = str(record.get("query_id") or "")
    classification = record.get("human_answerability_classification")
    d1_impact = record.get("d1_evaluation_impact")
    premise = record.get("external_factual_premise_assessment")
    scope = record.get("corpus_scope_checked")
    rationale = str(record.get("verification_rationale") or "").strip()
    revision_notes = str(record.get("revision_or_exclusion_notes") or "").strip()

    if classification not in VALID_CLASSIFICATIONS:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "MISSING_OR_INVALID_CLASSIFICATION",
                f"human_answerability_classification must be one of "
                f"{sorted(VALID_CLASSIFICATIONS)}, got {classification!r}.",
            )
        )

    if d1_impact not in VALID_D1_IMPACTS:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "MISSING_OR_INVALID_D1_IMPACT",
                f"d1_evaluation_impact must be one of {sorted(VALID_D1_IMPACTS)}, "
                f"got {d1_impact!r}.",
            )
        )
    elif classification in ALLOWED_IMPACT_BY_CLASSIFICATION:
        allowed_impacts = ALLOWED_IMPACT_BY_CLASSIFICATION[classification]
        if d1_impact not in allowed_impacts:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    qid,
                    "INCONSISTENT_CLASSIFICATION_AND_IMPACT",
                    f"Classification '{classification}' does not allow d1_evaluation_impact "
                    f"'{d1_impact}' (allowed: {sorted(allowed_impacts)}).",
                )
            )

    if premise not in VALID_PREMISE_ASSESSMENTS:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "MISSING_OR_INVALID_PREMISE_ASSESSMENT",
                f"external_factual_premise_assessment must be one of "
                f"{sorted(VALID_PREMISE_ASSESSMENTS)}, got {premise!r}.",
            )
        )

    if scope not in VALID_CORPUS_SCOPES:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "MISSING_OR_INVALID_CORPUS_SCOPE",
                f"corpus_scope_checked must be one of {sorted(VALID_CORPUS_SCOPES)}, "
                f"got {scope!r}.",
            )
        )

    if len(rationale) < MIN_RATIONALE_LENGTH:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "INSUFFICIENT_RATIONALE",
                f"verification_rationale must be at least {MIN_RATIONALE_LENGTH} characters.",
            )
        )

    checked_ids = list(record.get("checked_passage_ids") or [])
    for pid in checked_ids:
        status = corpus.get_eligibility_status(str(pid))
        if status != ELIGIBILITY_ELIGIBLE:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    qid,
                    "OUT_OF_CORPUS_CHECKED_PASSAGE",
                    f"Checked passage '{pid}' is not in the frozen eligible corpus ({status}).",
                )
            )

    hydrated = list(record.get("hydrated_candidates") or [])
    uninspected_candidates = 0
    for cand in hydrated:
        cpid = str(cand.get("passage_id") or "")
        status = corpus.get_eligibility_status(cpid)
        if status != ELIGIBILITY_ELIGIBLE:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    qid,
                    "OUT_OF_CORPUS_HYDRATED_CANDIDATE",
                    f"Hydrated candidate '{cpid}' is not in the frozen eligible corpus ({status}).",
                )
            )
        if cand.get("contains_answer") not in VALID_CANDIDATE_DECISIONS:
            uninspected_candidates += 1

    if uninspected_candidates > 0:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "UNINSPECTED_HYDRATED_CANDIDATES",
                f"{uninspected_candidates} hydrated candidate passage(s) still lack a "
                f"valid contains_answer decision ({sorted(VALID_CANDIDATE_DECISIONS)}).",
            )
        )

    if classification == CLASS_NO_ANSWER_IN_FROZEN_CORPUS:
        if scope not in CORPUS_WIDE_SCOPES:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    qid,
                    "INSUFFICIENT_SCOPE_FOR_CORPUS_WIDE_NEGATIVE",
                    "NO_ANSWER_IN_FROZEN_CORPUS requires corpus_scope_checked in "
                    f"{sorted(CORPUS_WIDE_SCOPES)}, not {scope!r}.",
                )
            )
        if not checked_ids and not hydrated:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    qid,
                    "NO_PASSAGES_CHECKED",
                    "NO_ANSWER_IN_FROZEN_CORPUS requires at least one recorded checked passage.",
                )
            )

    evidence_list = list(record.get("supporting_evidence") or [])
    validate_evidence_items(qid, evidence_list, corpus, issues)

    if classification == CLASS_ANSWERABLE_IN_FROZEN_CORPUS and not evidence_list:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "MISSING_ANSWERABLE_EVIDENCE",
                "ANSWERABLE_IN_FROZEN_CORPUS requires at least one verified corpus-eligible "
                "supporting_evidence citation with a verbatim excerpt.",
            )
        )

    if (
        classification in {CLASS_AMBIGUOUS_OR_UNSUPPORTED, CLASS_REQUIRES_REVISION}
        and not revision_notes
    ):
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "MISSING_REVISION_OR_EXCLUSION_NOTES",
                f"Classification '{classification}' requires explicit "
                "revision_or_exclusion_notes documenting the premise/revision issue.",
            )
        )

    prov = record.get("human_provenance")
    if not isinstance(prov, dict):
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                qid,
                "MISSING_PROVENANCE_BLOCK",
                "human_provenance block is missing.",
            )
        )
        prov = {}
    else:
        validate_provenance_block(qid, prov, issues)

    return {
        "classification": classification,
        "d1_evaluation_impact": d1_impact,
        "provenance_class": prov.get("provenance_class"),
        "evidence_count": len(evidence_list),
        "checked_passage_count": len(checked_ids),
        "searches_logged": len(record.get("search_audit_log") or []),
    }


def validate_worksheet(
    worksheet: dict[str, Any],
    corpus: CorpusIndex,
    *,
    expected_query_ids: Sequence[str] = NEGATIVE_CONTROL_QUERY_IDS,
) -> ValidationReport:
    """Validate a negative-control verification worksheet against the frozen eligible corpus."""
    issues: list[ValidationIssue] = []

    if worksheet.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                None,
                "SCHEMA_VERSION_MISMATCH",
                f"Expected schema_version '{SCHEMA_VERSION}', got "
                f"{worksheet.get('schema_version')!r}.",
            )
        )

    if worksheet.get("corpus_sha256") != corpus.corpus_sha256:
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                None,
                "CORPUS_SHA256_MISMATCH",
                f"Worksheet corpus_sha256 '{worksheet.get('corpus_sha256')}' does not match "
                f"loaded frozen corpus SHA-256 '{corpus.corpus_sha256}'.",
            )
        )

    queries = worksheet.get("queries")
    if not isinstance(queries, list):
        issues.append(
            ValidationIssue(
                SEVERITY_ERROR,
                None,
                "MISSING_QUERIES_LIST",
                "Worksheet 'queries' must be a list.",
            )
        )
        queries = []

    by_qid: dict[str, dict[str, Any]] = {}
    for entry in queries:
        qid = str(entry.get("query_id") or "")
        if qid in by_qid:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    qid,
                    "DUPLICATE_QUERY_ID",
                    f"Duplicate verification entry for query '{qid}'.",
                )
            )
        by_qid[qid] = entry

    expected_set = set(expected_query_ids)
    for req_qid in expected_query_ids:
        if req_qid not in by_qid:
            issues.append(
                ValidationIssue(
                    SEVERITY_ERROR,
                    req_qid,
                    "MISSING_REQUIRED_QUERY",
                    f"Required negative-control query '{req_qid}' is missing.",
                )
            )

    for extra in sorted(set(by_qid) - expected_set):
        issues.append(
            ValidationIssue(
                SEVERITY_WARNING,
                extra,
                "UNEXPECTED_QUERY_ID",
                f"Query '{extra}' is not in the expected negative-control query set.",
            )
        )

    query_statuses: dict[str, dict[str, Any]] = {}
    for qid in expected_query_ids:
        if qid in by_qid:
            query_statuses[qid] = _validate_single_query(by_qid[qid], corpus, issues)

    error_count = sum(1 for i in issues if i.severity == SEVERITY_ERROR)
    warning_count = sum(1 for i in issues if i.severity == SEVERITY_WARNING)
    valid = error_count == 0
    has_hold = any(
        st.get("d1_evaluation_impact") == IMPACT_HOLD_UNVERIFIED
        for st in query_statuses.values()
    )
    all_human_eligible = all(
        st.get("provenance_class") in ELIGIBLE_HUMAN_PROVENANCE_CLASSES
        for st in query_statuses.values()
    )

    return ValidationReport(
        valid=valid,
        ready_for_d1=valid and (not has_hold) and all_human_eligible,
        schema_version=str(worksheet.get("schema_version") or ""),
        corpus_version=corpus.corpus_version,
        corpus_sha256=corpus.corpus_sha256,
        error_count=error_count,
        warning_count=warning_count,
        query_statuses=query_statuses,
        issues=tuple(issues),
    )
