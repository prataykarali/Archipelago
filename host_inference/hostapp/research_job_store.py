"""Server-only access to the durable local research worker queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from typing import Any

import requests

API_TIMEOUT_SECONDS = 10
WORKER_STALE_SECONDS = 120
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
    endpoint, headers = _api("rpc/research_enqueue_job")
    response = requests.post(
        endpoint,
        headers=headers,
        json={
            "p_user_id": user_id,
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
    endpoint, headers = _api("research_processing_jobs")
    response = requests.get(
        endpoint,
        headers=headers,
        params={"job_id": f"eq.{job_id}", "select": JOB_COLUMNS, "limit": 1},
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
        params["user_id"] = f"eq.{user_id}"
    response = requests.get(
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
    endpoint, headers = _api("research_processing_papers")
    response = requests.get(
        endpoint,
        headers=headers,
        params={"job_id": f"eq.{job_id}", "select": PAPER_COLUMNS, "limit": 30},
        timeout=API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    return rows if isinstance(rows, list) else []


def list_job_okf(job_id: str) -> list[dict[str, Any]]:
    """Fetch every OKF object for an on-demand complete session export."""
    endpoint, headers = _api("research_processing_papers")
    response = requests.get(
        endpoint,
        headers=headers,
        params={
            "job_id": f"eq.{job_id}",
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
    endpoint, headers = _api("research_processing_papers")
    response = requests.get(
        endpoint,
        headers=headers,
        params={
            "job_id": f"eq.{job_id}",
            "paper_id": f"eq.{paper_id}",
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
    response = requests.get(
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
