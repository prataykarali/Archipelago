"""Dynamic corpus-restricted negative-control verification for S5-v3.1."""

from __future__ import annotations

from typing import Any

from .constants import (
    ASSISTANCE_NONE_HUMAN,
    BENCHMARK_VERSION,
    MIN_RATIONALE_CHARS,
    PROVENANCE_INDEPENDENT_HUMAN,
    VALID_NC_CLASSIFICATIONS,
)


def generate_nc_verification_worksheet(
    approved_nc_queries: list[dict[str, Any]],
    corpus_sha256: str,
) -> dict[str, Any]:
    """Generate blank corpus-restricted NC verification worksheet."""
    verifications: dict[str, dict[str, Any]] = {}
    for q in approved_nc_queries:
        qid = str(q["query_id"])
        verifications[qid] = {
            "query_id": qid,
            "query_text": str(q["query_text"]),
            "human_nc_classification": "",
            "verifier_id": "",
            "provenance_class": PROVENANCE_INDEPENDENT_HUMAN,
            "assistance_declaration": ASSISTANCE_NONE_HUMAN,
            "human_attestation_signed": False,
            "attestation_signer": "",
            "signed_timestamp_utc": "",
            "corpus_sha256": corpus_sha256,
            "rationale": "",
        }
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "corpus_sha256": corpus_sha256,
        "expected_nc_ids": sorted(verifications.keys()),
        "verifications": verifications,
    }


def validate_nc_verifications(
    nc_payload: dict[str, Any],
    expected_nc_ids: frozenset[str],
    expected_corpus_sha256: str,
) -> list[str]:
    """Validate completed human NC verifications; fail closed on any gap."""
    errors: list[str] = []
    if nc_payload.get("benchmark_version") != BENCHMARK_VERSION:
        errors.append("INVALID_NC_BENCHMARK_VERSION")
    if str(nc_payload.get("corpus_sha256", "")) != expected_corpus_sha256:
        errors.append("NC_CORPUS_SHA256_MISMATCH")

    verifications = nc_payload.get("verifications")
    if not isinstance(verifications, dict):
        errors.append("MISSING_NC_VERIFICATIONS_MAP")
        return errors

    actual_ids = frozenset(verifications.keys())
    if actual_ids != expected_nc_ids:
        errors.append(
            f"NC_ID_SET_MISMATCH: expected={sorted(expected_nc_ids)} "
            f"got={sorted(actual_ids)}"
        )

    for qid in sorted(expected_nc_ids):
        rec = verifications.get(qid)
        if not isinstance(rec, dict):
            continue
        if str(rec.get("query_id", "")) != qid:
            errors.append(f"NC_QUERY_ID_MISMATCH:{qid}")
        if str(rec.get("corpus_sha256", "")) != expected_corpus_sha256:
            errors.append(f"NC_ENTRY_CORPUS_SHA_MISMATCH:{qid}")
        if rec.get("human_nc_classification") not in VALID_NC_CLASSIFICATIONS:
            errors.append(f"INVALID_NC_CLASSIFICATION:{qid}")
        if rec.get("provenance_class") != PROVENANCE_INDEPENDENT_HUMAN:
            errors.append(f"NON_HUMAN_NC_PROVENANCE:{qid}")
        if rec.get("assistance_declaration") != ASSISTANCE_NONE_HUMAN:
            errors.append(f"AI_ASSISTED_NC_FORBIDDEN:{qid}")
        if rec.get("human_attestation_signed") is not True:
            errors.append(f"UNSIGNED_NC_VERIFICATION:{qid}")
        for fname in (
            "verifier_id",
            "attestation_signer",
            "signed_timestamp_utc",
        ):
            if not str(rec.get(fname, "")).strip():
                errors.append(f"MISSING_NC_{fname.upper()}:{qid}")
        if len(str(rec.get("rationale", "")).strip()) < MIN_RATIONALE_CHARS:
            errors.append(f"SHORT_NC_RATIONALE:{qid}")

    return errors
