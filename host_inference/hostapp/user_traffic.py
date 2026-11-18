"""Privacy-safe real user-activity traffic tracker for librarian analytics."""

from __future__ import annotations

import atexit
from collections import Counter, deque
from datetime import UTC, datetime
import hashlib
import os
import re
import threading
from typing import Any
from zoneinfo import ZoneInfo

_LOCK = threading.Lock()
_EVENTS: deque[dict[str, Any]] = deque(maxlen=2000)
_SHUTTING_DOWN = False

_TRUSTED_IP_HEADERS = ("X-Vercel-Forwarded-For", "CF-Connecting-IP", "Fly-Client-IP", "X-Real-IP")
_PII_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SECRET_TOKEN_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]+|Bearer\s+\S+)\b", re.I)

ACTION_LABELS = {
    "chat_query": "AI Chat Queries",
    "research_search": "Research Searches",
    "reader_open": "PDF Reader Opens",
    "graph_explore": "Graph Explorations",
    "quiz_activity": "Diagnostic Quizzes",
    "page_visit": "Page Visits",
}


def _client_ip(req: Any) -> str:
    trust_proxy = bool(os.environ.get("VERCEL")) or os.environ.get("ARCHIPELAGO_TRUST_PROXY") == "1"
    if trust_proxy:
        for header in _TRUSTED_IP_HEADERS:
            val = req.headers.get(header)
            if val and val.strip():
                return str(val).strip().split(",")[-1].strip()
        forwarded = req.headers.get("X-Forwarded-For")
        if forwarded and forwarded.strip():
            return str(forwarded).strip().split(",")[-1].strip()
    return str(req.remote_addr or "anon")


def _session_hash(raw_id: str | None = None) -> str:
    if not raw_id:
        try:
            from flask import request

            raw_id = _client_ip(request) + "|" + request.headers.get("User-Agent", "")[:64]
        except RuntimeError:
            raw_id = "anon"
    return hashlib.sha256(raw_id.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _user_hash(user_id: str | None = None) -> str | None:
    if not user_id:
        try:
            from flask import request

            principal = getattr(request, "archipelago_principal", None)
            if isinstance(principal, dict) and principal.get("id"):
                user_id = str(principal["id"])
        except RuntimeError:
            user_id = None
    if not user_id:
        return None
    return hashlib.sha256(f"user:{user_id}".encode("utf-8", errors="ignore")).hexdigest()[:16]


def _scrub_detail(detail: str) -> str:
    cleaned = " ".join(str(detail or "").split())
    cleaned = _PII_EMAIL_RE.sub("[redacted-email]", cleaned)
    cleaned = _SECRET_TOKEN_RE.sub("[redacted-token]", cleaned)
    return cleaned[:80]


def record_user_action(
    action: str,
    detail: str = "",
    session_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Record one anonymized user activity event for the real traffic graph."""
    clean_action = action if action in ACTION_LABELS else "page_visit"
    clean_detail = _scrub_detail(detail)
    event = {
        "action": clean_action,
        "detail": clean_detail,
        "session_hash": _session_hash(session_id),
        "user_hash": _user_hash(user_id),
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    with _LOCK:
        _EVENTS.append(event)


def clear_user_traffic(user_id: str | None = None, session_id: str | None = None) -> int:
    """Delete recorded activity events belonging to the caller's user_id or session_id."""
    target_user = _user_hash(user_id) if user_id else None
    target_session = _session_hash(session_id) if session_id else None
    if not target_user and not target_session:
        return 0
    removed = 0
    with _LOCK:
        kept = deque(maxlen=_EVENTS.maxlen)
        for ev in _EVENTS:
            match_user = bool(target_user and ev.get("user_hash") == target_user)
            match_session = bool(target_session and ev.get("session_hash") == target_session)
            if match_user or match_session:
                removed += 1
            else:
                kept.append(ev)
        _EVENTS.clear()
        _EVENTS.extend(kept)
    return removed


def summarize_user_traffic(tz_name: str | None = None) -> dict[str, Any]:
    """Return hourly and per-action breakdown of what users are actually doing."""
    try:
        tz = ZoneInfo(tz_name) if tz_name else UTC
    except Exception:
        tz = UTC

    with _LOCK:
        snapshot = list(_EVENTS)

    by_action: Counter[str] = Counter()
    sessions: set[str] = set()
    hourly: dict[int, dict[str, int]] = {
        h: {
            "count": 0,
            "chat_query": 0,
            "research_search": 0,
            "reader_open": 0,
            "graph_explore": 0,
            "quiz_activity": 0,
            "page_visit": 0,
        }
        for h in range(24)
    }

    for ev in snapshot:
        act = ev["action"]
        by_action[act] += 1
        sessions.add(ev["session_hash"])
        try:
            dt = datetime.fromisoformat(ev["occurred_at"]).astimezone(tz)
            bucket = hourly[dt.hour]
            bucket["count"] += 1
            bucket[act] = bucket.get(act, 0) + 1
        except ValueError:
            continue

    hourly_series = [
        {"hour": f"{h:02d}:00", **hourly[h]} for h in range(24)
    ]
    recent = [
        {
            "action": ev["action"],
            "label": ACTION_LABELS.get(ev["action"], ev["action"]),
            "detail": ev["detail"],
            "occurred_at": ev["occurred_at"],
        }
        for ev in reversed(snapshot[-12:])
    ]

    return {
        "status": "active" if snapshot else "idle",
        "total_actions": len(snapshot),
        "unique_sessions": len(sessions),
        "by_action": {k: by_action.get(k, 0) for k in ACTION_LABELS},
        "action_labels": ACTION_LABELS,
        "hourly_activity": hourly_series,
        "recent_actions": recent,
    }


def flush_user_traffic() -> list[dict[str, Any]]:
    """Drain and return buffered in-memory user traffic events."""
    with _LOCK:
        flushed = list(_EVENTS)
        _EVENTS.clear()
    return flushed


def shutdown() -> None:
    """Gracefully flush buffered telemetry state on process shutdown."""
    global _SHUTTING_DOWN
    with _LOCK:
        _SHUTTING_DOWN = True
        _EVENTS.clear()


def _register_shutdown() -> None:
    atexit.register(shutdown)
    try:
        from . import runtime_state

        reg = getattr(runtime_state, "register_shutdown_callback", None)
        if callable(reg):
            reg(shutdown)
    except Exception:
        pass


_register_shutdown()
