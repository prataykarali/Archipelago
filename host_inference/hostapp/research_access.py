"""Research permissions and audit events for the standalone hosted service."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import json
import logging


class ResearchCapability(StrEnum):
    """Actions available on the staff research surface."""

    SEARCH = "search"
    JOB_CREATE = "job_create"
    EVIDENCE_READ = "evidence_read"
    FEATURE_READ = "feature_read"
    TOPIC_TRACK = "topic_track"
    REFRESH_CONTROL = "refresh_control"
    SOURCE_HEALTH = "source_health"
    REVIEW = "review"
    GRAPH_EDIT = "graph_edit"
    CONNECTOR_CONFIG = "connector_config"


STAFF_ROLES = frozenset({"faculty", "librarian", "administrator"})
STAFF_CAPABILITIES = frozenset(
    {
        ResearchCapability.SEARCH,
        ResearchCapability.JOB_CREATE,
        ResearchCapability.EVIDENCE_READ,
        ResearchCapability.FEATURE_READ,
        ResearchCapability.TOPIC_TRACK,
    }
)
MANAGER_CAPABILITIES = frozenset(
    {
        ResearchCapability.REFRESH_CONTROL,
        ResearchCapability.SOURCE_HEALTH,
        ResearchCapability.REVIEW,
        ResearchCapability.GRAPH_EDIT,
    }
)


def allowed(role: str | None, capability: ResearchCapability) -> bool:
    """Deny students and grant staff only their approved actions."""
    if role not in STAFF_ROLES:
        return False
    if role == "administrator":
        return True
    if capability in STAFF_CAPABILITIES:
        return True
    return role == "librarian" and capability in MANAGER_CAPABILITIES


def audit_action(
    *,
    user_id: str | None,
    role: str | None,
    action: str,
    result: str,
    research_job_id: str | None = None,
    topic: str | None = None,
) -> None:
    """Write a structured access record without credentials or paper content."""
    logging.getLogger("archipelago.research.audit").info(
        json.dumps(
            {
                "user_id": user_id,
                "role": role,
                "action": action,
                "research_job_id": research_job_id,
                "topic": topic,
                "timestamp": datetime.now(UTC).isoformat(),
                "result": result,
            },
            sort_keys=True,
        )
    )
