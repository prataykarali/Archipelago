"""OpenAlex Discovery Adapter.

Primary discovery backbone connecting to OpenAlex works, topics, institutions, and open-access PDF links.
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

logger = logging.getLogger("archipelago.scholarly.openalex")


class OpenAlexAdapter:
    """Adapter for OpenAlex academic graph."""

    def __init__(self, polite_email: str = "researcher@archipelago.local"):
        self.polite_email = polite_email
        self.base_url = "https://api.openalex.org/works"
        self.headers = {"User-Agent": f"Archipelago-Research-Platform/1.1 (mailto:{polite_email})"}

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search OpenAlex works for a given research query."""
        params = urllib.parse.urlencode(
            {
                "search": query,
                "per-page": min(limit, 50),
                "sort": "relevance_score:desc",
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
                for item in payload.get("results", []):
                    canonical_item = self._transform_item(item, raw_sha256)
                    results.append(canonical_item)
                return results
        except Exception as e:
            logger.error("OpenAlex search failed for query '%s': %s", query, e)
            return []

    def _transform_item(self, item: dict[str, Any], raw_sha256: str) -> dict[str, Any]:
        """Convert OpenAlex work object to unified candidate dict."""
        openalex_id = item.get("id")
        doi = item.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/") :]

        # Extract authors and affiliations
        authors = []
        for auth_entry in item.get("authorships", []):
            author_obj = auth_entry.get("author", {})
            name = author_obj.get("display_name", "Unknown")
            institutions = [
                inst.get("display_name")
                for inst in auth_entry.get("institutions", [])
                if inst.get("display_name")
            ]
            authors.append(
                PaperAuthor(
                    name=name,
                    orcid=author_obj.get("orcid"),
                    institutions=institutions,
                )
            )

        # Open access & PDF URL
        oa_info = item.get("open_access") or {}
        is_oa = oa_info.get("is_oa", False)
        oa_url = oa_info.get("oa_url")
        pdf_url = oa_url if (oa_url and oa_url.endswith(".pdf")) else None
        prim_loc = item.get("primary_location") or {}
        if not pdf_url:
            pdf_url = prim_loc.get("pdf_url")

        # Provenance pointer for discovery
        prov = ProvenancePointer(
            source_type="openalex",
            artifact_sha256=raw_sha256,
            source_record_id=openalex_id,
            json_pointer=f"/results/{openalex_id}",
            source_url=openalex_id,
        )

        source_obj = prim_loc.get("source") or {}
        paper = PaperRecord(
            title=item.get("title") or "Untitled Paper",
            abstract=self._reconstruct_abstract(item.get("abstract_inverted_index")),
            identifiers=PaperIdentifiers(
                doi=doi,
                openalex_id=openalex_id,
            ),
            authors=authors,
            venue=source_obj.get("display_name"),
            publication_date=item.get("publication_date"),
            publication_type=item.get("type"),
            language=item.get("language") or "en",
            is_open_access=is_oa,
            oa_url=oa_url,
            license=prim_loc.get("license"),
        )

        return {
            "source": "openalex",
            "paper": paper,
            "provenance": prov,
            "raw_sha256": raw_sha256,
            "citation_count": item.get("cited_by_count"),
            "concepts": [c.get("display_name") for c in item.get("concepts", [])[:5]],
            "pdf_url": pdf_url or oa_url,
        }

    def _reconstruct_abstract(self, inverted_index: dict[str, list[int]] | None) -> str | None:
        """Reconstruct abstract string from OpenAlex inverted index."""
        if not inverted_index:
            return None
        token_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                token_positions.append((pos, word))
        token_positions.sort(key=lambda x: x[0])
        return " ".join([word for _, word in token_positions])
