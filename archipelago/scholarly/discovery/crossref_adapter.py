"""Crossref Discovery & DOI Authority Adapter.

Authoritative DOI metadata, funding, license, and update status resolver.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
import urllib.parse
import urllib.request

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)

logger = logging.getLogger("archipelago.scholarly.crossref")


class CrossrefAdapter:
    """Adapter for Crossref REST API."""

    def __init__(self, polite_email: str = "researcher@archipelago.local"):
        self.polite_email = polite_email
        self.base_url = "https://api.crossref.org/works"
        self.headers = {"User-Agent": f"Archipelago-Research-Platform/1.1 (mailto:{polite_email})"}

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search Crossref works for query."""
        params = urllib.parse.urlencode(
            {
                "query": query,
                "rows": min(limit, 20),
            }
        )
        url = f"{self.base_url}?{params}"
        req = urllib.request.Request(url, headers=self.headers)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_bytes = resp.read()
                raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
                payload = json.loads(raw_bytes.decode("utf-8"))

                results = []
                for item in payload.get("message", {}).get("items", []):
                    results.append(self._transform_item(item, raw_sha256))
                return results
        except Exception as e:
            logger.error("Crossref search failed for '%s': %s", query, e)
            return []

    def resolve_doi(self, doi: str) -> dict[str, Any] | None:
        """Resolve authoritative metadata for an exact DOI."""
        clean_doi = doi.replace("https://doi.org/", "").strip()
        url = f"{self.base_url}/{urllib.parse.quote(clean_doi)}"
        req = urllib.request.Request(url, headers=self.headers)

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw_bytes = resp.read()
                raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
                payload = json.loads(raw_bytes.decode("utf-8"))
                return self._transform_item(payload.get("message", {}), raw_sha256)
        except Exception as e:
            logger.warning("Crossref resolution failed for DOI '%s': %s", doi, e)
            return None

    def _transform_item(self, item: dict[str, Any], raw_sha256: str) -> dict[str, Any]:
        doi = item.get("DOI")
        title_list = item.get("title", [])
        title = title_list[0] if title_list else "Untitled"

        authors = []
        for a in item.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            full_name = f"{given} {family}".strip() or "Unknown"
            authors.append(
                PaperAuthor(
                    name=full_name,
                    orcid=a.get("ORCID"),
                    institutions=[
                        aff.get("name") for aff in a.get("affiliation", []) if aff.get("name")
                    ],
                )
            )

        issued = item.get("issued", {}).get("date-parts", [[None]])[0]
        pub_date = None
        if issued and issued[0]:
            year = issued[0]
            month = issued[1] if len(issued) > 1 and issued[1] else 1
            day = issued[2] if len(issued) > 2 and issued[2] else 1
            pub_date = f"{year:04d}-{month:02d}-{day:02d}"

        # PDF or content link
        links = item.get("link", [])
        pdf_url = None
        for link in links:
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL")
                break

        prov = ProvenancePointer(
            source_type="crossref",
            artifact_sha256=raw_sha256,
            source_record_id=doi,
            json_pointer=f"/message/items/{doi}",
            source_url=f"https://doi.org/{doi}" if doi else None,
        )

        paper = PaperRecord(
            title=title,
            abstract=item.get("abstract"),
            identifiers=PaperIdentifiers(doi=doi),
            authors=authors,
            venue=item.get("container-title", [None])[0]
            if item.get("container-title")
            else item.get("publisher"),
            publication_date=pub_date,
            publication_type=item.get("type"),
            license=item.get("license", [{}])[0].get("URL") if item.get("license") else None,
        )

        return {
            "source": "crossref",
            "paper": paper,
            "provenance": prov,
            "raw_sha256": raw_sha256,
            "citation_count": item.get("is-referenced-by-count"),
            "pdf_url": pdf_url,
        }
