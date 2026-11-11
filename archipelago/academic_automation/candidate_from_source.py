"""Persist verified public source text for the local consent-gated worker."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .candidate import ALLOWED_LICENSES
from .store import AcademicStore

MAX_CANDIDATE_CHARS = 50_000
MIN_CANDIDATE_CHARS = 40
PROVIDER_HOSTS = {
    "europe_pmc": "europepmc.org",
    "d2l_open_textbook": "d2l.ai",
}


def queue_verified_source(
    store: AcademicStore, root: Path, record_key: str, source: dict[str, Any]
) -> str | None:
    """Queue licensed body text; catalog contents never become extractable text."""
    provider = str(source.get("provider") or "")
    source_url = str(source.get("source_url") or "")
    parsed = urlparse(source_url)
    if (
        provider not in PROVIDER_HOSTS
        or parsed.scheme != "https"
        or parsed.hostname != PROVIDER_HOSTS[provider]
        or source.get("license") not in ALLOWED_LICENSES
    ):
        raise ValueError("Source host or rights not eligible for ingestion")
    text = str(source.get("text") or "")
    source_kind = (
        "open_textbook_chapter" if provider == "d2l_open_textbook" else "open_article_text"
    )
    text = text[:MAX_CANDIDATE_CHARS]
    if len(text) < MIN_CANDIDATE_CHARS:
        return None
    digest = sha256(text.encode("utf-8")).hexdigest()
    folder = root / "data" / "academic_candidates"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest}.md"
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    sidecar = path.with_suffix(".source.json")
    sidecar.write_text(
        json.dumps(
            {
                "record_key": record_key,
                "provider": provider,
                "source_id": source.get("source_id"),
                "source_url": source_url,
                "source_kind": source_kind,
                "doc_title": source.get("title"),
                "edition": source.get("edition"),
                "license": source["license"],
                "license_url": source.get("license_url"),
                "retrieved_at": source.get("retrieved_at"),
                "content_sha256": digest,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    job_id = store.enqueue(
        record_key=record_key,
        rights="open_permitted",
        content_path=str(path),
        content_sha256=digest,
    )
    store.audit(
        "source_policy",
        "public_content_queued",
        job_id,
        {"provider": provider, "source_url": source_url, "source_kind": source_kind},
    )
    return job_id
