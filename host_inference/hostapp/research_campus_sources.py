"""Discover bounded, public institutional URLs from official sitemaps."""

from __future__ import annotations

import os
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

SITEMAPS = (
    "https://uem.edu.in/uem-kolkata/page-sitemap.xml",
    "https://iem.edu.in/page-sitemap.xml",
)
ALLOWED_HOSTS = frozenset({"uem.edu.in", "iem.edu.in"})
PATH_TERMS = ("syllabus", "research", "publication", "library", "curriculum")
EXCLUDED_TERMS = ("login", "credential", "password", "access", "private", "admin")
MAX_SITEMAP_BYTES = 2_000_000
SITEMAP_TIMEOUT_SECONDS = 12
SEARCH_LIMIT = 10


def _approved_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_HOSTS
        and any(term in path for term in PATH_TERMS)
        and not any(term in path for term in EXCLUDED_TERMS)
        and not path.endswith((".pdf", ".jpg", ".jpeg", ".png", ".xml"))
    )


def discover_campus_pages() -> list[str]:
    """List relevant public HTML pages; never follow arbitrary sitemap hosts."""
    pages: set[str] = set()
    for sitemap in SITEMAPS:
        response = requests.get(
            sitemap,
            timeout=SITEMAP_TIMEOUT_SECONDS,
            allow_redirects=False,
            headers={"User-Agent": "ArchipelagoResearch/1.0 (+academic metadata intake)"},
        )
        response.raise_for_status()
        if len(response.content) > MAX_SITEMAP_BYTES:
            raise ValueError("Campus sitemap exceeds the discovery limit")
        root = ElementTree.fromstring(response.content)
        for item in root.iter():
            if item.tag.rsplit("}", 1)[-1] != "loc" or not item.text:
                continue
            url = item.text.strip()
            if _approved_url(url):
                pages.add(url)
    return sorted(pages)


def discover_serpapi_pages() -> list[str]:
    """Use one search-credit fallback when official sitemaps are unavailable."""
    key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not key:
        return []
    response = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google",
            "q": "site:uem.edu.in OR site:iem.edu.in syllabus research library publications",
            "num": SEARCH_LIMIT,
            "api_key": key,
        },
        timeout=SITEMAP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("organic_results", [])
    if not isinstance(results, list):
        raise ValueError("Unexpected SerpAPI response")
    return sorted(
        {
            str(item.get("link"))
            for item in results
            if isinstance(item, dict) and _approved_url(str(item.get("link") or ""))
        }
    )
