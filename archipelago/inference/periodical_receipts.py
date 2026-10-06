"""Normalize issue-level serial receipt records without inventing delivery dates."""

from __future__ import annotations

from collections.abc import Mapping

RECEIVED_ALIASES = frozenset({"received", "arrived", "delivered"})
LATE_ALIASES = frozenset({"late", "overdue"})
EXPECTED_ALIASES = frozenset({"expected", "pending", "awaited"})


def normalize_receipt_status(raw_status: str) -> str:
    """Return a supported status; never infer receipt from a blank cell."""
    value = raw_status.strip().casefold()
    if value in RECEIVED_ALIASES:
        return "Received"
    if value in LATE_ALIASES:
        return "Late"
    if value in EXPECTED_ALIASES:
        return "Expected"
    return "Unknown"


def issue_receipt(cleaned_row: Mapping[str, str]) -> dict[str, str] | None:
    """Preserve one identified issue and its source-reported delivery status."""
    journal_title = cleaned_row.get("journal title", "").strip()
    issue_label = cleaned_row.get("issue count", "").strip()
    if not journal_title or not issue_label:
        return None
    raw_status = cleaned_row.get("issue status", "").strip()
    return {
        "journal_title": journal_title,
        "issue_label": issue_label,
        "published_date": cleaned_row.get("published date", "").strip(),
        "status": normalize_receipt_status(raw_status),
        "source_status": raw_status,
    }
