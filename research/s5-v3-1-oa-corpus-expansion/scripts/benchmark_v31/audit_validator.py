"""Validator for S5-v3.1 blinded human query-audit workbooks & submissions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import (
    AUDIT_SCHEMA_VERSION,
    BLINDED_HIDDEN_KEYS,
    DECISION_ACCEPT,
    FORBIDDEN_PUBLIC_TEXT_KEYS,
    FORBIDDEN_RELEVANCE_GRADE_KEYS,
    MIN_RATIONALE_CHARS,
    VALID_HUMAN_DECISIONS,
    VALID_NC_CLASSIFICATIONS,
    VALID_TRI_STATE,
    WORKBOOK_STATUS_BLANK,
    WORKBOOK_STATUS_SUBMITTED,
)


@dataclass(frozen=True)
class AuditValidationIssue:
    """Single validation failure for a query-audit workbook or submission."""

    item_id: str
    code: str
    message: str


@dataclass
class AuditValidationResult:
    """Aggregated validation result for query-audit workbooks."""

    issues: list[AuditValidationIssue] = field(default_factory=list)
    item_count: int = 0

    @property
    def is_valid(self) -> bool:
        """Return True when zero validation issues exist."""
        return len(self.issues) == 0


def _scan_forbidden_keys(
    payload: Any,
    forbidden: frozenset[str],
    code: str,
    item_id: str,
    issues: list[AuditValidationIssue],
) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in forbidden:
                issues.append(
                    AuditValidationIssue(
                        item_id, code, f"Forbidden key '{key}' found."
                    )
                )
            _scan_forbidden_keys(value, forbidden, code, item_id, issues)
    elif isinstance(payload, list):
        for elem in payload:
            _scan_forbidden_keys(elem, forbidden, code, item_id, issues)


def _check_common(
    payload: dict[str, Any],
    expected_query_ids: frozenset[str] | None,
    require_no_raw_text: bool,
    issues: list[AuditValidationIssue],
) -> list[dict[str, Any]]:
    if payload.get("schema_version") != AUDIT_SCHEMA_VERSION:
        issues.append(
            AuditValidationIssue(
                "__WORKBOOK__",
                "INVALID_SCHEMA_VERSION",
                f"Expected schema_version '{AUDIT_SCHEMA_VERSION}'.",
            )
        )
    _scan_forbidden_keys(
        payload,
        FORBIDDEN_RELEVANCE_GRADE_KEYS,
        "FORBIDDEN_RELEVANCE_GRADE_FIELD",
        "__WORKBOOK__",
        issues,
    )
    if require_no_raw_text:
        _scan_forbidden_keys(
            payload,
            FORBIDDEN_PUBLIC_TEXT_KEYS,
            "FORBIDDEN_RAW_TEXT_IN_PUBLIC_ARTIFACT",
            "__WORKBOOK__",
            issues,
        )

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        issues.append(
            AuditValidationIssue(
                "__WORKBOOK__", "MISSING_ITEMS", "Workbook has no items."
            )
        )
        return []

    seen_qids: set[str] = set()
    for item in items:
        iid = str(item.get("blinded_item_id", "__ITEM__"))
        qid = str(item.get("query_id", ""))
        if not qid or qid in seen_qids:
            issues.append(
                AuditValidationIssue(
                    iid, "BAD_OR_DUP_QUERY_ID", f"Bad/dup query_id '{qid}'."
                )
            )
        seen_qids.add(qid)
        for hidden in BLINDED_HIDDEN_KEYS:
            if hidden in item:
                issues.append(
                    AuditValidationIssue(
                        iid,
                        "BLINDING_VIOLATION",
                        f"Blinded item must not expose '{hidden}'.",
                    )
                )

    if expected_query_ids is not None and seen_qids != expected_query_ids:
        issues.append(
            AuditValidationIssue(
                "__WORKBOOK__",
                "QUERY_COVERAGE_MISMATCH",
                "Workbook query_id set does not match proposed manifest.",
            )
        )
    return items


def validate_blank_workbook(
    payload: dict[str, Any],
    expected_query_ids: frozenset[str] | None = None,
    require_no_raw_text: bool = False,
) -> AuditValidationResult:
    """Reject any pre-filled human decisions, classifications, or signatures."""
    issues: list[AuditValidationIssue] = []
    items = _check_common(
        payload, expected_query_ids, require_no_raw_text, issues
    )
    if payload.get("workbook_status") != WORKBOOK_STATUS_BLANK:
        issues.append(
            AuditValidationIssue(
                "__WORKBOOK__",
                "NOT_BLANK_STATUS",
                f"Expected workbook_status='{WORKBOOK_STATUS_BLANK}'.",
            )
        )

    att = payload.get("reviewer_attestation", {})
    if not isinstance(att, dict) or att.get("reviewer_attestation_signed") is not False:
        issues.append(
            AuditValidationIssue(
                "__WORKBOOK__",
                "PREFILLED_SIGNATURE",
                "Blank workbook must have reviewer_attestation_signed=False.",
            )
        )
    if isinstance(att, dict):
        for fname in (
            "reviewer_id",
            "attestation_signer",
            "signed_timestamp_utc",
        ):
            if str(att.get(fname, "")).strip():
                issues.append(
                    AuditValidationIssue(
                        "__WORKBOOK__",
                        "PREFILLED_REVIEWER_METADATA",
                        f"Blank workbook must leave '{fname}' empty.",
                    )
                )

    for item in items:
        iid = str(item.get("blinded_item_id", "__ITEM__"))
        for fname in (
            "human_decision",
            "human_necessity_verified",
            "human_shortcut_found",
            "human_negative_control_classification",
            "human_correction_or_rationale",
        ):
            if str(item.get(fname, "")).strip():
                issues.append(
                    AuditValidationIssue(
                        iid,
                        "PREFILLED_HUMAN_DECISION",
                        f"Blank workbook must leave '{fname}' empty.",
                    )
                )
    return AuditValidationResult(issues=issues, item_count=len(items))


def validate_completed_submission(
    payload: dict[str, Any],
    expected_query_ids: frozenset[str] | None = None,
) -> AuditValidationResult:
    """Validate a completed human submission; reject unsigned or incomplete."""
    issues: list[AuditValidationIssue] = []
    items = _check_common(
        payload, expected_query_ids, require_no_raw_text=False, issues=issues
    )
    if payload.get("workbook_status") != WORKBOOK_STATUS_SUBMITTED:
        issues.append(
            AuditValidationIssue(
                "__WORKBOOK__",
                "INVALID_SUBMISSION_STATUS",
                f"Expected workbook_status='{WORKBOOK_STATUS_SUBMITTED}'.",
            )
        )

    att = payload.get("reviewer_attestation", {})
    if not isinstance(att, dict) or att.get("reviewer_attestation_signed") is not True:
        issues.append(
            AuditValidationIssue(
                "__WORKBOOK__",
                "UNSIGNED_ATTESTATION",
                "Completed submission requires reviewer_attestation_signed=True.",
            )
        )
    if isinstance(att, dict):
        for fname in (
            "reviewer_id",
            "attestation_signer",
            "signed_timestamp_utc",
        ):
            if not str(att.get(fname, "")).strip():
                issues.append(
                    AuditValidationIssue(
                        "__WORKBOOK__",
                        "MISSING_REVIEWER_METADATA",
                        f"Submission requires non-empty '{fname}'.",
                    )
                )

    for item in items:
        iid = str(item.get("blinded_item_id", "__ITEM__"))
        decision = str(item.get("human_decision", "")).strip()
        if decision not in VALID_HUMAN_DECISIONS:
            issues.append(
                AuditValidationIssue(
                    iid,
                    "INVALID_OR_BLANK_DECISION",
                    f"human_decision must be in {sorted(VALID_HUMAN_DECISIONS)}.",
                )
            )
        for tri_field in ("human_necessity_verified", "human_shortcut_found"):
            if str(item.get(tri_field, "")).strip() not in VALID_TRI_STATE:
                issues.append(
                    AuditValidationIssue(
                        iid,
                        "INVALID_TRI_STATE_FIELD",
                        f"{tri_field} must be in {sorted(VALID_TRI_STATE)}.",
                    )
                )
        nc_cls = str(
            item.get("human_negative_control_classification", "")
        ).strip()
        if nc_cls not in VALID_NC_CLASSIFICATIONS:
            issues.append(
                AuditValidationIssue(
                    iid,
                    "INVALID_NC_CLASSIFICATION",
                    "Missing or invalid human_negative_control_classification.",
                )
            )
        rationale = str(item.get("human_correction_or_rationale", "")).strip()
        if decision != DECISION_ACCEPT and len(rationale) < MIN_RATIONALE_CHARS:
            issues.append(
                AuditValidationIssue(
                    iid,
                    "MISSING_CORRECTION_RATIONALE",
                    "REVISE/REJECT requires human_correction_or_rationale.",
                )
            )
    return AuditValidationResult(issues=issues, item_count=len(items))
