"""Batched, cached, rate-limit-aware Stage-2 scholarly enrichment."""

from __future__ import annotations

from datetime import UTC, datetime
import re
import time
from typing import Any

import requests

AUTHOR_ID = re.compile(r"^(?:https://openalex\.org/)?(A\d+)$")
SOURCE_ID = re.compile(r"^(?:https://openalex\.org/)?(S\d+)$")
BATCH_SIZE = 50
DEFAULT_AUTHOR_BATCHES = 4
DEFAULT_TIMEOUT_SECONDS = 8
MAX_RETRIES = 2

_AUTHOR_CACHE: dict[str, dict[str, Any]] = {}
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
    for entry in data.get("affiliations") or []:
        inst = entry.get("institution") or {}
        if inst.get("display_name"):
            affs.append(
                {
                    "institution": inst.get("display_name"),
                    "institution_id": inst.get("id"),
                    "ror": inst.get("ror"),
                    "country_code": inst.get("country_code"),
                    "type": inst.get("type"),
                    "years": entry.get("years") or [],
                }
            )
    return {
        "id": author_id,
        "name": data.get("display_name") or fallback_name,
        "aliases": data.get("display_name_alternatives") or [],
        "orcid": data.get("orcid") or fallback_orcid,
        "identity_status": "provider_linked",
        "enrichment_status": "AVAILABLE",
        "provider": "openalex",
        "source_url": f"https://openalex.org/{author_id}",
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
    return {
        "id": venue_id,
        "name": name,
        "type": metadata.get("venue_type"),
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
