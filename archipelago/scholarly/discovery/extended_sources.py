"""Tier A/B official scholarly providers: DBLP, OpenAIRE, DataCite, OpenCitations."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from typing import Any

import requests

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)

TIMEOUT_SECONDS = 15
DBLP_URL = "https://dblp.org/search/publ/api"
OPENAIRE_URL = "https://api.openaire.eu/graph/v1/researchProducts"
DATACITE_URL = "https://api.datacite.org/dois"
OPENCITATIONS_COUNT_URL = "https://api.opencitations.net/index/v2/citation-count/doi:"
OPENCITATIONS_CITING_URL = "https://api.opencitations.net/index/v2/citations/doi:"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _prov(source: str, rec_id: str | None, url: str | None, sha: str) -> ProvenancePointer:
    return ProvenancePointer(
        source_type=source,
        artifact_sha256=sha,
        source_record_id=rec_id,
        source_url=url,
        fetched_at=_now_iso(),
    )


def _dblp_authors(raw: Any) -> tuple[list[PaperAuthor], list[str]]:
    items = raw if isinstance(raw, list) else ([raw] if isinstance(raw, (dict, str)) else [])
    authors: list[PaperAuthor] = []
    pids: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("text") or "").strip()
            pid = str(item.get("@pid") or "").strip()
        else:
            name, pid = str(item).strip(), ""
        if name:
            authors.append(PaperAuthor(name=name))
        if pid:
            pids.append(pid)
    return authors, pids


def search_dblp(session: requests.Session, query: str, limit: int) -> dict[str, Any]:
    """Query DBLP publication search API; surface HTTP 202 bot gate without bypassing."""
    resp = session.get(
        DBLP_URL,
        params={"q": query, "format": "json", "h": min(max(1, limit), 30)},
        headers={"Accept": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    sha = hashlib.sha256(resp.content).hexdigest()
    ctype = (resp.headers.get("content-type") or "").lower()
    if resp.status_code == 202 or "text/html" in ctype or "not a bot" in resp.text.lower():
        return {
            "status": "blocked_bot_challenge",
            "http_status": resp.status_code,
            "error": "dblp_bot_protection_gate",
            "rate_limited": False,
            "raw_sha256": sha,
            "raw_body": resp.content,
            "records": [],
        }
    if resp.status_code == 429:
        return {
            "status": "rate_limited",
            "http_status": 429,
            "error": "http_429",
            "rate_limited": True,
            "raw_sha256": sha,
            "raw_body": resp.content,
            "records": [],
        }
    resp.raise_for_status()
    hits = ((resp.json().get("result") or {}).get("hits") or {}).get("hit") or []
    records: list[dict[str, Any]] = []
    for hit in hits:
        info = hit.get("info") or {}
        title = str(info.get("title") or "").strip().rstrip(".")
        if not title:
            continue
        authors, pids = _dblp_authors((info.get("authors") or {}).get("author"))
        doi = str(info.get("doi") or "").strip() or None
        key = str(info.get("key") or "").strip() or None
        ee = info.get("ee")
        ee_url = ee[0] if isinstance(ee, list) and ee else (ee if isinstance(ee, str) else None)
        url = ee_url or str(info.get("url") or "").strip() or None
        year = str(info.get("year") or "").strip() or None
        ptype = str(info.get("type") or "").strip().lower() or "proceedings-article"
        paper = PaperRecord(
            title=title,
            identifiers=PaperIdentifiers(doi=doi, dblp_key=key),
            authors=authors,
            venue=str(info.get("venue") or "").strip() or None,
            publication_date=year,
            publication_type=ptype,
        )
        records.append(
            {
                "source": "dblp",
                "paper": paper,
                "provenance": _prov("dblp", key or doi, url, sha),
                "citation_count": None,
                "source_metadata": {
                    "dblp_key": key,
                    "dblp_author_pids": pids,
                    "dblp_type": info.get("type"),
                    "landing_page_url": url,
                },
            }
        )
    return {
        "status": "live" if records else "live_empty",
        "http_status": resp.status_code,
        "raw_sha256": sha,
        "raw_body": resp.content,
        "records": records,
    }


def search_openaire(session: requests.Session, query: str, limit: int) -> dict[str, Any]:
    """Query OpenAIRE Graph API v1 researchProducts."""
    resp = session.get(
        OPENAIRE_URL,
        params={"search": query, "pageSize": min(max(1, limit), 30), "page": 1},
        headers={"Accept": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    sha = hashlib.sha256(resp.content).hexdigest()
    if resp.status_code == 429:
        return {"status": "rate_limited", "http_status": 429, "error": "http_429", "rate_limited": True, "raw_sha256": sha, "raw_body": resp.content, "records": []}
    resp.raise_for_status()
    items = resp.json().get("results") or []
    records: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("mainTitle") or "").strip()
        if not title:
            continue
        pids = item.get("pids") or []
        doi = next((str(p.get("value")).strip() for p in pids if (p.get("scheme") or "").lower() == "doi" and p.get("value")), None)
        oa_id = str(item.get("id") or "").strip() or None
        authors = [PaperAuthor(name=str(a.get("fullName")).strip()) for a in (item.get("authors") or []) if isinstance(a, dict) and a.get("fullName")]
        desc = item.get("descriptions") or []
        abstract = str(desc[0]).strip() if desc and isinstance(desc[0], str) else None
        projects = [
            {"funder": (p.get("funding") or [{}])[0].get("shortName") if isinstance(p.get("funding"), list) and p.get("funding") else None, "award_id": p.get("code"), "title": p.get("title")}
            for p in (item.get("projects") or [])
            if isinstance(p, dict)
        ]
        access = ((item.get("bestAccessRight") or {}).get("label") or "").lower()
        is_oa = True if "open" in access else (False if access else None)
        url = f"https://explore.openaire.eu/search/publication?pid={oa_id}" if oa_id else None
        paper = PaperRecord(
            title=title,
            identifiers=PaperIdentifiers(doi=doi, openaire_id=oa_id),
            abstract=abstract,
            authors=authors,
            venue=str((item.get("container") or {}).get("name") or "").strip() or None,
            publication_date=str(item.get("publicationDate") or "").strip()[:10] or None,
            publication_type=str(item.get("type") or "publication").lower(),
            is_open_access=is_oa,
        )
        records.append(
            {
                "source": "openaire",
                "paper": paper,
                "provenance": _prov("openaire", oa_id or doi, url, sha),
                "citation_count": None,
                "source_metadata": {
                    "openaire_id": oa_id,
                    "grants": projects,
                    "oa_status": access or None,
                    "landing_page_url": url,
                },
            }
        )
    return {"status": "live" if records else "live_empty", "http_status": resp.status_code, "raw_sha256": sha, "raw_body": resp.content, "records": records}


def search_datacite(session: requests.Session, query: str, limit: int) -> dict[str, Any]:
    """Query DataCite REST API for datasets, software, and research outputs."""
    resp = session.get(
        DATACITE_URL,
        params={"query": query, "page[size]": min(max(1, limit), 30)},
        headers={"Accept": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    sha = hashlib.sha256(resp.content).hexdigest()
    if resp.status_code == 429:
        return {"status": "rate_limited", "http_status": 429, "error": "http_429", "rate_limited": True, "raw_sha256": sha, "raw_body": resp.content, "records": []}
    resp.raise_for_status()
    items = resp.json().get("data") or []
    records: list[dict[str, Any]] = []
    for item in items:
        attrs = item.get("attributes") or {}
        titles = attrs.get("titles") or []
        title = str((titles[0] or {}).get("title") or "").strip() if titles else ""
        if not title:
            continue
        doi = str(attrs.get("doi") or item.get("id") or "").strip() or None
        rtype = str((attrs.get("types") or {}).get("resourceTypeGeneral") or "dataset").strip().lower()
        creators = [
            PaperAuthor(name=str(c.get("name")).strip())
            for c in (attrs.get("creators") or [])
            if isinstance(c, dict) and c.get("name")
        ]
        descs = attrs.get("descriptions") or []
        abstract = str((descs[0] or {}).get("description") or "").strip() if descs else None
        url = str(attrs.get("url") or (f"https://doi.org/{doi}" if doi else "")).strip() or None
        grants = [
            {"funder": f.get("funderName"), "award_id": f.get("awardNumber"), "title": f.get("awardTitle")}
            for f in (attrs.get("fundingReferences") or [])
            if isinstance(f, dict)
        ]
        related = attrs.get("relatedIdentifiers") or []
        year = str(attrs.get("publicationYear") or "").strip() or None
        paper = PaperRecord(
            title=title,
            identifiers=PaperIdentifiers(doi=doi, datacite_doi=doi),
            abstract=abstract,
            authors=creators,
            venue=str(attrs.get("publisher") or "").strip() or None,
            publication_date=year,
            publication_type=rtype,
            is_open_access=True,
            oa_url=url,
        )
        records.append(
            {
                "source": "datacite",
                "paper": paper,
                "provenance": _prov("datacite", doi, url, sha),
                "citation_count": attrs.get("citationCount"),
                "source_metadata": {
                    "datacite_doi": doi,
                    "resource_type_general": rtype,
                    "publisher": attrs.get("publisher"),
                    "related_identifiers": related[:15],
                    "grants": grants,
                    "landing_page_url": url,
                },
            }
        )
    return {"status": "live" if records else "live_empty", "http_status": resp.status_code, "raw_sha256": sha, "raw_body": resp.content, "records": records}


def fetch_opencitations_for_dois(
    session: requests.Session, dois: list[str], max_dois: int = 8
) -> dict[str, dict[str, Any]]:
    """Fetch external OpenCitations citation counts for DOI-linked papers."""
    out: dict[str, dict[str, Any]] = {}
    for doi in dois[:max_dois]:
        clean = doi.strip().lower()
        if not clean:
            continue
        try:
            resp = session.get(f"{OPENCITATIONS_COUNT_URL}{clean}", timeout=8)
            if resp.status_code == 200:
                payload = resp.json()
                count = int(payload[0].get("count", 0)) if isinstance(payload, list) and payload else 0
                out[clean] = {"provider": "opencitations", "count": count, "status": "live"}
            elif resp.status_code == 429:
                out[clean] = {"provider": "opencitations", "count": None, "status": "rate_limited"}
                break
        except requests.RequestException:
            continue
    return out
