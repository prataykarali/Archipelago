"""Server-side capabilities for the staff Research Intelligence surface."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC
from enum import StrEnum
import functools
import logging
from typing import Any

from flask import g, jsonify, request

from archipelago import supabase_auth

logger = logging.getLogger("archipelago.research.audit")


class ResearchCapability(StrEnum):
    SEARCH = "search"
    JOB_CREATE = "job_create"
    EVIDENCE_READ = "evidence_read"
    FEATURE_READ = "feature_read"
    TOPIC_TRACK = "topic_track"
    REFRESH_CONTROL = "refresh_control"
    SOURCE_HEALTH = "source_health"
    REVIEW = "review"
    CONNECTOR_CONFIG = "connector_config"


STAFF_ROLES = frozenset({"faculty", "librarian", "administrator"})
MANAGER_ROLES = frozenset({"librarian", "administrator"})
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
    }
)


def allowed(
    role: str | None,
    capability: ResearchCapability,
    grants: Iterable[str] = (),
) -> bool:
    """Apply the default-deny role matrix plus explicit trusted grants."""
    if role not in STAFF_ROLES:
        return False
    if role == "administrator":
        return True
    if capability in STAFF_CAPABILITIES:
        return True
    if role == "librarian" and capability in MANAGER_CAPABILITIES:
        return True
    return capability.value in grants


def audit_action(
    *,
    user_id: str | None,
    role: str | None,
    action: str,
    result: str,
    research_job_id: str | None = None,
    topic: str | None = None,
) -> None:
    """Emit a structured audit event without credentials or paper content."""
    from datetime import datetime
    import json

    logger.info(
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


def require_research(
    capability: ResearchCapability,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require a verified individual principal even when reading is open."""

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def guarded(*args: Any, **kwargs: Any) -> Any:
            if request.method == "OPTIONS":
                return fn(*args, **kwargs)
            principal, _error = supabase_auth.authenticate_request(request)
            if principal is None:
                audit_action(
                    user_id=None, role=None, action=capability.value, result="unauthorized"
                )
                return jsonify({"error": "unauthorized"}), 401
            if not allowed(principal.role, capability):
                audit_action(
                    user_id=principal.user_id,
                    role=principal.role,
                    action=capability.value,
                    result="forbidden",
                )
                return jsonify({"error": "forbidden"}), 403
            g.archipelago_principal = principal
            return fn(*args, **kwargs)

        return guarded

    return decorate
