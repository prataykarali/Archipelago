"""Durable hosted-session state shared by all Vercel instances."""

from __future__ import annotations

import base64
import json
from typing import Any
import uuid

from .runtime_state import runtime_rpc

SESSION_RPC_NAME = "archipelago_runtime_session_rpc"
SESSION_ID_CLAIM = "session_id"
USER_ID_CLAIM = "sub"


def verified_session_ids(token: str, verified_user_id: str) -> tuple[str, str] | None:
    """Extract identifiers only after Supabase has verified this bearer token."""
    if token.count(".") != 2:
        return None
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        if not isinstance(claims, dict):
            return None
        session_id = str(uuid.UUID(str(claims.get(SESSION_ID_CLAIM) or "")))
        user_id = str(uuid.UUID(verified_user_id))
        if str(uuid.UUID(str(claims.get(USER_ID_CLAIM) or ""))) != user_id:
            return None
        return session_id, user_id
    except (ValueError, TypeError, UnicodeError):
        return None


def session_action(
    operation: str,
    session_id: str,
    user_id: str,
    *,
    idle_seconds: int,
    max_age_seconds: int,
    passive: bool = False,
) -> dict[str, Any]:
    """Perform an atomic server-only session operation or raise on RPC failure."""
    result = runtime_rpc(
        SESSION_RPC_NAME,
        {
            "p_operation": operation,
            "p_session_id": session_id,
            "p_user_id": user_id,
            "p_idle_seconds": idle_seconds,
            "p_max_age_seconds": max_age_seconds,
            "p_passive": passive,
        },
    )
    if not isinstance(result, dict) or result.get("status") not in {
        "active",
        "idle_expired",
        "absolute_expired",
        "revoked_credentials",
        "missing_session",
    }:
        raise RuntimeError("Durable session RPC returned an invalid response")
    return result
