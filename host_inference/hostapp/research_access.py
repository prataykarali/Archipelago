"""Hosted staff-only research access shared by route and request guard."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging

logger = logging.getLogger("archipelago.research.audit")
STAFF_ROLES = frozenset(("faculty", "librarian", "administrator"))


def staff_allowed(role: str | None) -> bool:
    """Default-deny research access for the hosted app."""
    return role in STAFF_ROLES


def audit_access(user_id: str | None, role: str | None, result: str) -> None:
    """Record a hosted research access decision without session material."""
    logger.info(
        json.dumps(
            {
                "user_id": user_id,
                "role": role,
                "action": "research_access",
                "research_job_id": None,
                "topic": None,
                "timestamp": datetime.now(UTC).isoformat(),
                "result": result,
            },
            sort_keys=True,
        )
    )
