"""Require explicit open-content rights evidence before academic ingestion."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlparse

from .store import AcademicStore

ALLOWED_LICENSES = frozenset({"CC0-1.0", "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-4.0", "public-domain"})


def enqueue_manifest(store: AcademicStore, root: Path, manifest_path: Path) -> str:
    """Queue a local file only when its rights declaration and hash match."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Rights manifest must be an object")
    license_id = str(manifest.get("license") or "")
    source_url = str(manifest.get("source_url") or "")
    reviewer = str(manifest.get("rights_reviewed_by") or "").strip()
    if license_id not in ALLOWED_LICENSES or not reviewer:
        raise ValueError("Open-content license and named rights reviewer required")
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Verified HTTPS source URL required")
    content = (
        root / "data" / "academic_candidates" / str(manifest.get("filename") or "")
    ).resolve()
    candidate_root = (root / "data" / "academic_candidates").resolve()
    if not content.is_relative_to(candidate_root) or not content.is_file():
        raise ValueError("Candidate must be an existing approved local file")
    digest = sha256(content.read_bytes()).hexdigest()
    if digest != manifest.get("sha256"):
        raise ValueError("Candidate content hash does not match rights manifest")
    record_key = str(manifest.get("record_key") or "")
    job_id = store.enqueue(
        record_key=record_key,
        rights="open_permitted",
        content_path=str(content),
        content_sha256=digest,
        priority=int(manifest.get("priority") or 0),
    )
    store.audit(
        reviewer,
        "content_rights_verified",
        job_id,
        {"license": license_id, "source_url": source_url, "sha256": digest},
    )
    return job_id
