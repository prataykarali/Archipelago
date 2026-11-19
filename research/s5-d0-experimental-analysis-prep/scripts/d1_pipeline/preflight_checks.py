"""Modular schema, provenance, negative-control, and judgment checks for S5-D1 preflight."""

from __future__ import annotations

from typing import Any

from d1_pipeline.constants import (
    AC_V2_SCHEMA_VERSIONS,
    AGREEMENT_ADJUDICATION_SOURCES,
    ALL_VALID_NEG_CONTROL_CLASSES,
    GOLD_FINAL_STATUSES,
    LEGACY_V1_SCHEMA_VERSION,
    NEG_CONTROL_CONFIRMED_UNANSWERABLE,
    NEG_CONTROL_EXCLUDED_CLASSES,
    NEG_CONTROL_RECLASSIFIED_ANSWERABLE,
    PROVISIONAL_NEG_CONTROL_IDS,
    REQUIRED_ASSISTANCE_DECLARATION,
    REQUIRED_PRIOR_EXPOSURE,
    VALID_ADJUDICATION_SOURCES,
    VALID_ADJUDICATOR_PROVENANCE_CLASSES,
    VALID_GRADES,
    VALID_HUMAN_PROVENANCE_CLASSES,
)
from d1_pipeline.preflight_models import (
    PoolEntry,
    PreflightFinding,
    PreflightResult,
    is_valid_human_id,
)


