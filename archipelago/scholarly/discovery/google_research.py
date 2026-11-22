"""Official Google Research publication discovery and affiliation classification.

Respects https://research.google/robots.txt and HTTP 403 automated-access restrictions.
Never bypasses access controls and never conflates Google author affiliation with
an official Google Research publication listing.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
import urllib.parse

import requests

from archipelago.scholarly.discovery.resilient_http import reliability_client

GOOGLE_RESEARCH_PUBS_URL = "https://research.google/pubs/"
GOOGLE_ROR_IDS = frozenset(
    {
        "https://ror.org/00njsd438",  # Google (United States)
        "https://ror.org/05k576t58",  # Google DeepMind / DeepMind
        "https://ror.org/032s22845",  # Google (Switzerland)
        "https://ror.org/036d21t16",  # Google (United Kingdom)
    }
)
GOOGLE_INST_RE = re.compile(
    r"\b(google(?:\s+research|\s+deepmind|\s+brain|\s+ai|\s+llc)?|deepmind)\b",
    re.IGNORECASE,
)


def google_research_search_url(query: str) -> str:
    """Return official Google Research publications navigation URL for a query."""
    cleaned = " ".join((query or "").split())
    if not cleaned:
        return GOOGLE_RESEARCH_PUBS_URL
    return f"{GOOGLE_RESEARCH_PUBS_URL}?search={urllib.parse.quote(cleaned)}"


def check_google_research_access(
    session: requests.Session,
    query: str,
) -> dict[str, Any]:
    """Check permitted access to research.google/pubs/ without bypassing restrictions."""
    nav_url = google_research_search_url(query)
    resp, err = reliability_client().get(
        session,
        "google_research",
        GOOGLE_RESEARCH_PUBS_URL,
        headers={"User-Agent": "Archipelago-Research/2.0 (academic metadata discovery)"},
        timeout=10,
        ttl_seconds=3600.0,
        max_retries=1,
    )
    if resp is None:
        return {
            "source": "google_research",
            "status": "request_failed",
            "http_status": None,
            "error": err or "request_failed",
            "official_url": nav_url,
            "record_count": 0,
            "records": [],
        }
    sha = hashlib.sha256(resp.content).hexdigest()
    if resp.status_code in {401, 403, 451}:
        return {
            "source": "google_research",
            "status": "automated_access_restricted",
            "http_status": resp.status_code,
            "error": "robots_or_http_403_restricted",
            "official_url": nav_url,
            "raw_sha256": sha,
            "record_count": 0,
            "records": [],
        }
    if resp.status_code == 429:
        return {
            "source": "google_research",
            "status": "rate_limited",
            "http_status": 429,
            "error": "http_429",
            "rate_limited": True,
            "official_url": nav_url,
            "raw_sha256": sha,
            "record_count": 0,
            "records": [],
        }
    return {
        "source": "google_research",
        "status": "navigation_only" if resp.ok else "http_error",
        "http_status": resp.status_code,
        "error": None if resp.ok else f"HTTP {resp.status_code}",
        "official_url": nav_url,
        "raw_sha256": sha,
        "record_count": 0,
        "records": [],
    }


def _is_google_institution(name: str | None = None, ror: str | None = None) -> bool:
    if ror and ror.strip().lower().rstrip("/") in GOOGLE_ROR_IDS:
        return True
    if name and GOOGLE_INST_RE.search(name):
        return True
    return False


def classify_google_research_paper(
    paper: dict[str, Any],
    official_listings: set[str] | None = None,
) -> dict[str, Any]:
    """Separately classify official Google Research listing vs author affiliation vs collaborator.

    Never labels a paper GOOGLE_RESEARCH_OFFICIAL_LISTING merely because an author
    has a Google affiliation.
    """
    title_key = " ".join((paper.get("title") or "").casefold().split())
    doi_key = (paper.get("doi") or "").casefold().strip()
    arxiv_key = (paper.get("identifiers", {}).get("arxiv_id") or "").casefold().strip()
    listings = official_listings or set()
    is_official = bool(
        (title_key and title_key in listings)
        or (doi_key and doi_key in listings)
        or (arxiv_key and arxiv_key in listings)
    )

    authors = paper.get("authors") or []
    author_insts = paper.get("author_institutions") or []
    google_authors: list[str] = []
    collaborator_authors: list[str] = []

    for idx, author in enumerate(authors):
        name = author.get("name") or f"Author {idx + 1}"
        has_google = any(_is_google_institution(name=inst) for inst in (author.get("institutions") or []))
        if not has_google and idx < len(author_insts):
            for inst_obj in author_insts[idx] or []:
                if isinstance(inst_obj, dict) and _is_google_institution(
                    name=inst_obj.get("name"), ror=inst_obj.get("ror")
                ):
                    has_google = True
                    break
        if has_google:
            google_authors.append(name)
        else:
            collaborator_authors.append(name)

    classifications: list[str] = []
    if is_official:
        classifications.append("GOOGLE_RESEARCH_OFFICIAL_LISTING")
    if google_authors:
        classifications.append("GOOGLE_AUTHOR_AFFILIATION")
        if collaborator_authors:
            classifications.append("GOOGLE_COLLABORATOR")

    return {
        "official_listing": is_official,
        "official_listing_status": (
            "GOOGLE_RESEARCH_OFFICIAL_LISTING" if is_official else "NOT_VERIFIED_IN_OFFICIAL_LISTING"
        ),
        "google_author_affiliation": bool(google_authors),
        "google_affiliated_authors": google_authors,
        "google_collaborators": collaborator_authors if google_authors else [],
        "classifications": classifications or ["NONE"],
        "official_search_url": google_research_search_url(paper.get("title") or ""),
    }
