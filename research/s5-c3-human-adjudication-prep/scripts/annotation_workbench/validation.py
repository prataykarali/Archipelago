"""Validation and completion-summary logic for S5-C3 human annotations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import (
    ASSISTANCE_AI_ASSISTED,
    ASSISTANCE_NONE,
    GRADE_IRRELEVANT,
    PROVENANCE_AI_ASSISTED,
    PROVENANCE_INDEPENDENT_HUMAN,
    PROVENANCE_POST_AI_EXPOSURE,
    STATUS_COMPLETED_TEMPLATE,
    STATUS_IN_PROGRESS,
    STATUS_NOT_STARTED,
    VALID_ASSISTANCE_DECLARATIONS,
    VALID_CONFIDENCE_LEVELS,
    VALID_GRADES,
    VALID_PROVENANCE_CLASSES,
)
from .models import (
    AnnotationSession,
    CandidatePair,
    JudgmentRecord,
    LoadedPool,
    ProvenanceDeclaration,
    content_hash,
)


@dataclass(frozen=True)
class PairValidationResult:
    """Validation status for one candidate pair judgment."""

    pair_id: str
    started: bool
    complete: bool
    valid: bool
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize pair validation status."""
        return {
            "pair_id": self.pair_id,
            "started": self.started,
            "complete": self.complete,
            "valid": self.valid,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class SessionValidationReport:
    """Full validation report for an annotation session against the frozen pool."""

    valid_for_export: bool
    total_pairs: int
    completed_pairs: int
    graded_pairs: int
    flagged_pairs: int
    invalid_pairs: int
    remaining_pairs: int
    provenance_valid: bool
    provenance_errors: tuple[str, ...] = ()
    pair_errors: dict[str, tuple[str, ...]] = field(default_factory=dict)
    integrity_errors: tuple[str, ...] = ()
    per_query: tuple[dict[str, Any], ...] = ()
    review_completion_status: str = STATUS_NOT_STARTED

    def to_dict(self) -> dict[str, Any]:
        """Serialize full validation report."""
        return {
            "valid_for_export": self.valid_for_export,
            "total_pairs": self.total_pairs,
            "completed_pairs": self.completed_pairs,
            "graded_pairs": self.graded_pairs,
            "flagged_pairs": self.flagged_pairs,
            "invalid_pairs": self.invalid_pairs,
            "remaining_pairs": self.remaining_pairs,
            "provenance_valid": self.provenance_valid,
            "provenance_errors": list(self.provenance_errors),
            "pair_errors": {pid: list(errs) for pid, errs in self.pair_errors.items()},
            "integrity_errors": list(self.integrity_errors),
            "per_query": list(self.per_query),
            "review_completion_status": self.review_completion_status,
        }


def is_exact_verbatim_quote(quote: str, passage_text: str) -> bool:
    """Return True iff non-empty quote is an exact character-for-character substring."""
    if not quote or not quote.strip():
        return False
    return quote in passage_text


def validate_pair_judgment(
    pair: CandidatePair, judgment: JudgmentRecord | None
) -> PairValidationResult:
    """Validate one candidate pair's human judgment against S5-C3 protocol rules."""
    if judgment is None:
        return PairValidationResult(
            pair_id=pair.pair_id,
            started=False,
            complete=False,
            valid=False,
            errors=("Judgment not started.",),
        )

    started = (
        judgment.relevance_grade is not None
        or bool(judgment.supporting_quotation.strip())
        or bool(judgment.confidence.strip())
        or bool(judgment.reviewer_notes.strip())
    )
    if not started:
        return PairValidationResult(
            pair_id=pair.pair_id,
            started=False,
            complete=False,
            valid=False,
            errors=("Judgment not started.",),
        )

    errors: list[str] = []

    if judgment.relevance_grade not in VALID_GRADES:
        errors.append("relevance_grade must be 0, 1, or 2.")
    elif judgment.relevance_grade == GRADE_IRRELEVANT:
        if judgment.supporting_quotation.strip():
            errors.append(
                "supporting_quotation must be strictly blank when relevance_grade is 0."
            )
    else:
        if not judgment.supporting_quotation.strip():
            errors.append(
                "supporting_quotation is required when relevance_grade is 1 or 2."
            )
        elif not is_exact_verbatim_quote(
            judgment.supporting_quotation, pair.passage_text
        ):
            errors.append(
                "supporting_quotation must be an exact character-for-character "
                "verbatim substring of the canonical passage text."
            )

    if judgment.confidence not in VALID_CONFIDENCE_LEVELS:
        errors.append("confidence must be one of HIGH, MEDIUM, or LOW.")

    if not judgment.reviewer_notes.strip():
        errors.append("reviewer_notes must contain a brief human justification.")

    is_valid = len(errors) == 0
    return PairValidationResult(
        pair_id=pair.pair_id,
        started=True,
        complete=is_valid,
        valid=is_valid,
        errors=tuple(errors),
    )


def validate_provenance(provenance: ProvenanceDeclaration) -> tuple[str, ...]:
    """Validate that human provenance declaration is complete, truthful, and signed."""
    errors: list[str] = []

    if not provenance.reviewer_identity_or_pseudonym.strip():
        errors.append("reviewer_identity_or_pseudonym is required.")

    if provenance.provenance_class not in VALID_PROVENANCE_CLASSES:
        errors.append(
            "provenance_class must be one of: "
            + ", ".join(VALID_PROVENANCE_CLASSES)
            + "."
        )

    if provenance.assistance_declaration not in VALID_ASSISTANCE_DECLARATIONS:
        errors.append(
            "assistance_declaration must be one of: "
            + ", ".join(VALID_ASSISTANCE_DECLARATIONS)
            + "."
        )

    if (
        provenance.provenance_class == PROVENANCE_INDEPENDENT_HUMAN
        and provenance.assistance_declaration != ASSISTANCE_NONE
    ):
        errors.append(
            "INDEPENDENT_HUMAN requires assistance_declaration == NONE_INDEPENDENT_HUMAN."
        )

    if (
        provenance.provenance_class == PROVENANCE_POST_AI_EXPOSURE
        and provenance.assistance_declaration == ASSISTANCE_NONE
    ):
        errors.append(
            "HUMAN_POST_AI_EXPOSURE cannot declare NONE_INDEPENDENT_HUMAN."
        )

    if (
        provenance.provenance_class == PROVENANCE_AI_ASSISTED
        and provenance.assistance_declaration != ASSISTANCE_AI_ASSISTED
    ):
        errors.append(
            "AI_ASSISTED_OR_GENERATED requires assistance_declaration == AI_ASSISTED."
        )

    if not provenance.human_attestation_confirmed:
        errors.append(
            "Human attestation checkbox must be explicitly confirmed by the human reviewer."
        )

    if not provenance.signed_by_human_at_utc.strip():
        errors.append(
            "Human provenance signature timestamp is missing (never auto-signed)."
        )

    return tuple(errors)


def validate_session(
    pool: LoadedPool,
    session: AnnotationSession,
    *,
    require_all_complete: bool = True,
) -> SessionValidationReport:
    """Validate all pairs, passage hashes, and human provenance for a session."""
    integrity_errors: list[str] = []
    if session.pool_sha256 and session.pool_sha256 != pool.pool_sha256:
        integrity_errors.append(
            f"Session pool_sha256 ({session.pool_sha256}) does not match "
            f"loaded pool ({pool.pool_sha256})."
        )

    unknown_ids = sorted(set(session.judgments.keys()) - set(pool.pairs_by_id.keys()))
    if unknown_ids:
        integrity_errors.append(
            f"Session contains unknown pair_ids not in frozen pool: {unknown_ids[:5]}"
        )

    per_query_stats: dict[str, dict[str, Any]] = {}
    for pair in pool.pairs:
        if pair.query_id not in per_query_stats:
            per_query_stats[pair.query_id] = {
                "query_id": pair.query_id,
                "domain": pair.domain,
                "query_text": pair.query_text,
                "total": 0,
                "completed": 0,
                "graded": 0,
                "flagged": 0,
                "invalid": 0,
            }
        per_query_stats[pair.query_id]["total"] += 1

    completed_pairs = 0
    graded_pairs = 0
    flagged_pairs = 0
    invalid_pairs = 0
    pair_errors: dict[str, tuple[str, ...]] = {}

    for pair in pool.pairs:
        if content_hash(pair.passage_text) != pair.passage_sha256:
            integrity_errors.append(
                f"Passage text hash mismatch for {pair.pair_id}: original passage altered."
            )

        judgment = session.judgments.get(pair.pair_id)
        qstat = per_query_stats[pair.query_id]

        if judgment is not None and judgment.flagged:
            flagged_pairs += 1
            qstat["flagged"] += 1

        if judgment is not None and judgment.relevance_grade in VALID_GRADES:
            graded_pairs += 1
            qstat["graded"] += 1

        result = validate_pair_judgment(pair, judgment)
        if result.complete:
            completed_pairs += 1
            qstat["completed"] += 1
        elif result.started:
            invalid_pairs += 1
            qstat["invalid"] += 1
            pair_errors[pair.pair_id] = result.errors
        elif require_all_complete:
            pair_errors[pair.pair_id] = result.errors

    total_pairs = len(pool.pairs)
    remaining_pairs = total_pairs - completed_pairs
    provenance_errors = validate_provenance(session.provenance)
    provenance_valid = len(provenance_errors) == 0

    if completed_pairs == 0 and graded_pairs == 0:
        completion_status = STATUS_NOT_STARTED
    elif completed_pairs == total_pairs:
        completion_status = STATUS_COMPLETED_TEMPLATE.format(
            completed=completed_pairs, total=total_pairs
        )
    else:
        completion_status = STATUS_IN_PROGRESS

    pairs_ok = (
        completed_pairs == total_pairs
        if require_all_complete
        else invalid_pairs == 0
    )
    valid_for_export = (
        len(integrity_errors) == 0 and provenance_valid and pairs_ok
    )

    ordered_queries = tuple(per_query_stats[qid] for qid in pool.query_order)
    return SessionValidationReport(
        valid_for_export=valid_for_export,
        total_pairs=total_pairs,
        completed_pairs=completed_pairs,
        graded_pairs=graded_pairs,
        flagged_pairs=flagged_pairs,
        invalid_pairs=invalid_pairs,
        remaining_pairs=remaining_pairs,
        provenance_valid=provenance_valid,
        provenance_errors=provenance_errors,
        pair_errors=pair_errors,
        integrity_errors=tuple(integrity_errors),
        per_query=ordered_queries,
        review_completion_status=completion_status,
    )
