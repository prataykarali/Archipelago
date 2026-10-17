"""arXiv Preprint Discovery Adapter.

Fetches CS and AI preprints via the official arXiv API with version history and direct PDF links.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)

logger = logging.getLogger("archipelago.scholarly.arxiv")


class ArXivAdapter:
    """Adapter for arXiv programmatic API."""

    def __init__(self) -> None:
        self.base_url = "https://export.arxiv.org/api/query"
        self.ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search arXiv preprints for query."""
        clean_q = re.sub(r"[^\w\s]", " ", query).strip()
        params = urllib.parse.urlencode(
            {
                "search_query": f"all:{clean_q}",
                "max_results": min(limit, 25),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
        )
        url = f"{self.base_url}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Archipelago-arXiv-Adapter/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_bytes = resp.read()
                raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
                root = ET.fromstring(raw_bytes)

                results = []
                for entry in root.findall("atom:entry", self.ns):
                    transformed = self._transform_entry(entry, raw_sha256)
                    if transformed:
                        results.append(transformed)
                return results
        except Exception as e:
            logger.error("arXiv search failed for '%s': %s", query, e)
            return []

    def _transform_entry(self, entry: ET.Element, raw_sha256: str) -> dict[str, Any] | None:
        id_el = entry.find("atom:id", self.ns)
        if id_el is None or not id_el.text:
            return None
        raw_id_url = id_el.text.strip()
        # Extract arxiv ID (e.g. 1706.03762v7 or cs/0101001)
        arxiv_id = raw_id_url.split("/abs/")[-1] if "/abs/" in raw_id_url else raw_id_url

        title_el = entry.find("atom:title", self.ns)
        title = " ".join((title_el.text or "").split()) if title_el is not None else "Untitled"

        summary_el = entry.find("atom:summary", self.ns)
        abstract = " ".join((summary_el.text or "").split()) if summary_el is not None else None

        pub_el = entry.find("atom:published", self.ns)
        pub_date = pub_el.text[:10] if pub_el is not None and pub_el.text else None

        authors = []
        for a_el in entry.findall("atom:author", self.ns):
            name_el = a_el.find("atom:name", self.ns)
            if name_el is not None and name_el.text:
                authors.append(PaperAuthor(name=name_el.text.strip()))

        # PDF download URL
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        for link in entry.findall("atom:link", self.ns):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", pdf_url)
                break
        parsed_pdf = urllib.parse.urlparse(pdf_url)
        if parsed_pdf.scheme == "http" and parsed_pdf.hostname in {"arxiv.org", "export.arxiv.org"}:
            pdf_url = parsed_pdf._replace(scheme="https").geturl()

        # Check for DOI if published
        doi_el = entry.find("arxiv:doi", self.ns)
        doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

        prov = ProvenancePointer(
            source_type="arxiv",
            artifact_sha256=raw_sha256,
            source_record_id=arxiv_id,
            source_url=raw_id_url,
        )

        paper = PaperRecord(
            title=title,
            abstract=abstract,
            identifiers=PaperIdentifiers(
                arxiv_id=arxiv_id,
                doi=doi,
            ),
            authors=authors,
            venue="arXiv",
            publication_date=pub_date,
            publication_type="preprint",
            is_open_access=True,
            oa_url=raw_id_url,
        )

        return {
            "source": "arxiv",
            "paper": paper,
            "provenance": prov,
            "raw_sha256": raw_sha256,
            "citation_count": None,
            "pdf_url": pdf_url,
        }
