"""Human provenance, attestation, and anti-AI-substitution validators."""

from __future__ import annotations

import re
from typing import Any

from .constants import (
    AI_PROVENANCE_KEYWORDS,
    ASSISTANCE_NONE,
    FORBIDDEN_SIGNER_TOKENS,
    MIN_APPROVAL_LENGTH,
    MIN_SIGNER_LENGTH,
    MIN_TIMESTAMP_LENGTH,
    PRIOR_EXPOSURE_NONE,
    PROVENANCE_ADJUDICATED_HUMAN,
    PROVENANCE_INDEPENDENT_HUMAN,
    PROVENANCE_NOT_REQUIRED_ZERO,
    PROVISIONAL_NEG_CONTROL_IDS,
    VALID_NEG_CONTROL_CLASSES,
)

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def is_valid_human_identifier(value: Any) -> bool:
    """Return True if value is a non-placeholder human identifier or pseudonym."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if len(stripped) < MIN_SIGNER_LENGTH:
        return False
    if "<" in stripped or ">" in stripped:
        return False
    lowered = stripped.lower()
    if lowered in FORBIDDEN_SIGNER_TOKENS:
        return False
    tokens = {tok for tok in _TOKEN_SPLIT_RE.split(lowered) if tok}
    if not tokens:
        return False
    return not tokens.intersection(FORBIDDEN_SIGNER_TOKENS)


def has_ai_provenance_marker(value: Any) -> bool:
    """Return True if string value explicitly indicates AI assistance or generation."""
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    if lowered in {ASSISTANCE_NONE.lower(), PROVENANCE_INDEPENDENT_HUMAN.lower()}:
        return False
    tokens = {tok for tok in _TOKEN_SPLIT_RE.split(lowered) if tok}
    return any(kw in tokens for kw in AI_PROVENANCE_KEYWORDS)


def validate_independent_human_provenance(
    provenance: Any,
    role: str,
) -> list[str]:
    """Validate truthful signed independent-human provenance for REV_A or REV_C."""
    errors: list[str] = []
    if not isinstance(provenance, dict):
        return [f"{role}: provenance must be an object"]

    reviewer_id = provenance.get("reviewer_id")
    if not is_valid_human_identifier(reviewer_id):
        errors.append(f"{role}: reviewer_id must be a valid non-placeholder human identifier")

    prov_class = provenance.get("provenance_class")
    if has_ai_provenance_marker(prov_class):
        errors.append(
            f"{role}: rejected AI-assisted/AI-generated provenance_class {prov_class!r}"
        )
    elif prov_class != PROVENANCE_INDEPENDENT_HUMAN:
        errors.append(
            f"{role}: provenance_class must be {PROVENANCE_INDEPENDENT_HUMAN!r}, got {prov_class!r}"
        )

    assistance = provenance.get("assistance_declaration")
    if has_ai_provenance_marker(assistance):
        errors.append(
            f"{role}: rejected AI assistance_declaration {assistance!r}"
        )
    elif assistance != ASSISTANCE_NONE:
        errors.append(
            f"{role}: assistance_declaration must be {ASSISTANCE_NONE!r}, got {assistance!r}"
        )

    exposure = provenance.get("prior_exposure_disclosure")
    if exposure != PRIOR_EXPOSURE_NONE:
        errors.append(
            f"{role}: prior_exposure_disclosure must be {PRIOR_EXPOSURE_NONE!r}, got {exposure!r}"
        )

    if provenance.get("human_attestation_signed") is not True:
        errors.append(f"{role}: human_attestation_signed must be explicitly True")

    if not is_valid_human_identifier(provenance.get("attestation_signer")):
        errors.append(
            f"{role}: attestation_signer must be a valid non-placeholder human identifier"
        )

    ts = provenance.get("signed_timestamp_utc")
    if not isinstance(ts, str) or len(ts.strip()) < MIN_TIMESTAMP_LENGTH:
        errors.append(f"{role}: signed_timestamp_utc must be a non-empty ISO-8601 timestamp")

    return errors


def validate_adjudicator_provenance(
    provenance: Any,
    *,
    total_disagreements: int,
) -> list[str]:
    """Validate human adjudicator provenance block (rejecting unsigned or AI)."""
    errors: list[str] = []
    if not isinstance(provenance, dict):
        return ["adjudicator_provenance must be an object"]

    if not is_valid_human_identifier(provenance.get("adjudicator_id")):
        errors.append("adjudicator_id must be a valid non-placeholder human identifier")

    prov_class = provenance.get("provenance_class")
    allowed = (
        {PROVENANCE_ADJUDICATED_HUMAN}
        if total_disagreements > 0
        else {PROVENANCE_ADJUDICATED_HUMAN, PROVENANCE_NOT_REQUIRED_ZERO}
    )
    if has_ai_provenance_marker(prov_class):
        errors.append(
            f"adjudicator_provenance: rejected AI-assisted/AI-generated class {prov_class!r}"
        )
    elif prov_class not in allowed:
        errors.append(
            f"adjudicator_provenance: provenance_class must be in {sorted(allowed)}, got {prov_class!r}"
        )

    assistance = provenance.get("assistance_declaration")
    if has_ai_provenance_marker(assistance):
        errors.append(
            f"adjudicator_provenance: rejected AI assistance_declaration {assistance!r}"
        )
    elif assistance != ASSISTANCE_NONE:
        errors.append(
            f"adjudicator_provenance: assistance_declaration must be {ASSISTANCE_NONE!r}, got {assistance!r}"
        )

    if provenance.get("human_attestation_signed") is not True:
        errors.append("adjudicator_provenance: human_attestation_signed must be explicitly True")

    if not is_valid_human_identifier(provenance.get("attestation_signer")):
        errors.append(
            "adjudicator_provenance: attestation_signer must be a valid non-placeholder human identifier"
        )

    ts = provenance.get("signed_timestamp_utc")
    if not isinstance(ts, str) or len(ts.strip()) < MIN_TIMESTAMP_LENGTH:
        errors.append("adjudicator_provenance: signed_timestamp_utc must be a non-empty timestamp")

    return errors


def validate_investigator_signoff(signoff: Any) -> list[str]:
    """Validate explicit human investigator sign-off block."""
    errors: list[str] = []
    if not isinstance(signoff, dict):
        return ["investigator_signoff must be an object"]

    if not is_valid_human_identifier(signoff.get("investigator_id")):
        errors.append("investigator_signoff: investigator_id must be a valid human identifier")

    decl = signoff.get("approval_declaration")
    if not isinstance(decl, str) or len(decl.strip()) < MIN_APPROVAL_LENGTH:
        errors.append("investigator_signoff: approval_declaration must be a non-empty statement")

    if signoff.get("human_signoff_confirmed") is not True:
        errors.append("investigator_signoff: human_signoff_confirmed must be explicitly True")

    ts = signoff.get("signed_timestamp_utc")
    if not isinstance(ts, str) or len(ts.strip()) < MIN_TIMESTAMP_LENGTH:
        errors.append("investigator_signoff: signed_timestamp_utc must be a non-empty timestamp")

    return errors


def validate_negative_control_verifications(neg_ver: Any) -> list[str]:
    """Validate human negative-control verification records for all 3 provisional queries."""
    errors: list[str] = []
    if not isinstance(neg_ver, dict):
        return ["negative_control_verifications must be an object"]

    for qid in PROVISIONAL_NEG_CONTROL_IDS:
        rec = neg_ver.get(qid)
        if not isinstance(rec, dict):
            errors.append(f"negative_control_verifications: missing record for {qid}")
            continue
        cls = rec.get("human_answerability_classification")
        if cls not in VALID_NEG_CONTROL_CLASSES:
            errors.append(f"{qid}: invalid human_answerability_classification {cls!r}")
        if not is_valid_human_identifier(rec.get("verifier_id")):
            errors.append(f"{qid}: verifier_id must be a valid human identifier")
        prov = rec.get("provenance_class")
        if has_ai_provenance_marker(prov) or prov != PROVENANCE_INDEPENDENT_HUMAN:
            errors.append(
                f"{qid}: provenance_class must be {PROVENANCE_INDEPENDENT_HUMAN!r}, got {prov!r}"
            )
        if rec.get("human_attestation_signed") is not True:
            errors.append(f"{qid}: human_attestation_signed must be explicitly True")
        ts = rec.get("signed_timestamp_utc")
        if not isinstance(ts, str) or len(ts.strip()) < MIN_TIMESTAMP_LENGTH:
            errors.append(f"{qid}: signed_timestamp_utc must be a non-empty timestamp")

    return errors
