"""Server-only access to the durable local research worker queue."""

from __future__ import annotations

import atexit
from datetime import UTC, datetime, timedelta
import os
import re
import threading
from typing import Any

import requests

API_TIMEOUT_SECONDS = 10
WORKER_STALE_SECONDS = 120
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
_SESSION_LOCK = threading.Lock()
_SESSION: requests.Session | None = requests.Session()


def _http_get(url: str, **kwargs: Any) -> requests.Response:
    if getattr(requests.get, "__module__", "") != "requests.api":
        return requests.get(url, **kwargs)
    with _SESSION_LOCK:
        session = _SESSION
    if session is not None:
        return session.get(url, **kwargs)
    return requests.get(url, **kwargs)


def _http_post(url: str, **kwargs: Any) -> requests.Response:
    if getattr(requests.post, "__module__", "") != "requests.api":
        return requests.post(url, **kwargs)
    with _SESSION_LOCK:
        session = _SESSION
    if session is not None:
        return session.post(url, **kwargs)
    return requests.post(url, **kwargs)


def _validate_id(value: str, field: str = "id") -> str:
    cleaned = str(value or "").strip()
    if not _SAFE_ID_RE.fullmatch(cleaned):
        raise ValueError(f"invalid_{field}")
    return cleaned
JOB_COLUMNS = (
    "job_id,user_id,role,topic,paper_limit,status,stage,fetched_count,"
    "processed_count,fulltext_count,result_summary,error,created_at,updated_at,completed_at"
)
PAPER_COLUMNS = (
    "paper_id,title,source_url,source_name,access_state,created_at,"
    "abstract:okf->parameters->paper_identity->abstract->>value,"
    "doi:okf->parameters->paper_identity->doi->>value,"
    "citations:okf->parameters->citation_metrics->citation_count->>value,"
    "references:okf->parameters->citation_metrics->reference_count->>value,"
    "first_author_h_index:okf->parameters->author_metrics->h_index->>value,"
    "method:okf->parameters->methodology->techniques->>value"
)


def _api(path: str) -> tuple[str, dict[str, str]]:
    """Build a service-only Supabase Data API request."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url or not key:
        raise RuntimeError("Research queue storage is not configured")
    return f"{url}/rest/v1/{path}", {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def enqueue_job(user_id: str, role: str, topic: str, paper_limit: int) -> dict[str, Any]:
    """Use the database's atomic per-user rate and concurrency gate."""
    clean_user = _validate_id(user_id, "user_id")
    endpoint, headers = _api("rpc/research_enqueue_job")
    response = _http_post(
        endpoint,
        headers=headers,
        json={
            "p_user_id": clean_user,
            "p_role": role,
            "p_topic": topic,
            "p_paper_limit": paper_limit,
        },
        timeout=API_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        try:
            detail = str(response.json().get("message") or "")
        except ValueError:
            detail = ""
        if detail in {
            "research_rate_limited",
            "research_job_in_progress",
            "research_queue_full",
            "invalid_research_job",
        }:
            raise ValueError(detail)
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or not result.get("job_id"):
        raise ValueError("Research queue returned an invalid job")
    return result


def get_job(job_id: str) -> dict[str, Any] | None:
    """Fetch one job; the route checks owner or manager access."""
    clean_job_id = _validate_id(job_id, "job_id")
    endpoint, headers = _api("research_processing_jobs")
    response = _http_get(
        endpoint,
        headers=headers,
        params={"job_id": f"eq.{clean_job_id}", "select": JOB_COLUMNS, "limit": 1},
        timeout=API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if isinstance(rows, list) and rows else None


def latest_job(user_id: str | None) -> dict[str, Any] | None:
    """Recover the last request; managers see the latest library-wide session."""
    endpoint, headers = _api("research_processing_jobs")
    params = {
        "select": JOB_COLUMNS,
        "order": "created_at.desc",
        "limit": 1,
    }
    if user_id is not None:
        params["user_id"] = f"eq.{_validate_id(user_id, 'user_id')}"
    response = _http_get(
        endpoint,
        headers=headers,
        params=params,
        timeout=API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if isinstance(rows, list) and rows else None


def list_job_papers(job_id: str) -> list[dict[str, Any]]:
    """Return small result cards; individual OKF JSON is fetched separately."""
    clean_job_id = _validate_id(job_id, "job_id")
    endpoint, headers = _api("research_processing_papers")
    response = _http_get(
        endpoint,
        headers=headers,
        params={"job_id": f"eq.{clean_job_id}", "select": PAPER_COLUMNS, "limit": 30},
        timeout=API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    return rows if isinstance(rows, list) else []


def list_job_okf(job_id: str) -> list[dict[str, Any]]:
    """Fetch every OKF object for an on-demand complete session export."""
    clean_job_id = _validate_id(job_id, "job_id")
    endpoint, headers = _api("research_processing_papers")
    response = _http_get(
        endpoint,
        headers=headers,
        params={
            "job_id": f"eq.{clean_job_id}",
            "select": "paper_id,title,source_url,source_name,access_state,okf,created_at",
            "order": "created_at.asc",
            "limit": 30,
        },
        timeout=API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    return rows if isinstance(rows, list) else []


def get_paper_okf(job_id: str, paper_id: str) -> dict[str, Any] | None:
    """Read a worker-produced paper object with verified evidence pointers."""
    clean_job_id = _validate_id(job_id, "job_id")
    clean_paper_id = _validate_id(paper_id, "paper_id")
    endpoint, headers = _api("research_processing_papers")
    response = _http_get(
        endpoint,
        headers=headers,
        params={
            "job_id": f"eq.{clean_job_id}",
            "paper_id": f"eq.{clean_paper_id}",
            "select": "okf",
            "limit": 1,
        },
        timeout=API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0]["okf"] if isinstance(rows, list) and rows else None


def worker_status() -> dict[str, Any]:
    """Report offline when the laptop has not sent a recent heartbeat."""
    endpoint, headers = _api("research_worker_heartbeats")
    response = _http_get(
        endpoint,
        headers=headers,
        params={
            "select": "last_seen_at,model_status,processed_jobs",
            "order": "last_seen_at.desc",
            "limit": 1,
        },
        timeout=API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        return {"online": False, "state": "system_offline", "last_seen_at": None}
    row = rows[0]
    seen = datetime.fromisoformat(str(row["last_seen_at"]).replace("Z", "+00:00"))
    online = datetime.now(UTC) - seen <= timedelta(seconds=WORKER_STALE_SECONDS)
    return {
        "online": online,
        "state": "online" if online else "system_offline",
        "last_seen_at": row["last_seen_at"],
        "model_status": row["model_status"],
        "processed_jobs": row["processed_jobs"],
    }


def shutdown() -> None:
    """Close pooled HTTP session on process shutdown."""
    global _SESSION
    with _SESSION_LOCK:
        session, _SESSION = _SESSION, None
    if session is not None:
        try:
            session.close()
        except Exception:
            pass


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
