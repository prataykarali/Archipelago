"""Normalize external source matches into the durable evidence ledger."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .open_books import opac_url
from .store import AcademicStore
from .store_views import save_evidence

RESTRICTED_REASON = "Author preprint is CC-BY-NC-ND-4.0; derivative extraction not permitted"


def record_source_evidence(
    store: AcademicStore, record_key: str, record: dict[str, Any], source: dict[str, Any]
) -> dict[str, Any]:
    """Persist one source match with a conservative extraction decision."""
    provider = str(source["provider"])
    status = str(source.get("status") or "metadata_only")
    restricted = status == "restricted_license"
    full_text = status == "open_permitted"
    toc = source.get("table_of_contents") or []
    license_id = str(source.get("license") or "")
    evidence = {
        "record_key": record_key,
        "provider": provider,
        "source_id": str(source["source_id"]),
        "opac_source_url": opac_url(record_key),
        "source_url": str(source["source_url"]),
        "matched_title": str(source.get("title") or ""),
        "matched_authors": str(source.get("authors") or source.get("author") or ""),
        "isbn": str(source.get("isbn") or record.get("isbn") or ""),
        "edition": str(record.get("edition") or ""),
        "match_verification": "title_exact_doi_verified"
        if source.get("doi")
        else "isbn_exact_title_verified",
        "license_id": license_id,
        "license_uri": str(source.get("license_url") or ""),
        "content_status": "restricted_license"
        if restricted
        else "open_full_text"
        if full_text
        else "table_of_contents_only"
        if toc
        else "metadata_only",
        "has_toc": int(bool(toc)),
        "has_preview": 0,
        "chapter_count": len(toc) if isinstance(toc, list) else 0,
        "has_full_text": int(full_text),
        "eligible_extraction": int(full_text and not restricted),
        "reason": RESTRICTED_REASON
        if restricted
        else "Verified licensed body text"
        if full_text
        else "Bibliographic metadata only; no chapter body text",
        "retrieved_at": str(source.get("retrieved_at") or datetime.now(UTC).isoformat()),
    }
    save_evidence(store, evidence)
    store.save_match(
        record_key,
        provider,
        str(evidence["source_id"]),
        str(evidence["source_url"]),
        str(evidence["content_status"]),
    )
    return evidence
