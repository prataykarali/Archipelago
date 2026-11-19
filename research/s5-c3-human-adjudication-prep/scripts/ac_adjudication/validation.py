"""Validation logic for reviewer submissions, adjudication worksheets, and gold v2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from .constants import (
    ADJUDICATION_SOURCE_ADJUDICATED,
    ADJUDICATION_SOURCE_AGREEMENT,
    DEFAULT_AC_V2_SCHEMA,
    GOLD_STATUS_AC_V2_FINAL,
    GRADE_IRRELEVANT,
    MIN_RATIONALE_LENGTH,
    PROVENANCE_AI_ASSISTED,
    ROLE_REV_A,
    ROLE_REV_B,
    ROLE_REV_C,
    SCHEMA_VERSION_AC_V2,
    VALID_GRADES,
    VALID_ROLES,
)
from .pool_index import FrozenPool, is_valid_sha256_hex, sha256_text
from .provenance import (
    is_valid_human_identifier,
    validate_adjudicator_provenance,
    validate_independent_human_provenance,
    validate_investigator_signoff,
    validate_negative_control_verifications,
)


class ACValidationError(ValueError):
    """Raised when an A/C submission, adjudication worksheet, or gold v2 fails checks."""


def _validate_quote_for_grade(
    pair_id: str,
    grade: int,
    quote: Any,
    canonical_text: str | None,
    field_name: str,
) -> list[str]:
    """Validate supporting quote rules for grade 0 vs grades 1/2."""
    errors: list[str] = []
    if not isinstance(quote, str):
        return [f"{pair_id}: {field_name} must be a string"]
    stripped = quote.strip()
    if grade == GRADE_IRRELEVANT:
        if stripped:
            errors.append(f"{pair_id}: {field_name} must be blank when grade is 0")
        return errors
    if not stripped:
        errors.append(f"{pair_id}: {field_name} is required when grade is {grade}")
        return errors
    if canonical_text is not None and stripped not in canonical_text:
        errors.append(
            f"{pair_id}: {field_name} is not an exact verbatim substring of canonical passage"
        )
    return errors


def validate_reviewer_submission(
    submission: dict[str, Any],
    pool: FrozenPool,
    *,
    expected_role: str,
) -> dict[str, dict[str, Any]]:
    """Validate a complete REV_A or REV_C submission against the frozen pool.

    Returns:
        Mapping of `pair_id` -> validated judgment dict.

    Raises:
        ACValidationError: If any alignment, completeness, quote, or provenance check fails.
    """
    errors: list[str] = []
    if expected_role not in VALID_ROLES:
        raise ACValidationError(f"Unsupported expected_role {expected_role!r}; must be REV_A or REV_C")

    actual_role = submission.get("reviewer_role")
    if actual_role == ROLE_REV_B:
        errors.append("REV_B submissions are permanently excluded from A/C independent human gold")
    elif actual_role != expected_role:
        errors.append(f"reviewer_role mismatch: expected {expected_role!r}, got {actual_role!r}")

    if submission.get("pool_version") != pool.version:
        errors.append(
            f"pool_version mismatch: expected {pool.version!r}, got {submission.get('pool_version')!r}"
        )
    if submission.get("pool_sha256") != pool.pool_sha256:
        errors.append(
            f"pool_sha256 mismatch: expected {pool.pool_sha256!r}, got {submission.get('pool_sha256')!r}"
        )

    errors.extend(validate_independent_human_provenance(submission.get("provenance"), expected_role))

    raw_judgments = submission.get("judgments")
    if not isinstance(raw_judgments, list):
        errors.append("judgments must be a list")
        raise ACValidationError("Reviewer submission validation failed:\n- " + "\n- ".join(errors))

    indexed: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(raw_judgments):
        if not isinstance(row, dict):
            errors.append(f"judgments[{idx}] must be an object")
            continue
        pid = row.get("pair_id")
        if not isinstance(pid, str) or pid not in pool.entries_by_pair_id:
            errors.append(f"judgments[{idx}]: unknown pair_id {pid!r}")
            continue
        if pid in indexed:
            errors.append(f"{pid}: duplicate pair_id")
            continue

        entry = pool.entries_by_pair_id[pid]
        if row.get("query_id") != entry.query_id or row.get("passage_id") != entry.passage_id:
            errors.append(
                f"{pid}: (query_id, passage_id) mismatch: expected "
                f"{(entry.query_id, entry.passage_id)}, got {(row.get('query_id'), row.get('passage_id'))}"
            )
        if row.get("passage_sha256") != entry.passage_sha256:
            errors.append(
                f"{pid}: passage_sha256 mismatch: expected {entry.passage_sha256}, "
                f"got {row.get('passage_sha256')!r}"
            )

        canonical_text = entry.passage_text
        if canonical_text is None and isinstance(row.get("passage_text"), str):
            row_text = row["passage_text"]
            if sha256_text(row_text) != entry.passage_sha256:
                errors.append(f"{pid}: passage_text SHA-256 does not match frozen passage_sha256")
            else:
                canonical_text = row_text

        grade = row.get("relevance_grade")
        if type(grade) is not int or grade not in VALID_GRADES:
            errors.append(f"{pid}: relevance_grade must be int in {{0, 1, 2}}, got {grade!r}")
            continue

        errors.extend(
            _validate_quote_for_grade(
                pid,
                grade,
                row.get("supporting_quotation", ""),
                canonical_text,
                "supporting_quotation",
            )
        )
        indexed[pid] = row

    missing = [pid for pid in pool.ordered_pair_ids if pid not in indexed]
    if missing:
        errors.append(
            f"Incomplete submission: missing {len(missing)} of {pool.pair_count} pairs "
            f"(e.g. {missing[:5]})"
        )

    if errors:
        raise ACValidationError("Reviewer submission validation failed:\n- " + "\n- ".join(errors))
    return indexed


def validate_adjudication_worksheet(
    worksheet: dict[str, Any],
    expected_disagreement_pairs: list[str],
    pool: FrozenPool,
) -> dict[str, dict[str, Any]]:
    """Validate a human-completed A/C adjudication worksheet for every disagreement."""
    errors: list[str] = []
    if worksheet.get("pool_version") != pool.version:
        errors.append("worksheet pool_version mismatch")
    if worksheet.get("pool_sha256") != pool.pool_sha256:
        errors.append("worksheet pool_sha256 mismatch")

    total_disagreements = len(expected_disagreement_pairs)
    errors.extend(
        validate_adjudicator_provenance(
            worksheet.get("adjudicator_provenance"),
            total_disagreements=total_disagreements,
        )
    )

    items = worksheet.get("disagreements")
    if not isinstance(items, list):
        errors.append("worksheet disagreements must be a list")
        raise ACValidationError("Adjudication worksheet validation failed:\n- " + "\n- ".join(errors))

    expected_set = set(expected_disagreement_pairs)
    resolved: dict[str, dict[str, Any]] = {}

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"disagreements[{idx}] must be an object")
            continue
        pid = item.get("pair_id")
        if not isinstance(pid, str) or pid not in expected_set:
            errors.append(f"disagreements[{idx}]: unexpected pair_id {pid!r}")
            continue
        if pid in resolved:
            errors.append(f"{pid}: duplicate disagreement entry")
            continue

        entry = pool.entries_by_pair_id[pid]
        if item.get("passage_sha256") != entry.passage_sha256:
            errors.append(f"{pid}: passage_sha256 mismatch in worksheet")

        grade = item.get("adjudicated_grade")
        if type(grade) is not int or grade not in VALID_GRADES:
            errors.append(f"{pid}: adjudicated_grade must be int in {{0, 1, 2}}, got {grade!r}")
            continue

        rationale = item.get("adjudication_rationale")
        if not isinstance(rationale, str) or len(rationale.strip()) < MIN_RATIONALE_LENGTH:
            errors.append(
                f"{pid}: human adjudication_rationale is required (>= {MIN_RATIONALE_LENGTH} chars)"
            )

        if not is_valid_human_identifier(item.get("adjudicator_id")):
            errors.append(f"{pid}: adjudicator_id must be a valid human identifier")

        canonical_text = entry.passage_text
        if (
            canonical_text is None
            and isinstance(item.get("passage_text"), str)
            and sha256_text(item["passage_text"]) == entry.passage_sha256
        ):
            canonical_text = item["passage_text"]

        errors.extend(
            _validate_quote_for_grade(
                pid,
                grade,
                item.get("adjudication_evidence_quote", ""),
                canonical_text,
                "adjudication_evidence_quote",
            )
        )
        resolved[pid] = item

    missing = [pid for pid in expected_disagreement_pairs if pid not in resolved]
    if missing:
        errors.append(
            f"Unadjudicated disagreements remain: {len(missing)} missing (e.g. {missing[:5]})"
        )

    if errors:
        raise ACValidationError("Adjudication worksheet validation failed:\n- " + "\n- ".join(errors))
    return resolved


def validate_gold_v2_payload(
    payload: dict[str, Any],
    pool: FrozenPool,
    schema_path: Path | None = None,
) -> None:
    """Validate an assembled A/C v2 gold-label payload against JSON Schema and semantic rules."""
    errors: list[str] = []
    effective_schema = schema_path or DEFAULT_AC_V2_SCHEMA
    if effective_schema.exists():
        schema = json.loads(effective_schema.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
            loc = ".".join(str(p) for p in err.path) or "<root>"
            errors.append(f"schema[{loc}]: {err.message}")

    if payload.get("schema_version") != SCHEMA_VERSION_AC_V2:
        errors.append(f"schema_version must be {SCHEMA_VERSION_AC_V2!r}")
    if payload.get("status") != GOLD_STATUS_AC_V2_FINAL:
        errors.append(f"status must be {GOLD_STATUS_AC_V2_FINAL!r}")
    if payload.get("pool_version") != pool.version:
        errors.append("pool_version mismatch")
    if payload.get("pool_sha256") != pool.pool_sha256:
        errors.append("pool_sha256 mismatch")
    if payload.get("historical_reviewer_b_excluded_from_gold") is not True:
        errors.append("historical_reviewer_b_excluded_from_gold must be True")

    legacy_b = payload.get("legacy_reviewer_b_provenance")
    if not isinstance(legacy_b, dict) or legacy_b.get("provenance_class") != PROVENANCE_AI_ASSISTED:
        errors.append("legacy_reviewer_b_provenance must preserve AI_ASSISTED_OR_GENERATED")

    errors.extend(validate_independent_human_provenance(payload.get("reviewer_a_provenance"), ROLE_REV_A))
    errors.extend(validate_independent_human_provenance(payload.get("reviewer_c_provenance"), ROLE_REV_C))
    for key in ("reviewer_a_provenance", "reviewer_c_provenance"):
        block = payload.get(key)
        if isinstance(block, dict) and not is_valid_sha256_hex(block.get("submission_sha256")):
            errors.append(f"{key}: submission_sha256 must be a valid 64-hex SHA-256")

    adj_summary = payload.get("adjudication_summary")
    total_disagreements = 0
    if isinstance(adj_summary, dict):
        total_disagreements = int(adj_summary.get("total_disagreements", 0))
        if adj_summary.get("adjudicated_count") != total_disagreements:
            errors.append("adjudication_summary: adjudicated_count must equal total_disagreements")
        errors.extend(
            validate_adjudicator_provenance(
                adj_summary.get("adjudicator_provenance"),
                total_disagreements=total_disagreements,
            )
        )
    else:
        errors.append("adjudication_summary must be an object")

    errors.extend(validate_investigator_signoff(payload.get("investigator_signoff")))
    errors.extend(validate_negative_control_verifications(payload.get("negative_control_verifications")))

    judgments = payload.get("judgments")
    if isinstance(judgments, list):
        seen: set[str] = set()
        disagreement_rows = 0
        for row in judgments:
            if not isinstance(row, dict):
                continue
            pid = row.get("pair_id")
            if not isinstance(pid, str) or pid not in pool.entries_by_pair_id:
                errors.append(f"unknown pair_id {pid!r} in gold judgments")
                continue
            if pid in seen:
                errors.append(f"duplicate pair_id {pid!r} in gold judgments")
                continue
            seen.add(pid)
            entry = pool.entries_by_pair_id[pid]
            if (
                row.get("query_id") != entry.query_id
                or row.get("passage_id") != entry.passage_id
                or row.get("passage_sha256") != entry.passage_sha256
            ):
                errors.append(f"{pid}: alignment mismatch with frozen pool")

            ga = row.get("reviewer_a_grade")
            gc = row.get("reviewer_c_grade")
            gf = row.get("final_grade")
            src = row.get("adjudication_source")
            if ga == gc:
                if src != ADJUDICATION_SOURCE_AGREEMENT or gf != ga:
                    errors.append(f"{pid}: agreement pair must use {ADJUDICATION_SOURCE_AGREEMENT} and matching final_grade")
            else:
                disagreement_rows += 1
                if src != ADJUDICATION_SOURCE_ADJUDICATED:
                    errors.append(f"{pid}: disagreement pair must use {ADJUDICATION_SOURCE_ADJUDICATED}")
                rat = row.get("adjudication_rationale")
                if not isinstance(rat, str) or len(rat.strip()) < MIN_RATIONALE_LENGTH:
                    errors.append(f"{pid}: missing human adjudication_rationale for disagreement")
                if not is_valid_human_identifier(row.get("adjudicator_id")):
                    errors.append(f"{pid}: missing valid human adjudicator_id for disagreement")

            if type(gf) is int and gf in VALID_GRADES:
                errors.extend(
                    _validate_quote_for_grade(
                        pid,
                        gf,
                        row.get("supporting_quotation", ""),
                        entry.passage_text,
                        "supporting_quotation",
                    )
                )

        if len(seen) != pool.pair_count:
            errors.append(f"expected {pool.pair_count} unique pairs, got {len(seen)}")
        if disagreement_rows != total_disagreements:
            errors.append(
                f"adjudication_summary total_disagreements ({total_disagreements}) != actual ({disagreement_rows})"
            )

    if errors:
        raise ACValidationError("Gold v2 validation failed:\n- " + "\n- ".join(errors))
