"""Read one published paper evidence row from the private Library_books dataset."""

from __future__ import annotations

from functools import lru_cache
import json
import os
import re
from typing import Any

import requests

LIBRARY_REPO_DEFAULT = "Prataykarali/Library_books"
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
RECORD_KEY_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MAX_CATALOG_BYTES = 2_000_000
FETCH_TIMEOUT_SECONDS = 6
STREAM_CHUNK_BYTES = 65536
CATALOG_CACHE_JOBS = 32


@lru_cache(maxsize=CATALOG_CACHE_JOBS)
def _read_job_catalog(repo: str, job_id: str, token: str) -> tuple[dict[str, Any], ...]:
    """Fetch one immutable job file once per warm server process."""
    path = f"catalogs/research_papers/{job_id}.jsonl"
    url = f"https://huggingface.co/datasets/{repo}/resolve/main/{path}"
    with requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=FETCH_TIMEOUT_SECONDS,
    ) as response:
        response.raise_for_status()
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=STREAM_CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_CATALOG_BYTES:
                raise ValueError("Research paper catalogue exceeds size limit")
            chunks.append(chunk)
    records = []
    for line in b"".join(chunks).splitlines():
        item = json.loads(line)
        if isinstance(item, dict):
            records.append(item)
    return tuple(records)


def library_paper_evidence(row: dict[str, Any]) -> dict[str, Any] | None:
    """Find the paper's bounded facts in its immutable research-job export."""
    metadata = row.get("metadata") or {}
    job_id = str(metadata.get("ingestion_job_id") or "")
    record_key = str(row.get("record_key") or "")
    token = os.getenv("HF_TOKEN", "").strip()
    if (
        not token
        or not JOB_ID_PATTERN.fullmatch(job_id)
        or not RECORD_KEY_PATTERN.fullmatch(record_key)
    ):
        return None
    repo = os.getenv("HF_LIBRARY_REPO", LIBRARY_REPO_DEFAULT)
    path = f"catalogs/research_papers/{job_id}.jsonl"
    try:
        records = _read_job_catalog(repo, job_id, token)
    except (requests.RequestException, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    for item in records:
        if item.get("record_key") == record_key:
            return {**item, "library_repo": repo, "library_path": path}
    return None
