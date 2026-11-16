"""Batched, cached, rate-limit-aware Stage-2 scholarly enrichment."""

from __future__ import annotations

from datetime import UTC, datetime
import os
import re
import time
from typing import Any

import requests

from archipelago.scholarly.discovery.resilient_http import reliability_client
from archipelago.scholarly.discovery.scholar_deeplink import generate_scholar_author_url

AUTHOR_ID = re.compile(r"^(?:https://openalex\.org/)?(A\d+)$")
SOURCE_ID = re.compile(r"^(?:https://openalex\.org/)?(S\d+)$")
ORCID_RE = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")
BATCH_SIZE = 50
DEFAULT_AUTHOR_BATCHES = 4
DEFAULT_TIMEOUT_SECONDS = 8
MAX_RETRIES = 2

_AUTHOR_CACHE: dict[str, dict[str, Any]] = {}
_S2_AUTHOR_CACHE: dict[str, dict[str, Any]] = {}
_ORCID_CACHE: dict[str, dict[str, Any]] = {}
_VENUE_CACHE: dict[str, dict[str, Any]] = {}


def _get_json_with_retry(
    client: requests.Session,
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any] | None, str | None]:
    """Execute GET with rate-limit-aware backoff; return (payload, error_status)."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = client.get(url, params=params, timeout=timeout)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < MAX_RETRIES:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                return None, "PROVIDER_RATE_LIMITED" if resp.status_code == 429 else "PROVIDER_ERROR"
            resp.raise_for_status()
            data = resp.json()
            return (data if isinstance(data, dict) else None), None
        except (requests.RequestException, ValueError):
            if attempt < MAX_RETRIES:
                time.sleep(0.3)
                continue
            return None, "PROVIDER_UNAVAILABLE"
    return None, "RETRY_EXHAUSTED"


def _author_observation_from_oa(
    author_id: str,
    fallback_name: str,
    fallback_orcid: str | None,
    data: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    stats = data.get("summary_stats") or {}
    counts = data.get("counts_by_year") or []
    years = [c.get("year") for c in counts if isinstance(c.get("year"), int)]
    affs = []
    current_affs = []
    latest_aff_year = -1
    for entry in data.get("affiliations") or []:
        inst = entry.get("institution") or {}
        if inst.get("display_name"):
            yrs = [y for y in (entry.get("years") or []) if isinstance(y, int)]
            aff_item = {
                "institution": inst.get("display_name"),
                "institution_id": inst.get("id"),
                "ror": inst.get("ror"),
                "country_code": inst.get("country_code"),
                "type": inst.get("type"),
                "years": yrs,
            }
            affs.append(aff_item)
            if yrs and max(yrs) > latest_aff_year:
                latest_aff_year = max(yrs)
                current_affs = [aff_item]
            elif yrs and max(yrs) == latest_aff_year:
                current_affs.append(aff_item)
    name = data.get("display_name") or fallback_name
    orcid_val = data.get("orcid") or fallback_orcid
    return {
        "id": author_id,
        "name": name,
        "aliases": data.get("display_name_alternatives") or [],
        "orcid": orcid_val,
        "identity_status": "provider_linked",
        "identity_confidence": "high_provider_id",
        "enrichment_status": "AVAILABLE",
        "provider": "openalex",
        "source_url": f"https://openalex.org/{author_id}",
        "google_scholar_search_url": generate_scholar_author_url(name),
        "google_scholar_profile_url": None,
        "google_scholar_status": "NOT_AVAILABLE",
        "retrieved_at": observed_at,
        "metrics": {
            "publication_count": data.get("works_count"),
            "citation_count": data.get("cited_by_count"),
            "h_index": stats.get("h_index"),
            "i10_index": stats.get("i10_index"),
            "2yr_mean_citedness": stats.get("2yr_mean_citedness"),
            "counts_by_year": counts[:10],
            "earliest_year": min(years) if years else None,
            "latest_year": max(years) if years else None,
            "definition": "OpenAlex indexed works and citations at retrieval time",
            "coverage": "OpenAlex corpus; may omit works and citations",
            "author_id": author_id,
        },
        "affiliations": affs,
        "current_affiliations": current_affs or affs[:1],
        "topics": [
            entry.get("display_name")
            for entry in data.get("topics") or []
            if entry.get("display_name")
        ][:10],
    }


def enrich_authors(
    papers: list[dict[str, Any]],
    session: requests.Session | None = None,
    max_batches: int = DEFAULT_AUTHOR_BATCHES,
) -> list[dict[str, Any]]:
    """Fetch OpenAlex metrics in bounded 50-ID batches for all eligible author IDs."""
    client = session or requests.Session()
    observations: list[dict[str, Any]] = []
    targets: dict[str, tuple[str, str | None]] = {}
    for paper in papers:
        provider_ids = paper.get("source_metadata", {}).get("author_openalex_ids") or []
        for index, author in enumerate(paper.get("authors") or []):
            candidate = provider_ids[index] if index < len(provider_ids) else None
            match = AUTHOR_ID.fullmatch(candidate) if isinstance(candidate, str) else None
            if match and match.group(1) not in targets:
                targets[match.group(1)] = (author.get("name") or "Unknown", author.get("orcid"))

    pending_ids: list[str] = []
    for aid in targets:
        if aid in _AUTHOR_CACHE:
            observations.append(_AUTHOR_CACHE[aid])
        else:
            pending_ids.append(aid)

    batches_used = 0
    for start in range(0, len(pending_ids), BATCH_SIZE):
        chunk = pending_ids[start : start + BATCH_SIZE]
        observed_at = datetime.now(UTC).isoformat()
        if batches_used >= max_batches:
            for aid in chunk:
                name, orcid = targets[aid]
                observations.append(
                    {
                        "id": aid,
                        "name": name,
                        "orcid": orcid,
                        "identity_status": "provider_linked",
                        "enrichment_status": "ENRICHMENT_PENDING",
                        "metrics": None,
                        "provider": "openalex",
                        "retrieved_at": observed_at,
                        "error": "ENRICHMENT_PENDING",
                    }
                )
            continue
        batches_used += 1
        data, err = _get_json_with_retry(
            client,
            "https://api.openalex.org/authors",
            params={"filter": f"openalex_id:{'|'.join(chunk)}", "per-page": len(chunk)},
        )
        if not data or not isinstance(data.get("results"), list):
            for aid in chunk:
                name, orcid = targets[aid]
                observations.append(
                    {
                        "id": aid,
                        "name": name,
                        "orcid": orcid,
                        "identity_status": "provider_linked",
                        "enrichment_status": err or "PROVIDER_UNAVAILABLE",
                        "metrics": None,
                        "provider": "openalex",
                        "retrieved_at": observed_at,
                        "error": err or "author_lookup_unavailable",
                    }
                )
            continue
        returned: dict[str, dict[str, Any]] = {
            str(item.get("id") or "").rsplit("/", 1)[-1]: item
            for item in data["results"]
            if item.get("id")
        }
        for aid in chunk:
            name, orcid = targets[aid]
            item = returned.get(aid)
            if item is None:
                observations.append(
                    {
                        "id": aid,
                        "name": name,
                        "orcid": orcid,
                        "identity_status": "provider_linked",
                        "enrichment_status": "PROVIDER_FIELD_ABSENT",
                        "metrics": None,
                        "provider": "openalex",
                        "retrieved_at": observed_at,
                        "error": "author_not_returned_in_batch",
                    }
                )
                continue
            obs = _author_observation_from_oa(aid, name, orcid, item, observed_at)
            _AUTHOR_CACHE[aid] = obs
            observations.append(obs)
    return observations


def enrich_venues(
    papers: list[dict[str, Any]],
    session: requests.Session | None = None,
) -> dict[str, dict[str, Any]]:
    """Batch-enrich OpenAlex source/venue records without conflating licensed metrics."""
    client = session or requests.Session()
    by_id: dict[str, dict[str, Any]] = {}
    to_fetch: list[str] = []
    for paper in papers:
        vid = (paper.get("source_metadata") or {}).get("venue_id")
        match = SOURCE_ID.fullmatch(vid) if isinstance(vid, str) else None
        if not match:
            continue
        sid = match.group(1)
        if sid in _VENUE_CACHE:
            by_id[sid] = _VENUE_CACHE[sid]
        elif sid not in to_fetch:
            to_fetch.append(sid)

    for start in range(0, len(to_fetch), BATCH_SIZE):
        chunk = to_fetch[start : start + BATCH_SIZE]
        observed_at = datetime.now(UTC).isoformat()
        data, _err = _get_json_with_retry(
            client,
            "https://api.openalex.org/sources",
            params={"filter": f"openalex_id:{'|'.join(chunk)}", "per-page": len(chunk)},
        )
        if not data or not isinstance(data.get("results"), list):
            continue
        for item in data["results"]:
            sid = str(item.get("id") or "").rsplit("/", 1)[-1]
            if not sid:
                continue
            stats = item.get("summary_stats") or {}
            record = {
                "id": f"https://openalex.org/{sid}",
                "short_id": sid,
                "name": item.get("display_name"),
                "alternate_titles": item.get("alternate_titles") or [],
                "type": item.get("type"),
                "venue_category": classify_venue_category(item.get("display_name"), item.get("type")),
                "publisher": item.get("host_organization_name"),
                "issn": item.get("issn") or [],
                "issn_l": item.get("issn_l"),
                "url": item.get("homepage_url"),
                "source_metadata_url": f"https://openalex.org/{sid}",
                "open_access": item.get("is_oa"),
                "is_in_doaj": item.get("is_in_doaj"),
                "works_count": item.get("works_count"),
                "cited_by_count": item.get("cited_by_count"),
                "h_index": stats.get("h_index"),
                "i10_index": stats.get("i10_index"),
                "openalex_2yr_mean_citedness": stats.get("2yr_mean_citedness"),
                "counts_by_year": (item.get("counts_by_year") or [])[:10],
                "topics": [t.get("display_name") for t in item.get("topics") or [] if t.get("display_name")][:8],
                "provider": "openalex",
                "retrieved_at": observed_at,
                "impact_factor": None,
                "citescore": None,
                "sjr": None,
                "core_rank": None,
                "licensed_metrics_status": "LICENSE_RESTRICTED",
            }
            _VENUE_CACHE[sid] = record
            by_id[sid] = record
    return by_id


def classify_venue_category(name: str | None, venue_type: str | None = None) -> str:
    """Strictly distinguish peer-reviewed venues, workshops, preprint repositories, and institutional listings."""
    low_name = (name or "").casefold()
    low_type = (venue_type or "").casefold()
    if low_type == "repository" or any(
        repo in low_name for repo in ("arxiv", "biorxiv", "medrxiv", "ssrn", "preprint", "zenodo", "osf")
    ):
        return "preprint_repository"
    if "workshop" in low_name or low_type == "workshop":
        return "workshop"
    if "google research" in low_name or low_type == "institution":
        return "institutional_listing"
    if low_type == "journal":
        return "peer_reviewed_journal"
    if low_type == "conference" or any(tok in low_name for tok in ("conference", "proceedings", "symposium")):
        return "peer_reviewed_conference"
    return "unknown"


def enrich_s2_authors(
    papers: list[dict[str, Any]],
    session: requests.Session | None = None,
    max_authors: int = 20,
) -> list[dict[str, Any]]:
    """Fetch Semantic Scholar author metrics for authors with S2 author IDs, bounded and cached."""
    client = session or requests.Session()
    targets: dict[str, str] = {}
    for paper in papers:
        s2_ids = (paper.get("source_metadata") or {}).get("author_s2_ids") or []
        for idx, author in enumerate(paper.get("authors") or []):
            s2_id = s2_ids[idx] if idx < len(s2_ids) else None
            if isinstance(s2_id, str) and s2_id.isdigit() and s2_id not in targets:
                targets[s2_id] = author.get("name") or "Unknown"
                if len(targets) >= max_authors:
                    break
        if len(targets) >= max_authors:
            break
    if not targets:
        return []

    observations: list[dict[str, Any]] = []
    pending: list[str] = []
    for sid in targets:
        if sid in _S2_AUTHOR_CACHE:
            observations.append(_S2_AUTHOR_CACHE[sid])
        else:
            pending.append(sid)

    if pending:
        headers = {"User-Agent": "Archipelago-Research/2.0"}
        if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
            headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
        observed_at = datetime.now(UTC).isoformat()
        ttl = 3600.0 if isinstance(client, requests.Session) else 0.0
        for sid in pending:
            resp, err = reliability_client().get(
                client,
                "semantic_scholar",
                f"https://api.semanticscholar.org/graph/v1/author/{sid}",
                params={"fields": "name,aliases,affiliations,homepage,paperCount,citationCount,hIndex,url"},
                headers=headers,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                ttl_seconds=ttl,
                max_retries=1,
            )
            if resp is None or not resp.ok:
                status = "RATE_LIMITED" if (resp is not None and resp.status_code == 429) or (err and "429" in err) else "PROVIDER_UNAVAILABLE"
                observations.append(
                    {
                        "id": f"s2:{sid}",
                        "s2_author_id": sid,
                        "name": targets[sid],
                        "identity_status": "provider_linked",
                        "enrichment_status": status,
                        "provider": "semantic_scholar",
                        "retrieved_at": observed_at,
                        "metrics": None,
                        "error": err or (f"HTTP {resp.status_code}" if resp is not None else "unavailable"),
                    }
                )
                if status == "RATE_LIMITED":
                    break
                continue
            item = resp.json()
            name = item.get("name") or targets[sid]
            obs = {
                "id": f"s2:{sid}",
                "s2_author_id": sid,
                "name": name,
                "aliases": item.get("aliases") or [],
                "identity_status": "provider_linked",
                "identity_confidence": "high_provider_id",
                "enrichment_status": "AVAILABLE",
                "provider": "semantic_scholar",
                "source_url": item.get("url") or f"https://www.semanticscholar.org/author/{sid}",
                "google_scholar_search_url": generate_scholar_author_url(name),
                "google_scholar_profile_url": None,
                "google_scholar_status": "NOT_AVAILABLE",
                "retrieved_at": observed_at,
                "metrics": {
                    "publication_count": item.get("paperCount"),
                    "citation_count": item.get("citationCount"),
                    "h_index": item.get("hIndex"),
                    "i10_index": None,
                    "definition": "Semantic Scholar indexed papers, citations, and h-index",
                    "coverage": "Semantic Scholar corpus; may differ from OpenAlex",
                    "author_id": sid,
                },
                "affiliations": [
                    {"institution": aff, "years": []}
                    for aff in (item.get("affiliations") or [])
                    if isinstance(aff, str) and aff
                ],
                "current_affiliations": [
                    {"institution": aff, "years": []}
                    for aff in (item.get("affiliations") or [])
                    if isinstance(aff, str) and aff
                ],
                "topics": [],
            }
            _S2_AUTHOR_CACHE[sid] = obs
            observations.append(obs)
    return observations


def enrich_orcid_authors(
    papers: list[dict[str, Any]],
    session: requests.Session | None = None,
    max_authors: int = 15,
) -> dict[str, dict[str, Any]]:
    """Fetch public ORCID person records for authors with verified ORCID IDs."""
    client = session or requests.Session()
    orcids: list[str] = []
    for paper in papers:
        for author in paper.get("authors") or []:
            raw = str(author.get("orcid") or "")
            m = ORCID_RE.search(raw)
            if m and m.group(1) not in orcids:
                orcids.append(m.group(1))
                if len(orcids) >= max_authors:
                    break
        if len(orcids) >= max_authors:
            break
    out: dict[str, dict[str, Any]] = {}
    ttl = 3600.0 if isinstance(client, requests.Session) else 0.0
    for orcid_id in orcids:
        if orcid_id in _ORCID_CACHE:
            out[orcid_id] = _ORCID_CACHE[orcid_id]
            continue
        resp, _err = reliability_client().get(
            client,
            "orcid",
            f"https://pub.orcid.org/v3.0/{orcid_id}/person",
            headers={"Accept": "application/json", "User-Agent": "Archipelago-Research/2.0"},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            ttl_seconds=ttl,
            max_retries=1,
        )
        if resp is not None and resp.ok:
            data = resp.json()
            name_obj = (data.get("name") or {})
            given = ((name_obj.get("given-names") or {}).get("value") or "").strip()
            family = ((name_obj.get("family-name") or {}).get("value") or "").strip()
            credit = ((name_obj.get("credit-name") or {}).get("value") or "").strip()
            rec = {
                "orcid": orcid_id,
                "orcid_url": f"https://orcid.org/{orcid_id}",
                "verified": True,
                "display_name": credit or f"{given} {family}".strip() or None,
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
            _ORCID_CACHE[orcid_id] = rec
            out[orcid_id] = rec
    return out


def detect_author_collisions(papers: list[dict[str, Any]]) -> list[str]:
    """Flag normalized author names that appear with distinct or missing provider IDs."""
    seen: dict[str, set[str]] = {}
    for paper in papers:
        oa_ids = (paper.get("source_metadata") or {}).get("author_openalex_ids") or []
        s2_ids = (paper.get("source_metadata") or {}).get("author_s2_ids") or []
        for idx, author in enumerate(paper.get("authors") or []):
            name = " ".join(str(author.get("name") or "").casefold().split())
            if not name:
                continue
            oa_id = oa_ids[idx] if idx < len(oa_ids) else None
            s2_id = s2_ids[idx] if idx < len(s2_ids) else None
            ident = str(oa_id or author.get("orcid") or s2_id or f"unverified:{paper['paper_id']}:{idx}")
            seen.setdefault(name, set()).add(ident)
    return sorted(name for name, idents in seen.items() if len(idents) > 1)


def venue_observation(
    paper: dict[str, Any],
    retrieved_at: str,
    enriched_venues: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Retain provider-supplied venue facts and mark licensed metrics explicitly restricted."""
    metadata = paper.get("source_metadata") or {}
    name = paper.get("venue")
    if not name:
        return None
    venue_id = metadata.get("venue_id")
    short = venue_id.rsplit("/", 1)[-1] if isinstance(venue_id, str) else None
    if short and enriched_venues and short in enriched_venues:
        return enriched_venues[short]
    provider = "openalex" if venue_id else paper.get("citation_provider")
    vtype = metadata.get("venue_type")
    return {
        "id": venue_id,
        "name": name,
        "type": vtype,
        "venue_category": classify_venue_category(name, vtype),
        "publisher": metadata.get("publisher"),
        "issn": metadata.get("venue_issn"),
        "issn_l": metadata.get("venue_issn_l"),
        "url": metadata.get("venue_url"),
        "source_metadata_url": venue_id if isinstance(venue_id, str) and venue_id.startswith("http") else None,
        "open_access": metadata.get("venue_is_oa"),
        "provider": provider,
        "retrieved_at": retrieved_at,
        "impact_factor": None,
        "citescore": None,
        "sjr": None,
        "core_rank": None,
        "licensed_metrics_status": "LICENSE_RESTRICTED",
    }
