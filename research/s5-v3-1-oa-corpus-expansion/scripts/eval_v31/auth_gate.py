"""Hash-pinned two-factor Investigator-Authorization Gate for S5-v3.1 D1 evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval_v31.constants import (
    AUTH_APPROVED_STATUS_V31,
    AUTH_SCHEMA_VERSION_V31,
    BENCHMARK_VERSION_V31,
    MIN_DECLARATION_CHARS,
    PLACEHOLDER_ID_MARKERS,
)


class V31AuthorizationError(RuntimeError):
    """Raised when the two-factor S5-v3.1 Investigator-Authorization Gate refuses execution."""


def is_valid_human_id(value: Any) -> bool:
    """Return True if value is a non-empty, non-placeholder human identifier."""
    if not isinstance(value, str):
        return False
    cleaned = value.strip()
    if not cleaned:
        return False
    if cleaned.upper() in PLACEHOLDER_ID_MARKERS:
        return False
    return not (cleaned.startswith("<") and cleaned.endswith(">"))


def build_v31_authorization_template(
    *,
    corpus_sha256: str,
    query_manifest_sha256: str,
    pool_sha256: str,
    gold_labels_sha256: str,
    nc_verification_sha256: str,
    retrieval_manifest_sha256: str,
) -> dict[str, Any]:
    """Build an unsigned authorization template (must be signed by a human investigator)."""
    return {
        "schema_version": AUTH_SCHEMA_VERSION_V31,
        "benchmark_version": BENCHMARK_VERSION_V31,
        "status": "PENDING_INVESTIGATOR_AUTHORIZATION",
        "investigator_id": "<INVESTIGATOR_ID>",
        "approval_declaration": "<ENTER_EXPLICIT_HUMAN_APPROVAL_STATEMENT>",
        "human_authorization_signed": False,
        "signed_timestamp_utc": "",
        "corpus_sha256": corpus_sha256,
        "query_manifest_sha256": query_manifest_sha256,
        "pool_sha256": pool_sha256,
        "gold_labels_sha256": gold_labels_sha256,
        "nc_verification_sha256": nc_verification_sha256,
        "retrieval_manifest_sha256": retrieval_manifest_sha256,
    }


def validate_v31_authorization_gate(
    *,
    authorize_flag: bool,
    authorization_path: Path | None,
    expected_hashes: dict[str, str],
) -> dict[str, Any]:
    """Enforce two-factor authorization (CLI flag + hash-pinned signed JSON artifact)."""
    if not authorize_flag:
        raise V31AuthorizationError(
            "Real S5-v3.1 D1 execution refused: missing --authorize-real-v31-d1 flag."
        )
    if authorization_path is None or not authorization_path.exists():
        raise V31AuthorizationError(
            f"Real S5-v3.1 D1 execution refused: authorization artifact missing ({authorization_path})."
        )

    try:
        auth = json.loads(authorization_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise V31AuthorizationError(f"Invalid authorization JSON: {exc}") from exc

    if not isinstance(auth, dict):
        raise V31AuthorizationError("Authorization artifact root must be a JSON object.")

    errors: list[str] = []
    if auth.get("schema_version") != AUTH_SCHEMA_VERSION_V31:
        errors.append(
            f"schema_version must be {AUTH_SCHEMA_VERSION_V31!r}, got {auth.get('schema_version')!r}"
        )
    if auth.get("benchmark_version") != BENCHMARK_VERSION_V31:
        errors.append(
            f"benchmark_version must be {BENCHMARK_VERSION_V31!r}, got {auth.get('benchmark_version')!r}"
        )
    if auth.get("status") != AUTH_APPROVED_STATUS_V31:
        errors.append(
            f"status must be {AUTH_APPROVED_STATUS_V31!r}, got {auth.get('status')!r}"
        )
    if auth.get("human_authorization_signed") is not True:
        errors.append("human_authorization_signed must be explicitly True.")
    if not is_valid_human_id(auth.get("investigator_id")):
        errors.append(f"Invalid investigator_id: {auth.get('investigator_id')!r}")

    decl = auth.get("approval_declaration")
    if (
        not isinstance(decl, str)
        or len(decl.strip()) < MIN_DECLARATION_CHARS
        or decl.strip().startswith("<")
    ):
        errors.append("approval_declaration must be a non-placeholder human statement.")

    ts = auth.get("signed_timestamp_utc")
    if not isinstance(ts, str) or not ts.strip():
        errors.append("signed_timestamp_utc must be non-empty.")

    for key in (
        "corpus_sha256",
        "query_manifest_sha256",
        "pool_sha256",
        "gold_labels_sha256",
        "nc_verification_sha256",
        "retrieval_manifest_sha256",
    ):
        expected = expected_hashes.get(key)
        actual = auth.get(key)
        if not expected or actual != expected:
            errors.append(f"Hash pin mismatch for {key}: expected {expected!r}, got {actual!r}")

    if errors:
        raise V31AuthorizationError(
            "Real S5-v3.1 D1 authorization gate failed: " + "; ".join(errors)
        )
    return auth
