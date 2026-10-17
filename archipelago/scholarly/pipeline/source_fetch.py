"""Fetch scholarly candidates from the four configured sources."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.discovery.anything_api_bridge import AnythingApiBridge
from archipelago.scholarly.discovery.arxiv_adapter import ArXivAdapter
from archipelago.scholarly.discovery.iemcrp_adapter import IEMCRPAdapter
from archipelago.scholarly.discovery.opac_adapter import OPACAdapter
from archipelago.scholarly.discovery.openalex_adapter import OpenAlexAdapter
from archipelago.scholarly.discovery.scholar_adapter import GoogleScholarAdapter

logger = logging.getLogger("archipelago.scholarly.harvester")


class SourceFetchMixin:
    """Implement source retrieval for a configured harvester."""

    use_api_anything: bool
    bridge: AnythingApiBridge
    arxiv_adapter: ArXivAdapter
    opac_adapter: OPACAdapter
    iemcrp_adapter: IEMCRPAdapter
    scholar_adapter: GoogleScholarAdapter
    openalex_adapter: OpenAlexAdapter

    def fetch_arxiv(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch preprints from arXiv via api-anything with adapter fallback."""
        results: list[dict[str, Any]] = []

        if self.use_api_anything and self.bridge.is_available():
            try:
                res = self.bridge.call("arxiv", "search", q=query)
                if res and res.get("ok") and isinstance(res.get("data"), list):
                    items = res["data"]
                    for it in items[:limit]:
                        title = it.get("title", "").strip().replace("\n", " ")
                        if not title:
                            continue
                        url = it.get("url", "")
                        summary = it.get("summary", "")
                        pub = it.get("published", "")
                        raw_sha256 = hashlib.sha256(f"arxiv_{title}_{url}".encode()).hexdigest()

                        prov = ProvenancePointer(
                            source_type="arxiv",
                            artifact_sha256=raw_sha256,
                            source_record_id=url.split("/")[-1] if "/" in url else "arxiv_id",
                            source_url=url,
                        )
                        paper = PaperRecord(
                            title=title,
                            abstract=summary,
                            identifiers=PaperIdentifiers(
                                arxiv_id=url.split("/")[-1] if "/" in url else None
                            ),
                            authors=[PaperAuthor(name="arXiv Researcher")],
                            venue="arXiv.org",
                            publication_date=pub[:10] if pub else None,
                            publication_type="preprint",
                            is_open_access=True,
                            oa_url=url,
                        )
                        results.append(
                            {
                                "source": "arxiv",
                                "paper": paper,
                                "provenance": prov,
                                "raw_sha256": raw_sha256,
                                "citation_count": 0,
                                "pdf_url": url.replace("/abs/", "/pdf/") + ".pdf"
                                if "/abs/" in url
                                else None,
                                "method": "api-anything",
                                "retrieval_mode": "live",
                            }
                        )
            except Exception as e:
                logger.warning("api-anything arXiv query failed: %s", e)

        if not results:
            logger.info("Using native ArXivAdapter for '%s'", query)
            native_res = self.arxiv_adapter.search(query, limit=limit)
            for r in native_res:
                r["method"] = "native-adapter"
                r["retrieval_mode"] = "live"
                results.append(r)

        return results

    # -------------------------------------------------------------------------
    # Target 2: UEMK Koha OPAC
    # -------------------------------------------------------------------------
    def fetch_opac(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch library books from UEMK OPAC via api-anything with adapter fallback."""
        results: list[dict[str, Any]] = []

        if self.use_api_anything and self.bridge.is_available():
            try:
                res = self.bridge.call("uemk-opac", "search", q=query)
                if res and res.get("ok") and isinstance(res.get("data"), list):
                    for it in res["data"][:limit]:
                        title = it.get("title", "").strip()
                        author = it.get("author", "UEM Library Cataloged Author").strip()
                        if not title:
                            continue
                        record_url = it.get("url") or it.get("link")
                        if not record_url:
                            continue
                        raw_sha256 = hashlib.sha256(
                            f"opac_{title}_{author}_{record_url}".encode()
                        ).hexdigest()
                        prov = ProvenancePointer(
                            source_type="opac",
                            artifact_sha256=raw_sha256,
                            source_record_id=f"opac_{raw_sha256[:8]}",
                            source_url=record_url,
                        )
                        paper = PaperRecord(
                            title=title,
                            abstract=f"UEMK Central Library catalog record for '{title}'.",
                            identifiers=PaperIdentifiers(),
                            authors=[PaperAuthor(name=author)],
                            venue="UEMK Central Library",
                            publication_type="book",
                            is_open_access=False,
                            oa_url=record_url,
                        )
                        results.append(
                            {
                                "source": "uemk_opac",
                                "paper": paper,
                                "provenance": prov,
                                "raw_sha256": raw_sha256,
                                "citation_count": 0,
                                "availability": "unknown",
                                "method": "api-anything",
                                "retrieval_mode": "live",
                            }
                        )
            except Exception as e:
                logger.warning("api-anything OPAC call failed: %s", e)

        if not results:
            logger.info("Using native OPACAdapter for '%s'", query)
            native_res = self.opac_adapter.search(query, limit=limit)
            for r in native_res:
                r["method"] = (
                    "native-adapter" if r.get("retrieval_mode") == "live" else "pearson-bookshelf"
                )
                results.append(r)

        return results

    # -------------------------------------------------------------------------
    # Target 3: IEM CRP
    # -------------------------------------------------------------------------
    def fetch_iemcrp(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch digital library resources from IEM CRP via api-anything with adapter fallback."""
        results: list[dict[str, Any]] = []

        if self.use_api_anything and self.bridge.is_available():
            try:
                res = self.bridge.call("iemcrp", "library")
                if res and res.get("ok") and isinstance(res.get("data"), list):
                    for it in res["data"][:limit]:
                        title = it.get("title", "").strip()
                        url = it.get("url", "")
                        if not title or not url:
                            continue
                        raw_sha256 = hashlib.sha256(f"iemcrp_{title}_{url}".encode()).hexdigest()
                        prov = ProvenancePointer(
                            source_type="iemcrp",
                            artifact_sha256=raw_sha256,
                            source_record_id=f"iemcrp_{raw_sha256[:8]}",
                            source_url=url,
                        )
                        paper = PaperRecord(
                            title=title,
                            abstract=f"Official IEM-UEM Group Digital Library resource: {title}",
                            identifiers=PaperIdentifiers(),
                            authors=[PaperAuthor(name="IEM-UEM Academic Board")],
                            venue="IEM CRP Digital Library",
                            publication_type="resource",
                            oa_url=url,
                        )
                        results.append(
                            {
                                "source": "iemcrp",
                                "paper": paper,
                                "provenance": prov,
                                "raw_sha256": raw_sha256,
                                "citation_count": 0,
                                "category": "Digital Library",
                                "access_url": url,
                                "method": "api-anything",
                                "retrieval_mode": "live",
                            }
                        )
            except Exception as e:
                logger.warning("api-anything IEM CRP call failed: %s", e)

        if not results:
            logger.info("Using native IEMCRPAdapter for '%s'", query)
            native_res = self.iemcrp_adapter.search_resources(query, limit=limit)
            for r in native_res:
                r["method"] = (
                    "native-adapter" if r.get("retrieval_mode") == "live" else "local-link-manifest"
                )
                results.append(r)

        return results

    # -------------------------------------------------------------------------
    # Target 4: Google Scholar
    # -------------------------------------------------------------------------
    def fetch_scholar(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Keep Scholar as a human verification link, never a machine record."""
        return self.scholar_adapter.search(query, limit=limit)

    def fetch_openalex(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch live scholarly metadata from an open machine-readable index."""
        results: list[dict[str, Any]] = self.openalex_adapter.search(query, limit=limit)
        for result in results:
            result["method"] = "openalex-api"
            result["retrieval_mode"] = "live"
        return results

    # -------------------------------------------------------------------------
    # Core Parallel Execution Pipeline
    # -------------------------------------------------------------------------
