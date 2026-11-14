"""Tier C domain-specific scholarly providers: Europe PMC, PubMed, ORCID."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import os
from typing import Any

import requests

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)

TIMEOUT_SECONDS = 15
EPMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
ORCID_PERSON_URL = "https://pub.orcid.org/v3.0/{orcid}/person"


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


def search_europe_pmc(session: requests.Session, query: str, limit: int) -> dict[str, Any]:
    """Query Europe PMC REST API for biomedical & life-science literature."""
    resp = session.get(
        EPMC_URL,
        params={"query": query, "format": "json", "resultType": "core", "pageSize": min(max(1, limit), 25)},
        headers={"Accept": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    sha = hashlib.sha256(resp.content).hexdigest()
    if resp.status_code == 429:
        return {"status": "rate_limited", "http_status": 429, "error": "http_429", "rate_limited": True, "raw_sha256": sha, "raw_body": resp.content, "records": []}
    resp.raise_for_status()
    items = (resp.json().get("resultList") or {}).get("result") or []
    records: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("title") or "").strip().rstrip(".")
        if not title:
            continue
        pmid = str(item.get("pmid") or "").strip() or None
        pmcid = str(item.get("pmcid") or "").strip() or None
        doi = str(item.get("doi") or "").strip() or None
        authors = [
            PaperAuthor(
                name=str(a.get("fullName")).strip(),
                institutions=[str(a.get("affiliation")).strip()] if a.get("affiliation") else [],
            )
            for a in ((item.get("authorList") or {}).get("author") or [])
            if isinstance(a, dict) and a.get("fullName")
        ]
        full_urls = (item.get("fullTextUrlList") or {}).get("fullTextUrl") or []
        oa_url = next((u.get("url") for u in full_urls if isinstance(u, dict) and u.get("url")), None)
        url = oa_url or (f"https://europepmc.org/article/MED/{pmid}" if pmid else None)
        paper = PaperRecord(
            title=title,
            identifiers=PaperIdentifiers(doi=doi, pmid=pmid, pmcid=pmcid),
            abstract=str(item.get("abstractText") or "").strip() or None,
            authors=authors,
            venue=str(item.get("journalTitle") or "").strip() or None,
            publication_date=str(item.get("firstPublicationDate") or item.get("pubYear") or "").strip() or None,
            publication_type="journal-article",
            is_open_access=(str(item.get("isOpenAccess") or "").upper() == "Y"),
            oa_url=oa_url,
        )
        records.append(
            {
                "source": "europe_pmc",
                "paper": paper,
                "provenance": _prov("europe_pmc", pmid or pmcid or doi, url, sha),
                "citation_count": item.get("citedByCount"),
                "source_metadata": {"pmid": pmid, "pmcid": pmcid, "landing_page_url": url},
            }
        )
    return {"status": "live" if records else "live_empty", "http_status": resp.status_code, "raw_sha256": sha, "raw_body": resp.content, "records": records}


def search_pubmed(session: requests.Session, query: str, limit: int) -> dict[str, Any]:
    """Query NCBI PubMed E-utilities (esearch + esummary) respecting rate limits."""
    params: dict[str, Any] = {"db": "pubmed", "term": query, "retmode": "json", "retmax": min(max(1, limit), 20)}
    api_key = os.getenv("NCBI_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key
    s_resp = session.get(PUBMED_SEARCH_URL, params=params, timeout=TIMEOUT_SECONDS)
    sha = hashlib.sha256(s_resp.content).hexdigest()
    if s_resp.status_code == 429:
        return {"status": "rate_limited", "http_status": 429, "error": "http_429", "rate_limited": True, "raw_sha256": sha, "raw_body": s_resp.content, "records": []}
    s_resp.raise_for_status()
    id_list = (s_resp.json().get("esearchresult") or {}).get("idlist") or []
    if not id_list:
        return {"status": "live_empty", "http_status": s_resp.status_code, "raw_sha256": sha, "raw_body": s_resp.content, "records": []}

    sum_params: dict[str, Any] = {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"}
    if api_key:
        sum_params["api_key"] = api_key
    sum_resp = session.get(PUBMED_SUMMARY_URL, params=sum_params, timeout=TIMEOUT_SECONDS)
    sha2 = hashlib.sha256(sum_resp.content).hexdigest()
    if sum_resp.status_code == 429:
        return {"status": "rate_limited", "http_status": 429, "error": "http_429", "rate_limited": True, "raw_sha256": sha2, "raw_body": sum_resp.content, "records": []}
    sum_resp.raise_for_status()
    result_map = sum_resp.json().get("result") or {}
    records: list[dict[str, Any]] = []
    for pmid in id_list:
        item = result_map.get(str(pmid))
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip().rstrip(".")
        if not title:
            continue
        doi = next(
            (str(aid.get("value")).strip() for aid in (item.get("articleids") or []) if isinstance(aid, dict) and aid.get("idtype") == "doi" and aid.get("value")),
            None,
        )
        authors = [PaperAuthor(name=str(a.get("name")).strip()) for a in (item.get("authors") or []) if isinstance(a, dict) and a.get("name")]
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        paper = PaperRecord(
            title=title,
            identifiers=PaperIdentifiers(doi=doi, pmid=str(pmid)),
            authors=authors,
            venue=str(item.get("fulljournalname") or item.get("source") or "").strip() or None,
            publication_date=str(item.get("pubdate") or "").strip()[:10] or None,
            publication_type="journal-article",
        )
        records.append(
            {
                "source": "pubmed",
                "paper": paper,
                "provenance": _prov("pubmed", str(pmid), url, sha2),
                "citation_count": None,
                "source_metadata": {"pmid": str(pmid), "landing_page_url": url},
            }
        )
    return {"status": "live" if records else "live_empty", "http_status": sum_resp.status_code, "raw_sha256": sha2, "raw_body": sum_resp.content, "records": records}


def fetch_orcid_record(session: requests.Session, orcid_id: str) -> dict[str, Any] | None:
    """Fetch public ORCID person metadata for an already-verified ORCID identifier."""
    clean = orcid_id.strip().rsplit("/", 1)[-1]
    if not clean:
        return None
    try:
        resp = session.get(
            ORCID_PERSON_URL.format(orcid=clean),
            headers={"Accept": "application/json"},
            timeout=8,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        name_obj = data.get("name") or {}
        given = ((name_obj.get("given-names") or {}).get("value") or "").strip()
        family = ((name_obj.get("family-name") or {}).get("value") or "").strip()
        return {
            "orcid": clean,
            "verified_name": f"{given} {family}".strip() or None,
            "source": "orcid_public_api",
        }
    except requests.RequestException:
        return None
