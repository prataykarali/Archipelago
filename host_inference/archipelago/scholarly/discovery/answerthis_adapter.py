"""AnswerThis Scholarly Discovery & Independent Validation Adapter.

Supports server-configured AnswerThis API access when authorized, or imported
AnswerThis JSON/CSV validation exports. Never fabricates AnswerThis responses.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import hashlib
import io
import json
import os
from typing import Any

import requests

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.discovery.canonicalizer import normalize_title
from archipelago.scholarly.discovery.resilient_http import reliability_client

ANSWERTHIS_API_VERIFIED = "ANSWERTHIS_API_VERIFIED"
ANSWERTHIS_IMPORTED_VALIDATION = "ANSWERTHIS_IMPORTED_VALIDATION"
ANSWERTHIS_NOT_CONFIGURED = "ANSWERTHIS_NOT_CONFIGURED"
ANSWERTHIS_UNAVAILABLE = "ANSWERTHIS_UNAVAILABLE"


class AnswerThisProvider:
    """Isolated AnswerThis adapter using server-side credentials only."""

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.api_url = os.getenv("ANSWERTHIS_API_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("ANSWERTHIS_API_KEY", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_key)

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "source": "answerthis",
            "status": ANSWERTHIS_API_VERIFIED if self.configured else ANSWERTHIS_NOT_CONFIGURED,
            "configured": self.configured,
            "record_count": 0,
            "rate_limited": False,
        }

    def search(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            return {
                "source": "answerthis",
                "status": ANSWERTHIS_NOT_CONFIGURED,
                "http_status": None,
                "error": "answerthis_credentials_not_configured",
                "rate_limited": False,
                "records": [],
            }
        params: dict[str, Any] = {"q": query, "limit": min(max(1, limit), 50)}
        if year_from:
            params["year_from"] = year_from
        if year_to:
            params["year_to"] = year_to
        resp, err = reliability_client().get(
            self.session,
            "answerthis",
            f"{self.api_url}/papers/search",
            params=params,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "Archipelago-Research/2.0",
            },
            timeout=15,
            ttl_seconds=900.0 if isinstance(self.session, requests.Session) else 0.0,
        )
        if resp is None or not resp.ok:
            is_rl = bool((resp is not None and resp.status_code == 429) or (err and "429" in err))
            return {
                "source": "answerthis",
                "status": "rate_limited" if is_rl else ANSWERTHIS_UNAVAILABLE,
                "http_status": resp.status_code if resp is not None else None,
                "error": err or (f"HTTP {resp.status_code}" if resp is not None else "unavailable"),
                "rate_limited": is_rl,
                "records": [],
            }
        sha = hashlib.sha256(resp.content).hexdigest()
        payload = resp.json()
        items = payload.get("results") or payload.get("papers") or []
        records = [_normalize_answerthis_item(item, sha, ANSWERTHIS_API_VERIFIED) for item in items if item.get("title")]
        return {
            "source": "answerthis",
            "status": ANSWERTHIS_API_VERIFIED,
            "http_status": resp.status_code,
            "raw_sha256": sha,
            "rate_limited": False,
            "records": records,
        }


def _normalize_answerthis_item(
    item: dict[str, Any],
    digest: str,
    verification_status: str,
) -> dict[str, Any]:
    title = str(item.get("title") or "").strip()
    doi = str(item.get("doi") or "").strip() or None
    arxiv_id = str(item.get("arxiv_id") or "").strip() or None
    raw_authors = item.get("authors") or []
    if isinstance(raw_authors, str):
        authors = [PaperAuthor(name=a.strip()) for a in raw_authors.split(";") if a.strip()]
    else:
        authors = [
            PaperAuthor(name=str(a.get("name") if isinstance(a, dict) else a).strip())
            for a in raw_authors
            if (a.get("name") if isinstance(a, dict) else a)
        ]
    year = item.get("year") or item.get("publication_year")
    pub_date = f"{int(year)}-01-01" if str(year or "").isdigit() else None
    url = item.get("url") or (f"https://doi.org/{doi}" if doi else None)
    paper = PaperRecord(
        title=title,
        abstract=str(item.get("abstract") or "").strip() or None,
        identifiers=PaperIdentifiers(doi=doi, arxiv_id=arxiv_id),
        authors=authors,
        venue=str(item.get("venue") or "").strip() or None,
        publication_date=pub_date,
        publication_type=str(item.get("publication_type") or "").strip() or None,
    )
    return {
        "source": "answerthis",
        "verification_status": verification_status,
        "paper": paper,
        "provenance": ProvenancePointer(
            source_type="answerthis",
            artifact_sha256=digest,
            source_record_id=doi or arxiv_id or title[:64],
            source_url=url,
            fetched_at=datetime.now(UTC).isoformat(),
        ),
        "citation_count": item.get("citation_count") if isinstance(item.get("citation_count"), int) else None,
        "source_metadata": {"answerthis_status": verification_status},
    }


def import_answerthis_export(raw_content: str, fmt: str = "auto") -> dict[str, Any]:
    """Parse an externally exported AnswerThis JSON or CSV validation dataset."""
    text = (raw_content or "").strip()
    if not text:
        return {"status": ANSWERTHIS_UNAVAILABLE, "records": [], "error": "empty_export"}
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    detected = fmt if fmt in {"json", "csv"} else ("json" if text.startswith(("{", "[")) else "csv")
    items: list[dict[str, Any]] = []
    if detected == "json":
        parsed = json.loads(text)
        raw_list = parsed if isinstance(parsed, list) else (parsed.get("results") or parsed.get("papers") or [])
        items = [x for x in raw_list if isinstance(x, dict)]
    else:
        reader = csv.DictReader(io.StringIO(text))
        items = [dict(row) for row in reader]
    records = [_normalize_answerthis_item(it, digest, ANSWERTHIS_IMPORTED_VALIDATION) for it in items if it.get("title")]
    return {
        "status": ANSWERTHIS_IMPORTED_VALIDATION,
        "record_count": len(records),
        "raw_sha256": digest,
        "records": records,
    }


def compare_against_answerthis(
    archipelago_papers: list[dict[str, Any]],
    answerthis_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare Archipelago results against AnswerThis records by DOI and normalized title."""
    arch_dois = {str(p.get("doi")).strip().casefold() for p in archipelago_papers if p.get("doi")}
    arch_titles = {normalize_title(p.get("title") or "") for p in archipelago_papers if p.get("title")}
    matched = 0
    unmatched: list[str] = []
    for rec in answerthis_records:
        paper: PaperRecord = rec["paper"]
        doi = (paper.identifiers.doi or "").strip().casefold()
        ntitle = normalize_title(paper.title)
        if (doi and doi in arch_dois) or (ntitle and ntitle in arch_titles):
            matched += 1
        else:
            unmatched.append(paper.title)
    return {
        "answerthis_count": len(answerthis_records),
        "archipelago_count": len(archipelago_papers),
        "matched_count": matched,
        "overlap_rate": round(matched / len(answerthis_records), 4) if answerthis_records else None,
        "answerthis_only_titles": unmatched[:20],
    }
