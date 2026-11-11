"""Service-key queue operations for the local research workstation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import time
from typing import Any

import requests

REQUEST_TIMEOUT_SECONDS = 20
REQUEST_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1
RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
STALE_JOB_MINUTES = 15
QUEUE_COLUMNS = "job_id,user_id,role,topic,paper_limit,status,created_at,updated_at"


class ResearchQueueStore:
    """Poll and checkpoint work through the existing Supabase project."""

    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        self.url = (url or os.getenv("SUPABASE_URL", "")).strip().rstrip("/")
        self.key = (
            key
            or os.getenv("SUPABASE_SECRET_KEY", "")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        ).strip()
        if not self.url or not self.key:
            raise RuntimeError("Supabase research queue credentials are unavailable")
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, table: str, **kwargs: Any) -> Any:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        for attempt in range(REQUEST_ATTEMPTS):
            try:
                response = requests.request(
                    method,
                    f"{self.url}/rest/v1/{table}",
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    **kwargs,
                )
            except (requests.ConnectionError, requests.Timeout):
                if attempt + 1 == REQUEST_ATTEMPTS:
                    raise
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            if response.status_code in RETRYABLE_STATUS_CODES and attempt + 1 < REQUEST_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            response.raise_for_status()
            return response.json() if response.content else None
        raise RuntimeError("Research queue request exhausted its retries")

    def heartbeat(self, worker_id: str, model_status: str, processed_jobs: int) -> None:
        """Keep the hosted status accurate even while no job is waiting."""
        self._request(
            "POST",
            "research_worker_heartbeats",
            params={"on_conflict": "worker_id"},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            json={
                "worker_id": worker_id,
                "last_seen_at": datetime.now(UTC).isoformat(),
                "model_status": model_status,
                "processed_jobs": processed_jobs,
            },
        )

    def recover_stale_jobs(self) -> int:
        """Retry jobs stranded by a laptop shutdown after a bounded lease."""
        cutoff = (datetime.now(UTC) - timedelta(minutes=STALE_JOB_MINUTES)).isoformat()
        rows = self._request(
            "GET",
            "research_processing_jobs",
            params={
                "status": "eq.running",
                "updated_at": f"lt.{cutoff}",
                "select": "job_id",
                "limit": 20,
            },
        )
        recovered = 0
        for row in rows or []:
            changed = self._request(
                "PATCH",
                "research_processing_jobs",
                params={"job_id": f"eq.{row['job_id']}", "status": "eq.running"},
                headers={"Prefer": "return=representation"},
                json={
                    "status": "queued",
                    "stage": "RETRY_QUEUED",
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
            recovered += bool(changed)
        return recovered

    def claim_next(self, worker_id: str) -> dict[str, Any] | None:
        """Claim one queued row atomically through a conditional PATCH."""
        rows = self._request(
            "GET",
            "research_processing_jobs",
            params={
                "status": "eq.queued",
                "select": QUEUE_COLUMNS,
                "order": "created_at.asc",
                "limit": 1,
            },
        )
        if not rows:
            return None
        job_id = rows[0]["job_id"]
        changed = self._request(
            "PATCH",
            "research_processing_jobs",
            params={"job_id": f"eq.{job_id}", "status": "eq.queued"},
            headers={"Prefer": "return=representation"},
            json={
                "status": "running",
                "stage": "SOURCE_DISCOVERY",
                "worker_id": worker_id,
                "started_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        return changed[0] if isinstance(changed, list) and changed else None

    def update_job(self, job_id: str, **fields: Any) -> None:
        """Publish a progress checkpoint visible to the Vercel page."""
        fields["updated_at"] = datetime.now(UTC).isoformat()
        self._request(
            "PATCH",
            "research_processing_jobs",
            params={"job_id": f"eq.{job_id}"},
            headers={"Prefer": "return=minimal"},
            json=fields,
        )

    def save_result(self, row: dict[str, Any]) -> None:
        """Upsert one finished paper so retries never duplicate it."""
        self._request(
            "POST",
            "research_processing_papers",
            params={"on_conflict": "job_id,paper_id"},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            json=row,
        )

    def save_intake_record(self, row: dict[str, Any]) -> None:
        """Feed the normal hosted research graph and chat from local ingestion."""
        existing = self._request(
            "GET",
            "research_intake_records",
            params={"record_key": f"eq.{row['record_key']}", "select": "metadata", "limit": 1},
        )
        if existing:
            row["metadata"] = {**existing[0].get("metadata", {}), **row["metadata"]}
        self._request(
            "POST",
            "research_intake_records",
            params={"on_conflict": "record_key"},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            json=row,
        )