def resolve_neg_control_records(
    gold_payload: dict[str, Any],
    neg_control_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Extract negative-control verification records from external file or embedded gold."""
    if neg_control_payload is not None:
        for key in ("verifications", "negative_control_verifications"):
            if isinstance(neg_control_payload.get(key), dict):
                return neg_control_payload[key]
        if isinstance(neg_control_payload.get("queries"), list):
            return {
                row["query_id"]: row
                for row in neg_control_payload["queries"]
                if isinstance(row, dict) and "query_id" in row
            }
        return None
    embedded = gold_payload.get("negative_control_verifications")
    return embedded if isinstance(embedded, dict) else None


def _extract_neg_classification(rec: dict[str, Any]) -> str | None:
    for key in (
        "human_answerability_classification",
        "classification",
        "answerability_classification",
    ):
        val = rec.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _validate_reviewer_prov(
    gold: dict[str, Any],
    prov_key: str,
    flat_key: str,
    errors: list[PreflightFinding],
) -> None:
    prov_obj = gold.get(prov_key)
    if isinstance(prov_obj, dict):
        pcls = prov_obj.get("provenance_class")
        if pcls not in VALID_HUMAN_PROVENANCE_CLASSES:
            errors.append(
                PreflightFinding("INVALID_HUMAN_PROVENANCE", f"{prov_key}.provenance_class invalid: {pcls!r}")
            )
        if prov_obj.get("assistance_declaration") != REQUIRED_ASSISTANCE_DECLARATION:
            errors.append(
                PreflightFinding(
                    "INVALID_HUMAN_PROVENANCE",
                    f"{prov_key}.assistance_declaration must be {REQUIRED_ASSISTANCE_DECLARATION!r}",
                )
            )
        if prov_obj.get("prior_exposure_disclosure") != REQUIRED_PRIOR_EXPOSURE:
            errors.append(
                PreflightFinding(
                    "INVALID_HUMAN_PROVENANCE",
                    f"{prov_key}.prior_exposure_disclosure must be {REQUIRED_PRIOR_EXPOSURE!r}",
                )
            )
        if prov_obj.get("human_attestation_signed") is not True:
            errors.append(
                PreflightFinding("INVALID_HUMAN_PROVENANCE", f"{prov_key}.human_attestation_signed must be True")
            )
        if not is_valid_human_id(prov_obj.get("reviewer_id")):
            errors.append(
                PreflightFinding("INVALID_HUMAN_PROVENANCE", f"{prov_key}.reviewer_id is invalid or placeholder")
            )
        return

    pcls = gold.get(flat_key)
    if pcls not in VALID_HUMAN_PROVENANCE_CLASSES:
        errors.append(
            PreflightFinding(
                "INVALID_HUMAN_PROVENANCE",
                f"Missing {prov_key} and {flat_key} is not independent human: {pcls!r}",
            )
        )


def validate_schema_and_provenance(
    gold: dict[str, Any],
    schema_mode: str,
    errors: list[PreflightFinding],
) -> str:
    """Validate top-level gold schema, adjudication flags, and human provenance."""
    version = gold.get("schema_version")
    resolved = schema_mode
    if resolved == "auto":
        if version == LEGACY_V1_SCHEMA_VERSION:
            resolved = "v1"
        elif version in AC_V2_SCHEMA_VERSIONS:
            resolved = "ac_v2"
        else:
            errors.append(PreflightFinding("INVALID_GOLD_SCHEMA", f"Unsupported schema_version: {version!r}"))
            return "unknown"

    if gold.get("status") not in GOLD_FINAL_STATUSES:
        errors.append(
            PreflightFinding("INVALID_GOLD_SCHEMA", f"status must be final gold, got {gold.get('status')!r}")
        )

    if resolved == "v1":
        if version != LEGACY_V1_SCHEMA_VERSION:
            errors.append(
                PreflightFinding("INVALID_GOLD_SCHEMA", f"Legacy v1 requires {LEGACY_V1_SCHEMA_VERSION!r}")
            )
        if gold.get("reviewer_b_independence_confirmed") is not True:
            errors.append(
                PreflightFinding(
                    "INVALID_HUMAN_PROVENANCE",
                    "Legacy v1 contract requires reviewer_b_independence_confirmed is True",
                )
            )
        if gold.get("all_disagreements_adjudicated") is not True:
            errors.append(
                PreflightFinding("INCOMPLETE_ADJUDICATION", "Legacy v1 requires all_disagreements_adjudicated is True")
            )
        return "v1"

    if version not in AC_V2_SCHEMA_VERSIONS:
        errors.append(
            PreflightFinding("INVALID_GOLD_SCHEMA", f"A/C v2 requires schema_version in {sorted(AC_V2_SCHEMA_VERSIONS)}")
        )
    if gold.get("primary_human_assessor_pair") != ["REV_A", "REV_C"]:
        errors.append(
            PreflightFinding("INVALID_HUMAN_PROVENANCE", "primary_human_assessor_pair must be ['REV_A', 'REV_C']")
        )
    _validate_reviewer_prov(gold, "reviewer_a_provenance", "reviewer_a_provenance_class", errors)
    _validate_reviewer_prov(gold, "reviewer_c_provenance", "reviewer_c_provenance_class", errors)

    if gold.get("historical_reviewer_b_excluded_from_gold") is not True:
        errors.append(
            PreflightFinding("INVALID_HUMAN_PROVENANCE", "A/C v2 requires historical_reviewer_b_excluded_from_gold=True")
        )

    adj_summary = gold.get("adjudication_summary")
    if isinstance(adj_summary, dict):
        if adj_summary.get("all_ac_disagreements_adjudicated") is not True:
            errors.append(
                PreflightFinding("INCOMPLETE_ADJUDICATION", "adjudication_summary.all_ac_disagreements_adjudicated!=True")
            )
        adj_prov = adj_summary.get("adjudicator_provenance")
        if isinstance(adj_prov, dict):
            if adj_prov.get("provenance_class") not in VALID_ADJUDICATOR_PROVENANCE_CLASSES:
                errors.append(PreflightFinding("INVALID_HUMAN_PROVENANCE", "adjudicator_provenance.provenance_class invalid"))
            if adj_prov.get("assistance_declaration") != REQUIRED_ASSISTANCE_DECLARATION:
                errors.append(PreflightFinding("INVALID_HUMAN_PROVENANCE", "adjudicator_provenance.assistance_declaration invalid"))
            if adj_prov.get("human_attestation_signed") is not True:
                errors.append(PreflightFinding("INVALID_HUMAN_PROVENANCE", "adjudicator_provenance unsigned"))
    elif gold.get("all_ac_disagreements_adjudicated", gold.get("all_disagreements_adjudicated")) is not True:
        errors.append(PreflightFinding("INCOMPLETE_ADJUDICATION", "A/C v2 requires all_ac_disagreements_adjudicated=True"))

    signoff = gold.get("investigator_signoff")
    if isinstance(signoff, dict):
        if signoff.get("human_signoff_confirmed") is not True:
            errors.append(PreflightFinding("INVALID_HUMAN_PROVENANCE", "investigator_signoff not confirmed"))
        if not is_valid_human_id(signoff.get("investigator_id")):
            errors.append(PreflightFinding("INVALID_HUMAN_PROVENANCE", "investigator_signoff.investigator_id invalid"))
    return "ac_v2"


def validate_negative_controls(
    neg_records: dict[str, Any] | None,
    pool_query_ids: set[str],
    schema_mode: str,
    result: PreflightResult,
) -> None:
    """Validate negative-control verifications and record reclassifications."""
    required_neg_ids = [qid for qid in PROVISIONAL_NEG_CONTROL_IDS if qid in pool_query_ids]
    if not required_neg_ids:
        return
    if not isinstance(neg_records, dict):
        result.errors.append(PreflightFinding("UNVERIFIED_NEGATIVE_CONTROLS", "Missing negative-control records"))
        return

    for qid in required_neg_ids:
        rec = neg_records.get(qid)
        if not isinstance(rec, dict):
            result.errors.append(PreflightFinding("UNVERIFIED_NEGATIVE_CONTROLS", f"Missing neg-control for {qid}"))
            continue
        cls = _extract_neg_classification(rec)
        if cls not in ALL_VALID_NEG_CONTROL_CLASSES:
            result.errors.append(
                PreflightFinding("UNVERIFIED_NEGATIVE_CONTROLS", f"{qid}: invalid classification {cls!r}")
            )
            continue
        if rec.get("d1_evaluation_impact") == "HOLD_UNVERIFIED_NEGATIVE_CONTROL":
            result.errors.append(
                PreflightFinding(
                    "UNVERIFIED_NEGATIVE_CONTROLS",
                    f"{qid}: d1_evaluation_impact is HOLD_UNVERIFIED_NEGATIVE_CONTROL",
                )
            )
            continue
        hp = rec.get("human_provenance") if isinstance(rec.get("human_provenance"), dict) else {}
        verifier_id = hp.get("verifier_id", rec.get("verifier_id"))
        if not is_valid_human_id(verifier_id):
            result.errors.append(
                PreflightFinding("INVALID_HUMAN_PROVENANCE", f"{qid}: invalid verifier_id {verifier_id!r}")
            )
        prov = hp.get("provenance_class", rec.get("provenance_class"))
        if (schema_mode == "ac_v2" or prov is not None) and prov not in VALID_HUMAN_PROVENANCE_CLASSES:
            result.errors.append(
                PreflightFinding("INVALID_HUMAN_PROVENANCE", f"{qid}: neg-control provenance_class must be human")
            )
        attested = hp.get("human_attestation_confirmed", rec.get("human_attestation_signed"))
        if attested is not None and attested is not True:
            result.errors.append(
                PreflightFinding("INVALID_HUMAN_PROVENANCE", f"{qid}: neg-control human attestation not signed")
            )

        result.negative_control_classifications[qid] = cls
        if cls in NEG_CONTROL_CONFIRMED_UNANSWERABLE:
            result.verified_negative_controls.append(qid)
        elif cls in NEG_CONTROL_RECLASSIFIED_ANSWERABLE:
            result.reclassified_answerable_controls.append(qid)
            result.warnings.append(
                PreflightFinding("NEG_CONTROL_RECLASSIFIED", f"{qid} reclassified as answerable ({cls}).")
            )
        elif cls in NEG_CONTROL_EXCLUDED_CLASSES:
            result.excluded_negative_controls.append(qid)
            result.warnings.append(
                PreflightFinding("NEG_CONTROL_RECLASSIFIED", f"{qid} classified as {cls}; excluded from primary set.")
            )


def validate_judgments(
    gold: dict[str, Any],
    pool_index: dict[str, PoolEntry],
    passage_texts: dict[str, str] | None,
    errors: list[PreflightFinding],
) -> None:
    """Validate all pair judgments for alignment, grades, adjudication, and verbatim quotes."""
    judgments = gold.get("judgments")
    if not isinstance(judgments, list):
        errors.append(PreflightFinding("INVALID_GOLD_SCHEMA", "judgments must be a list"))
        return

    seen_pairs: set[str] = set()
    for idx, row in enumerate(judgments):
        if not isinstance(row, dict):
            errors.append(PreflightFinding("INVALID_GOLD_SCHEMA", f"judgments[{idx}] must be an object"))
            continue

        pid, qid, passage_id = row.get("pair_id"), row.get("query_id"), row.get("passage_id")
        grade, src = row.get("final_grade"), row.get("adjudication_source")

        if pid not in pool_index:
            errors.append(PreflightFinding("PAIR_ID_HASH_MISALIGNMENT", f"Unknown pair_id {pid!r}"))
            continue
        if pid in seen_pairs:
            errors.append(PreflightFinding("PAIR_ID_HASH_MISALIGNMENT", f"Duplicate pair_id {pid!r}"))
            continue
        seen_pairs.add(pid)

        expected = pool_index[pid]
        if (qid, passage_id) != (expected.query_id, expected.passage_id):
            errors.append(
                PreflightFinding(
                    "PAIR_ID_HASH_MISALIGNMENT",
                    f"{pid}: expected ({expected.query_id}, {expected.passage_id}), got ({qid}, {passage_id})",
                )
            )
        row_sha = row.get("passage_sha256")
        if row_sha is not None and expected.passage_sha256 is not None and row_sha != expected.passage_sha256:
            errors.append(PreflightFinding("PAIR_ID_HASH_MISALIGNMENT", f"{pid}: passage_sha256 mismatch"))

        if type(grade) is not int or grade not in VALID_GRADES:
            errors.append(PreflightFinding("INCONSISTENT_GRADES", f"{pid}: invalid final_grade {grade!r}"))
            continue
        if src not in VALID_ADJUDICATION_SOURCES:
            errors.append(PreflightFinding("INCOMPLETE_ADJUDICATION", f"{pid}: invalid adjudication_source {src!r}"))

        grade_a, grade_c = row.get("reviewer_a_grade"), row.get("reviewer_c_grade")
        if grade_a is not None and grade_c is not None:
            if type(grade_a) is not int or grade_a not in VALID_GRADES:
                errors.append(PreflightFinding("INCONSISTENT_GRADES", f"{pid}: invalid reviewer_a_grade {grade_a!r}"))
            elif type(grade_c) is not int or grade_c not in VALID_GRADES:
                errors.append(PreflightFinding("INCONSISTENT_GRADES", f"{pid}: invalid reviewer_c_grade {grade_c!r}"))
            elif src in AGREEMENT_ADJUDICATION_SOURCES:
                if grade_a != grade_c or grade != grade_a:
                    errors.append(
                        PreflightFinding("INCONSISTENT_GRADES", f"{pid}: {src} requires A==C==final_grade")
                    )
            elif grade_a != grade_c:
                rationale = row.get("adjudication_rationale")
                if not isinstance(rationale, str) or not rationale.strip():
                    errors.append(
                        PreflightFinding("INCOMPLETE_ADJUDICATION", f"{pid}: disagreement missing adjudication_rationale")
                    )

        if passage_texts is not None and grade > 0:
            quote = row.get("supporting_quotation", row.get("supporting_quote", row.get("verbatim_quote")))
            passage_text = passage_texts.get(expected.passage_id)
            if not isinstance(quote, str) or not quote.strip():
                errors.append(PreflightFinding("QUOTE_MISMATCH", f"{pid}: grade={grade} requires supporting quote"))
            elif passage_text is not None and quote not in passage_text:
                errors.append(
                    PreflightFinding("QUOTE_MISMATCH", f"{pid}: quote not verbatim substring of {expected.passage_id}")
                )

    missing_pairs = sorted(set(pool_index.keys()) - seen_pairs)
    if missing_pairs:
        errors.append(
            PreflightFinding("MISSING_JUDGMENTS", f"Missing {len(missing_pairs)} pair_id(s), e.g. {missing_pairs[:5]}")
        )
