"""Privacy-safe real user-activity traffic tracker for librarian analytics."""

from __future__ import annotations

from collections import Counter, deque
from datetime import UTC, datetime
import hashlib
import threading
from typing import Any
from zoneinfo import ZoneInfo

_LOCK = threading.Lock()
_EVENTS: deque[dict[str, Any]] = deque(maxlen=2000)

ACTION_LABELS = {
    "chat_query": "AI Chat Queries",
    "research_search": "Research Searches",
    "reader_open": "PDF Reader Opens",
    "graph_explore": "Graph Explorations",
    "quiz_activity": "Diagnostic Quizzes",
    "page_visit": "Page Visits",
}


def _session_hash(raw_id: str | None = None) -> str:
    if not raw_id:
        try:
            from flask import request

            raw_id = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or request.remote_addr
                or "anon"
            ) + "|" + request.headers.get("User-Agent", "")[:64]
        except RuntimeError:
            raw_id = "anon"
    return hashlib.sha256(raw_id.encode("utf-8", errors="ignore")).hexdigest()[:12]


def record_user_action(
    action: str,
    detail: str = "",
    session_id: str | None = None,
) -> None:
    """Record one anonymized user activity event for the real traffic graph."""
    clean_action = action if action in ACTION_LABELS else "page_visit"
    clean_detail = " ".join(str(detail or "").split())[:80]
    event = {
        "action": clean_action,
        "detail": clean_detail,
        "session_hash": _session_hash(session_id),
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    with _LOCK:
        _EVENTS.append(event)


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
