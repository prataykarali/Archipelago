"""Live scholarly source requests with inspectable response evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import os
import re
from typing import Any
import xml.etree.ElementTree as ET

import requests

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.discovery.arxiv_adapter import ArXivAdapter
from archipelago.scholarly.discovery.crossref_adapter import CrossrefAdapter
from archipelago.scholarly.discovery.openalex_adapter import OpenAlexAdapter

SOURCE_TIMEOUT_SECONDS = 15
ARXIV_TIMEOUT_SECONDS = 30
MAX_SOURCE_RESULTS = 50
MAX_ARXIV_RESULTS = 25
PAPER_TYPES = frozenset(
    {
        "article",
        "journal-article",
        "proceedings-article",
        "posted-content",
        "preprint",
        "report",
        "dissertation",
        "peer-review",
        "review",
    }
)
S2_FIELDS = (
    "title,authors,year,venue,externalIds,abstract,citationCount,openAccessPdf,isOpenAccess,url"
)
SOURCE_URLS = {
    "openalex": "https://api.openalex.org/works",
    "crossref": "https://api.crossref.org/works",
    "arxiv": "https://export.arxiv.org/api/query",
    "semantic_scholar": "https://api.semanticscholar.org/graph/v1/paper/search",
}


@dataclass
class SourceResponse:
    """One actual upstream request, including failure or empty-result state."""

    source: str
    requested_at: str
    status: str
    records: list[dict[str, Any]] = field(default_factory=list)
    raw_body: bytes | None = None
    raw_sha256: str | None = None
    request_id: str | None = None
    http_status: int | None = None
    error: str | None = None
    rate_limited: bool = False

    def summary(self) -> dict[str, Any]:
        """Return safe report fields without raw response content."""
        return {
            "source": self.source,
            "requested_at": self.requested_at,
            "status": self.status,
            "record_count": len(self.records),
            "raw_sha256": self.raw_sha256,
            "request_id": self.request_id,
            "http_status": self.http_status,
            "error": self.error,
            "rate_limited": self.rate_limited,
        }


class LiveResearchSources:
    """Fetch from official machine-readable research APIs only."""

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.openalex = OpenAlexAdapter(
            polite_email=os.getenv("ARCHIPELAGO_CONTACT_EMAIL", "researcher@archipelago.local")
        )
        self.crossref = CrossrefAdapter(
            polite_email=os.getenv("ARCHIPELAGO_CONTACT_EMAIL", "researcher@archipelago.local")
        )
        self.arxiv = ArXivAdapter()

    def search(self, source: str, query: str, limit: int) -> SourceResponse:
        """Fetch and parse one source; never disguise an error as zero results."""
        if source not in SOURCE_URLS:
            raise ValueError(f"Unknown research source: {source}")
        requested_at = datetime.now(UTC).isoformat()
        count = min(max(limit, 1), MAX_SOURCE_RESULTS)
        params: dict[str, Any] = {
            "openalex": {"search": query, "per-page": count},
            "crossref": {"query": query, "rows": count},
            "arxiv": {
                "search_query": f"all:{re.sub(r'[^\w\s]', ' ', query)}",
                "max_results": min(count, MAX_ARXIV_RESULTS),
            },
            "semantic_scholar": {"query": query, "limit": count, "fields": S2_FIELDS},
        }[source]
        headers = {"User-Agent": "Archipelago-Research/2.0 (scholarly metadata discovery)"}
        if source == "semantic_scholar" and os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
            headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
        result = SourceResponse(source=source, requested_at=requested_at, status="unavailable")
        try:
            response = self.session.get(
                SOURCE_URLS[source],
                params=params,
                headers=headers,
                timeout=ARXIV_TIMEOUT_SECONDS if source == "arxiv" else SOURCE_TIMEOUT_SECONDS,
            )
            result.http_status = response.status_code
            result.request_id = response.headers.get("x-request-id") or response.headers.get(
                "x-amzn-requestid"
            )
            result.rate_limited = response.status_code == 429
            result.raw_body = response.content
            result.raw_sha256 = hashlib.sha256(response.content).hexdigest()
            if not response.ok:
                result.status = "rate_limited" if result.rate_limited else "http_error"
                result.error = f"HTTP {response.status_code}"
                return result
            result.records = self._parse(source, response.content, result.raw_sha256)
            result.status = "live" if result.records else "live_empty"
        except requests.RequestException as exc:
            result.status = "request_failed"
            result.error = type(exc).__name__
        except (ValueError, KeyError, ET.ParseError) as exc:
            result.status = "parse_failed"
            result.error = type(exc).__name__
        return result

    def _parse(self, source: str, body: bytes, digest: str) -> list[dict[str, Any]]:
        if source == "arxiv":
            root = ET.fromstring(body)
            entries = root.findall("atom:entry", self.arxiv.ns)
            return [
                item for entry in entries if (item := self.arxiv._transform_entry(entry, digest))
            ]
        data = json.loads(body)
        if source == "openalex":
            return [
                self.openalex._transform_item(item, digest)
                for item in data["results"]
                if item.get("type") in PAPER_TYPES
            ]
        if source == "crossref":
            return [
                self.crossref._transform_item(item, digest)
                for item in data["message"]["items"]
                if item.get("type") in PAPER_TYPES
            ]
        return [
            self._semantic_scholar_item(item, digest)
            for item in data["data"]
            if item.get("title") and "Book" not in (item.get("publicationTypes") or [])
        ]

    @staticmethod
    def _semantic_scholar_item(item: dict[str, Any], digest: str) -> dict[str, Any]:
        identifiers = item.get("externalIds") or {}
        paper_id = item["paperId"]
        pdf = item.get("openAccessPdf") or {}
        paper = PaperRecord(
            title=item["title"],
            abstract=item.get("abstract"),
            authors=[
                PaperAuthor(name=a["name"]) for a in item.get("authors") or [] if a.get("name")
            ],
            venue=item.get("venue"),
            publication_date=f"{item['year']}-01-01" if item.get("year") else None,
            identifiers=PaperIdentifiers(
                doi=identifiers.get("DOI"),
                arxiv_id=identifiers.get("ArXiv"),
                semantic_scholar_id=paper_id,
            ),
            is_open_access=item.get("isOpenAccess"),
            oa_url=pdf.get("url"),
        )
        return {
            "source": "semantic_scholar",
            "paper": paper,
            "provenance": ProvenancePointer(
                source_type="semantic_scholar",
                artifact_sha256=digest,
                source_record_id=paper_id,
                source_url=item.get("url"),
            ),
            "raw_sha256": digest,
            "citation_count": item.get("citationCount"),
            "pdf_url": pdf.get("url"),
        }
