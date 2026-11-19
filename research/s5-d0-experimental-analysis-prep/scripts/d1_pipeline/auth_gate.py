"""Explicit Investigator-Authorization Gate for real S5-D1 execution.

Real S5-D1 execution is locked behind TWO independent requirements:
1. A passing preflight validation on non-synthetic, fully validated human evidence.
2. An explicit investigator authorization JSON artifact containing:
   - Non-placeholder human investigator_id
   - Explicit approval status and written declaration
   - Valid ISO-8601 UTC timestamp
   - Exact SHA-256 matches for validated gold labels, negative-control file,
     frozen pool, and frozen rankings
   PLUS the explicit CLI flag `--authorize-real-d1`.

No environment variable, config default, or automated fallback can bypass this gate.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
from typing import Any

from d1_pipeline.constants import (
    AUTH_APPROVED_STATUS,
    AUTH_SCHEMA_VERSION,
    MIN_APPROVAL_DECLARATION_CHARS,
    PLACEHOLDER_ID_MARKERS,
)
from d1_pipeline.preflight import PreflightResult


class ExecutionMode(StrEnum):
    """Allowed execution modes for S5-D1 evaluation."""

    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    REAL_D1_AUTHORIZED = "REAL_D1_AUTHORIZED"


class AuthorizationError(RuntimeError):
    """Raised when real S5-D1 execution lacks valid investigator authorization."""


def authorization_template(
    *,
    gold_labels_sha256: str = "<SHA256_OF_VALIDATED_GOLD_JSON>",
    negative_control_sha256: str = "<SHA256_OF_VALIDATED_NEG_CONTROL_JSON>",
    pool_sha256: str = "<SHA256_OF_FROZEN_POOL_JSON>",
    rankings_sha256: str = "<SHA256_OF_FROZEN_RANKINGS_JSON>",
) -> dict[str, Any]:
    """Return a blank investigator-authorization template (never auto-signed)."""
    return {
        "schema_version": AUTH_SCHEMA_VERSION,
        "authorization_status": "",
        "investigator_id": "",
        "explicit_approval_declaration": "",
        "approved_at_utc": "",
        "gold_labels_sha256": gold_labels_sha256,
        "negative_control_sha256": negative_control_sha256,
        "pool_sha256": pool_sha256,
        "rankings_sha256": rankings_sha256,
    }


def _is_valid_iso8601_utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _is_valid_investigator_id(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    cleaned = value.strip()
    if not cleaned:
        return False
    return cleaned.upper() not in PLACEHOLDER_ID_MARKERS


def validate_investigator_authorization(
    *,
    authorize_real_d1_flag: bool,
    auth_artifact_path: Path | None,
    preflight: PreflightResult,
) -> dict[str, Any]:
    """Enforce the two-factor investigator authorization gate for real S5-D1.

    Raises:
        AuthorizationError: If any requirement fails.
    """
    errors: list[str] = []

    if not authorize_real_d1_flag:
        errors.append("Missing explicit --authorize-real-d1 CLI flag")
    if not preflight.passed:
        errors.append("Preflight validation did not pass; real S5-D1 is blocked")
    if preflight.is_synthetic:
        errors.append("Cannot authorize real S5-D1 using synthetic preflight results")
    if auth_artifact_path is None:
        errors.append("Missing --auth-artifact path to investigator authorization JSON")
    elif not auth_artifact_path.exists() or not auth_artifact_path.is_file():
        errors.append(f"Authorization artifact file does not exist: {auth_artifact_path}")

    if errors:
        raise AuthorizationError("Real S5-D1 authorization refused:\n- " + "\n- ".join(errors))

    assert auth_artifact_path is not None
    try:
        payload = json.loads(auth_artifact_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Authorization artifact root must be a JSON object")
    except (OSError, ValueError) as exc:
        raise AuthorizationError(f"Failed to parse authorization artifact: {exc}") from exc

    if payload.get("schema_version") != AUTH_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {AUTH_SCHEMA_VERSION!r}, got {payload.get('schema_version')!r}"
        )
    if payload.get("authorization_status") != AUTH_APPROVED_STATUS:
        errors.append(
            f"authorization_status must be {AUTH_APPROVED_STATUS!r}, got {payload.get('authorization_status')!r}"
        )
    if not _is_valid_investigator_id(payload.get("investigator_id")):
        errors.append(
            f"investigator_id must be a valid non-placeholder human identifier, got {payload.get('investigator_id')!r}"
        )
    declaration = payload.get("explicit_approval_declaration")
    if not isinstance(declaration, str) or len(declaration.strip()) < MIN_APPROVAL_DECLARATION_CHARS:
        errors.append("explicit_approval_declaration must be a substantive human approval statement")
    if not _is_valid_iso8601_utc(payload.get("approved_at_utc")):
        errors.append(f"approved_at_utc must be a timezone-aware ISO-8601 timestamp, got {payload.get('approved_at_utc')!r}")

    hash_checks = (
        ("gold_labels_sha256", preflight.gold_labels_sha256),
        ("negative_control_sha256", preflight.neg_control_sha256),
        ("pool_sha256", preflight.pool_sha256),
        ("rankings_sha256", preflight.rankings_sha256),
    )
    for field_name, expected_sha in hash_checks:
        actual = payload.get(field_name)
        if not expected_sha or actual != expected_sha:
            errors.append(f"{field_name} mismatch: expected {expected_sha!r}, got {actual!r}")

    if errors:
        raise AuthorizationError("Real S5-D1 authorization refused:\n- " + "\n- ".join(errors))

    return {
        "authorized": True,
        "investigator_id": payload["investigator_id"].strip(),
        "approved_at_utc": payload["approved_at_utc"].strip(),
        "auth_artifact_path": str(auth_artifact_path),
    }
