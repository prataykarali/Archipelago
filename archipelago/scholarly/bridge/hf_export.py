"""Publish versioned paper OKF JSONL to the configured Hugging Face dataset."""

from __future__ import annotations

from io import BytesIO
import json
import logging
import os
from typing import Any

import requests

DEFAULT_DATASET_REPO = "Prataykarali/graphier"
DEFAULT_LIBRARY_REPO = "Prataykarali/Library_books"
MAX_LIBRARY_FACTS = 8
MAX_LIBRARY_VALUE_CHARS = 160
LOGGER = logging.getLogger(__name__)


def publish_okf_dataset(job_id: str, records: list[dict[str, Any]]) -> dict[str, str]:
    """Upload one idempotent job file; never upload source PDFs."""
    token = os.getenv("HF_TOKEN")
    if not token:
        return {"status": "skipped", "reason": "HF_TOKEN missing"}
    if not records:
        return {"status": "skipped", "reason": "No OKF records"}
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {"status": "skipped", "reason": "huggingface_hub missing"}
    repo_id = os.getenv("ARCHIPELAGO_SCHOLARLY_HF_REPO", DEFAULT_DATASET_REPO)
    content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    path = f"datasets/research_okf/{job_id}.jsonl"
    try:
        HfApi(token=token).upload_file(
            path_or_fileobj=BytesIO(content.encode("utf-8")),
            path_in_repo=path,
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"data: update research OKF session {job_id}",
        )
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        LOGGER.exception("Research OKF dataset upload failed")
        return {"status": "failed", "reason": type(exc).__name__}
    return {"status": "published", "repo_id": repo_id, "path": path}


def publish_library_papers(job_id: str, records: list[dict[str, Any]]) -> dict[str, str]:
    """Publish paper pointers and bounded verified facts without copying PDFs."""
    token = os.getenv("HF_TOKEN")
    if not token:
        return {"status": "skipped", "reason": "HF_TOKEN missing"}
    if not records:
        return {"status": "skipped", "reason": "No paper records"}
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {"status": "skipped", "reason": "huggingface_hub missing"}
    repo_id = os.getenv("HF_LIBRARY_REPO", DEFAULT_LIBRARY_REPO)
    path = f"catalogs/research_papers/{job_id}.jsonl"
    public_fields = ("record_key", "title", "source_url", "source_name", "topic", "published_at")
    lines = [
        json.dumps(
            {
                **{field: record.get(field) for field in public_fields},
                "doi": (record.get("metadata") or {}).get("doi"),
                "arxiv_id": (record.get("metadata") or {}).get("arxiv_id"),
                "open_access_pdf": (record.get("metadata") or {}).get("open_access_pdf"),
                "access_state": (record.get("metadata") or {}).get("access_state"),
                "verified_facts": [
                    {
                        "group": fact.get("group"),
                        "field": fact.get("field"),
                        "value": str(fact.get("value") or "")[:MAX_LIBRARY_VALUE_CHARS],
                        "pdf_page": fact.get("pdf_page"),
                        "verification_status": fact.get("verification_status"),
                    }
                    for fact in (record.get("metadata") or {}).get("verified_extractions", [])[
                        :MAX_LIBRARY_FACTS
                    ]
                    if isinstance(fact, dict) and str(fact.get("value") or "").strip()
                ],
            },
            ensure_ascii=False,
        )
        for record in records
    ]
    try:
        HfApi(token=token).upload_file(
            path_or_fileobj=BytesIO(("\n".join(lines) + "\n").encode("utf-8")),
            path_in_repo=path,
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"data: index research paper sources for {job_id}",
        )
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        LOGGER.exception("Research paper catalogue upload failed")
        return {"status": "failed", "reason": type(exc).__name__}
    return {"status": "published", "repo_id": repo_id, "path": path}
