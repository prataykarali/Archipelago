"""Enumerate verified Hugging Face resources as reader metadata."""

from __future__ import annotations

from collections.abc import Callable
import datetime
from typing import Any


def enumerate_hf_resources(
    repo_id: str,
    repo_type: str,
    revision: str,
    hf_token: str | None,
    get_files: Callable[..., set[str]],
) -> list[dict[str, Any]]:
    """Enumerate all books and papers present in the Hugging Face repository."""
    files = get_files(repo_id=repo_id, repo_type=repo_type, hf_token=hf_token)
    resources = []
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()

    for f in sorted(files):
        if not f.endswith(".pdf"):
            continue

        category = (
            "textbook"
            if f.startswith("textbooks/")
            else ("paper" if f.startswith("papers/") else "document")
        )
        blob_url = f"https://huggingface.co/{repo_type}s/{repo_id}/blob/{revision}/{f}"
        raw_resolve_url = f"https://huggingface.co/{repo_type}s/{repo_id}/resolve/{revision}/{f}"

        resources.append(
            {
                "filename": f,
                "category": category,
                "repo_id": repo_id,
                "repo_type": repo_type,
                "revision": revision,
                "blob_url": blob_url,
                "resolve_url": raw_resolve_url,
                "canonical_url": blob_url,
                "url": blob_url,
                "status": "resolved",
                "working": True,
                "source": "huggingface",
                "last_verified": now_iso,
                "target_blank": True,
            }
        )

    return resources
