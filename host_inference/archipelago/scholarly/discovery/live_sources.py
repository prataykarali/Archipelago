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

SOURCE_TIMEOUT_SECONDS = 8
ARXIV_TIMEOUT_SECONDS = 12
MAX_SOURCE_RESULTS = 500
MAX_PAGE_SIZE = 100
MAX_ARXIV_PAGE_SIZE = 50
MAX_PAGES_PER_PROVIDER = 12
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
    "title,authors.name,authors.authorId,year,venue,externalIds,abstract,citationCount,"
    "referenceCount,influentialCitationCount,publicationDate,publicationTypes,fieldsOfStudy,"
    "openAccessPdf,isOpenAccess,url"
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
    pages_fetched: int = 0

    def summary(self) -> dict[str, Any]:
        """Return safe report fields without raw response content."""
        return {
            "source": self.source,
            "requested_at": self.requested_at,
            "status": self.status,
            "record_count": len(self.records),
            "pages_fetched": self.pages_fetched,
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

    def _build_page_params(
        self, source: str, query: str, page_size: int, page_idx: int
    ) -> dict[str, Any]:
        offset = page_idx * page_size
        if source == "openalex":
            params = {"search": query, "per-page": page_size, "page": page_idx + 1}
            if api_key := os.getenv("OPENALEX_API_KEY", "").strip():
                params["api_key"] = api_key
            return params
        if source == "crossref":
            return {"query": query, "rows": page_size, "offset": offset}
        if source == "arxiv":
            return {
                "search_query": f"all:{re.sub(r'[^\w\s]', ' ', query)}",
                "start": offset,
                "max_results": page_size,
            }
        return {"query": query, "limit": page_size, "offset": offset, "fields": S2_FIELDS}

    def search(self, source: str, query: str, limit: int) -> SourceResponse:
        """Fetch and parse one source with pagination; never disguise an error as zero results."""
        requested_at = datetime.now(UTC).isoformat()
        count = min(max(limit, 1), MAX_SOURCE_RESULTS)
        if source in {"dblp", "openaire", "datacite", "europe_pmc", "pubmed"}:
            return self._search_extended(source, query, count, requested_at)
        if source not in SOURCE_URLS:
            raise ValueError(f"Unknown research source: {source}")
        headers = {
            "User-Agent": (
                f"Archipelago-Research/2.0 (mailto:{os.getenv('ARCHIPELAGO_CONTACT_EMAIL', 'researcher@archipelago.local')})"
            )
        }
        if source == "semantic_scholar" and os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
            headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
        result = SourceResponse(source=source, requested_at=requested_at, status="unavailable")
        page_cap = MAX_ARXIV_PAGE_SIZE if source == "arxiv" else MAX_PAGE_SIZE
        from archipelago.scholarly.discovery.resilient_http import reliability_client

        ttl = 900.0 if isinstance(self.session, requests.Session) else 0.0
        try:
            for page_idx in range(MAX_PAGES_PER_PROVIDER):
                remaining = count - len(result.records)
                if remaining <= 0:
                    break
                # Keep the upstream page size fixed. A shrinking size changes
                # offset arithmetic after filtered records and repeats pages.
                page_size = min(count, page_cap)
                params = self._build_page_params(source, query, page_size, page_idx)
                response, err = reliability_client().get(
                    self.session,
                    source,
                    SOURCE_URLS[source],
                    params=params,
                    headers=headers,
                    timeout=ARXIV_TIMEOUT_SECONDS if source == "arxiv" else SOURCE_TIMEOUT_SECONDS,
                    ttl_seconds=ttl,
                )
                if response is None:
                    if page_idx == 0:
                        is_rl = bool(err and "429" in err)
                        result.rate_limited = is_rl
                        result.status = "rate_limited" if is_rl else "request_failed"
                        result.error = err or "request_failed"
                        return result
                    result.error = err or "request_failed"
                    break
                result.http_status = response.status_code
                result.request_id = response.headers.get("x-request-id") or response.headers.get(
                    "x-amzn-requestid"
                )
                result.rate_limited = response.status_code == 429
                result.raw_body = response.content
                result.raw_sha256 = hashlib.sha256(response.content).hexdigest()
                if not response.ok:
                    if page_idx == 0:
                        result.status = "rate_limited" if result.rate_limited else "http_error"
                        result.error = f"HTTP {response.status_code}"
                        return result
                    result.error = f"HTTP {response.status_code}"
                    break
                ctype = (response.headers.get("content-type") or "").lower()
                if source == "arxiv":
                    if ctype and "html" in ctype:
                        raise ValueError("unexpected_html_content_type")
                elif ctype and "json" not in ctype and "javascript" not in ctype:
                    raise ValueError(f"unexpected_content_type:{ctype.split(';', 1)[0].strip()}")
                page_records, raw_items_count = self._parse_page(
                    source, response.content, result.raw_sha256
                )
                result.pages_fetched += 1
                result.records.extend(page_records)
                if raw_items_count < page_size:
                    break
            result.records = result.records[:count]
            result.status = (
                ("live_partial" if result.error else "live") if result.records else "live_empty"
            )
        except requests.RequestException as exc:
            if not result.records:
                result.status = "request_failed"
                result.error = type(exc).__name__
            else:
                result.status = "live_partial"
                result.error = type(exc).__name__
        except (ValueError, KeyError, ET.ParseError) as exc:
            if not result.records:
                result.status = "parse_failed"
                result.error = type(exc).__name__
            else:
                result.status = "live_partial"
                result.error = type(exc).__name__
        return result

    def _search_extended(
        self, source: str, query: str, count: int, requested_at: str
    ) -> SourceResponse:
        from archipelago.scholarly.discovery.biomed_sources import search_europe_pmc, search_pubmed
        from archipelago.scholarly.discovery.extended_sources import (
            search_datacite,
            search_dblp,
            search_openaire,
        )

        fn = {
            "dblp": search_dblp,
            "openaire": search_openaire,
            "datacite": search_datacite,
            "europe_pmc": search_europe_pmc,
            "pubmed": search_pubmed,
        }[source]
        result = SourceResponse(source=source, requested_at=requested_at, status="unavailable")
        try:
            payload = fn(self.session, query, count)
            result.status = str(payload.get("status") or "unavailable")
            result.http_status = payload.get("http_status")
            result.error = payload.get("error")
            result.rate_limited = bool(payload.get("rate_limited"))
            result.raw_sha256 = payload.get("raw_sha256")
            result.raw_body = payload.get("raw_body")
            result.pages_fetched = int(
                payload.get("pages_fetched") or (1 if payload.get("http_status") == 200 else 0)
            )
            result.records = list(payload.get("records") or [])
        except requests.RequestException as exc:
            result.status = "request_failed"
            result.error = type(exc).__name__
        except (ValueError, KeyError) as exc:
            result.status = "parse_failed"
            result.error = type(exc).__name__
        return result

    def _parse(self, source: str, body: bytes, digest: str) -> list[dict[str, Any]]:
        records, _ = self._parse_page(source, body, digest)
        return records

    def _parse_page(
        self, source: str, body: bytes, digest: str
    ) -> tuple[list[dict[str, Any]], int]:
        if source == "arxiv":
            root = ET.fromstring(body)
            entries = root.findall("atom:entry", self.arxiv.ns)
            parsed = [
                item for entry in entries if (item := self.arxiv._transform_entry(entry, digest))
            ]
            return parsed, len(entries)
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("expected_json_object")
        if data.get("error") or data.get("status") == "error":
            raise ValueError(
                f"provider_error_payload:{data.get('error') or data.get('message') or 'error'}"
            )
        if source == "openalex":
            raw_items = data.get("results")
            if not isinstance(raw_items, list):
                raise KeyError("results")
            parsed = []
            for item in raw_items:
                if isinstance(item, dict) and item.get("type") in PAPER_TYPES and item.get("title"):
                    parsed.append(self.openalex._transform_item(item, digest))
            return parsed, len(raw_items)
        if source == "crossref":
            msg = data.get("message")
            if not isinstance(msg, dict) or not isinstance(msg.get("items"), list):
                raise KeyError("items")
            raw_items = msg["items"]
            parsed = []
            for item in raw_items:
                if isinstance(item, dict) and item.get("type") in PAPER_TYPES and item.get("title"):
                    parsed.append(self.crossref._transform_item(item, digest))
            return parsed, len(raw_items)
        raw_items = data.get("data")
        if not isinstance(raw_items, list):
            raise KeyError("data")
        parsed = [
            self._semantic_scholar_item(item, digest)
            for item in raw_items
            if isinstance(item, dict)
            and item.get("title")
            and item.get("paperId")
            and "Book" not in (item.get("publicationTypes") or [])
        ]
        return parsed, len(raw_items)

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
                pubmed_id=identifiers.get("PubMed"),
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
            "source_metadata": {
                "reference_count": item.get("referenceCount"),
                "influential_citations": item.get("influentialCitationCount"),
                "research_domain": item.get("fieldsOfStudy"),
                "publication_types": item.get("publicationTypes"),
                "author_s2_ids": [a.get("authorId") for a in item.get("authors") or []],
            },
        }
