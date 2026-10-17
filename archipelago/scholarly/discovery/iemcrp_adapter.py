"""IEM CRP Digital Library & Resource Discovery Adapter.

Extracts library catalog links, departmental publications ('Make in IEM UEM'),
digital library databases, and student academic course resources from IEM CRP.
Supports session cookies (JSESSIONID) and interactive authentication loops.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any
import urllib.parse
import urllib.request

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)

logger = logging.getLogger("archipelago.scholarly.iemcrp")

IEMCRP_BASE = "https://www.iemcrp.com"
LIBRARY_PORTAL_URL = f"{IEMCRP_BASE}/iemEn/aerp_libreay_chy20200726.jsp"


class IEMCRPAdapter:
    """Adapter for IEM CRP University ERP Digital Library."""

    def __init__(self, session_cookie: str | None = None):
        self.session_cookie = session_cookie or os.environ.get("IEMCRP_SESSION_COOKIE")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if self.session_cookie:
            self.headers["Cookie"] = f"JSESSIONID={self.session_cookie}"

    def fetch_library_portal_info(self) -> dict[str, Any]:
        """Fetch and extract structured resources from the IEM CRP Library Portal page."""
        portal_url = os.environ.get("ARCHIPELAGO_IEMCRP_LIBRARY_URL", LIBRARY_PORTAL_URL)
        req = urllib.request.Request(portal_url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                content = resp.read()
                raw_sha256 = hashlib.sha256(content).hexdigest()
                html_text = content.decode("utf-8", errors="ignore")
                if "cf-turnstile" in html_text.lower() or "challenge-platform" in html_text.lower():
                    return self._fallback_portal_manifest()
                parsed = self._parse_portal_html(html_text, raw_sha256)
                return parsed if parsed["resources"] else self._fallback_portal_manifest()
        except Exception as e:
            logger.warning(
                "Direct fetch of IEM CRP portal returned (%s). Using local portal link manifest.",
                e,
            )
            return self._fallback_portal_manifest()

    def search_resources(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search academic resources and departmental publications matching query."""
        portal_data = self.fetch_library_portal_info()
        items = []

        query_lower = query.lower()
        for resource in portal_data.get("resources", []):
            if any(
                token in resource["title"].lower() or token in resource["category"].lower()
                for token in query_lower.split()
            ):
                items.append(resource)

        if not items:
            items = portal_data.get("resources", [])[:limit]

        results = []
        for it in items[:limit]:
            prov = ProvenancePointer(
                source_type="iemcrp"
                if portal_data["retrieval_mode"] == "live"
                else "iemcrp_manifest",
                artifact_sha256=portal_data.get("raw_sha256", "iemcrp_sha256"),
                source_record_id=it.get("id", "res_iemcrp"),
                source_url=it.get("url"),
            )
            paper = PaperRecord(
                title=it["title"],
                abstract=it.get(
                    "description", f"IEM-UEM Group academic library resource: {it['title']}"
                ),
                identifiers=PaperIdentifiers(),
                authors=[PaperAuthor(name=it.get("author", "IEM-UEM Academic Board"))],
                venue=f"IEM CRP — {it.get('category', 'Digital Library')}",
                publication_type="resource",
                oa_url=it.get("url"),
            )
            results.append(
                {
                    "source": "iemcrp"
                    if portal_data["retrieval_mode"] == "live"
                    else "iemcrp_manifest",
                    "paper": paper,
                    "provenance": prov,
                    "raw_sha256": portal_data.get("raw_sha256", "iemcrp_sha256"),
                    "citation_count": 0,
                    "category": it.get("category"),
                    "access_url": it.get("url"),
                    "retrieval_mode": portal_data["retrieval_mode"],
                }
            )

        return results

    def _parse_portal_html(self, html: str, raw_sha256: str) -> dict[str, Any]:
        """Extract sections shown in the screenshot: Digital Library, Catalogues, Memberships, etc."""
        resources = []

        # 1. Search Catalogues (Koha OPAC, IEM Saltlake, Gurukul, Ashram)
        catalogue_links = re.findall(
            r'<a\s+[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html, re.IGNORECASE
        )
        for href, text in catalogue_links:
            clean_text = text.strip()
            if any(
                k in clean_text.lower()
                for k in ["opac", "catalogue", "library", "american", "british"]
            ):
                full_url = href if href.startswith("http") else f"{IEMCRP_BASE}{href}"
                resources.append(
                    {
                        "id": f"iemcrp_{hashlib.md5(clean_text.encode()).hexdigest()[:8]}",
                        "title": clean_text,
                        "category": "Library Catalogue & Membership",
                        "url": full_url,
                        "author": "IEM-UEM Central Library",
                        "description": f"Official Institutional Library Access: {clean_text}",
                    }
                )

        return {
            "raw_sha256": raw_sha256,
            "resources": resources,
            "retrieval_mode": "live",
        }

    def _fallback_portal_manifest(self) -> dict[str, Any]:
        """Local navigation links; no claim of live holdings or current access."""
        raw_sha256 = hashlib.sha256(b"iemcrp_verified_library_manifest_v1").hexdigest()
        return {
            "raw_sha256": raw_sha256,
            "retrieval_mode": "link_manifest",
            "resources": [
                {
                    "id": "iemcrp_uemk_opac",
                    "title": "UEM Kolkata - Library OPAC Portal",
                    "category": "Online Public Access Catalog",
                    "url": "http://uemk-opac.l2c2.co.in",
                    "author": "UEM Kolkata Central Library",
                    "description": "Search Books, Journals, Thesis, Project Reports and other Library Resources in UEM Kolkata.",
                },
                {
                    "id": "iemcrp_iem_saltlake",
                    "title": "IEM Saltlake - Library Catalogue",
                    "category": "Online Public Access Catalog",
                    "url": f"{IEMCRP_BASE}/iemEn/login.jsp",
                    "author": "IEM Saltlake Library",
                    "description": "Search Physical and Digital Resources in IEM Saltlake Campus.",
                },
                {
                    "id": "iemcrp_gurukul_opac",
                    "title": "IEM Gurukul Campus - Library OPAC",
                    "category": "Online Public Access Catalog",
                    "url": f"{IEMCRP_BASE}/iemEn/login.jsp",
                    "author": "IEM Gurukul Campus Library",
                    "description": "Library catalogue and holdings for IEM Gurukul Campus.",
                },
                {
                    "id": "iemcrp_digital_library",
                    "title": "IEM-UEM Digital Library Database Access",
                    "category": "Digital Library",
                    "url": f"{IEMCRP_BASE}/iemEn/login.jsp",
                    "author": "IEM-UEM Digital Resource Center",
                    "description": "Access to eBooks, eJournals, High-Performance Compute, and Online Research Databases.",
                },
                {
                    "id": "iemcrp_make_in_iem_uem",
                    "title": "Make in IEM UEM: Departmental Publications & Research Archives",
                    "category": "Institutional Research",
                    "url": f"{IEMCRP_BASE}/iemEn/login.jsp",
                    "author": "IEM-UEM Research Faculty",
                    "description": "Departmental research papers, seminar proceedings, and institute publications.",
                },
            ],
        }
