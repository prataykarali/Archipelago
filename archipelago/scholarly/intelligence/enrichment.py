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
    if url.startswith("https://api.openalex.org/") and (
        api_key := os.getenv("OPENALEX_API_KEY", "").strip()
    ):
        params = {**(params or {}), "api_key": api_key}
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = client.get(url, params=params, timeout=timeout)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < MAX_RETRIES:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                return (
                    None,
                    "PROVIDER_RATE_LIMITED" if resp.status_code == 429 else "PROVIDER_ERROR",
                )
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
            "counts_by_year": sorted(
                (row for row in counts if isinstance(row.get("year"), int)),
                key=lambda row: row["year"],
                reverse=True,
            )[:10],
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
                "venue_category": classify_venue_category(
                    item.get("display_name"), item.get("type")
                ),
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
                "topics": [
                    t.get("display_name") for t in item.get("topics") or [] if t.get("display_name")
                ][:8],
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
        repo in low_name
        for repo in ("arxiv", "biorxiv", "medrxiv", "ssrn", "preprint", "zenodo", "osf")
    ):
        return "preprint_repository"
    if "workshop" in low_name or low_type == "workshop":
        return "workshop"
    if "google research" in low_name or low_type == "institution":
        return "institutional_listing"
    if low_type == "journal":
        return "peer_reviewed_journal"
    if low_type == "conference" or any(
        tok in low_name for tok in ("conference", "proceedings", "symposium")
    ):
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
                params={
                    "fields": "name,aliases,affiliations,homepage,paperCount,citationCount,hIndex,url"
                },
                headers=headers,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                ttl_seconds=ttl,
                max_retries=1,
            )
            if resp is None or not resp.ok:
                status = (
                    "RATE_LIMITED"
                    if (resp is not None and resp.status_code == 429) or (err and "429" in err)
                    else "PROVIDER_UNAVAILABLE"
                )
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
                        "error": err
                        or (f"HTTP {resp.status_code}" if resp is not None else "unavailable"),
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
    """Fetch public ORCID person, works count, and affiliation records for verified ORCID IDs."""
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
            f"https://pub.orcid.org/v3.0/{orcid_id}/record",
            headers={"Accept": "application/json", "User-Agent": "Archipelago-Research/2.0"},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            ttl_seconds=ttl,
            max_retries=1,
        )
        if resp is not None and resp.ok:
            data = resp.json()
            person = data.get("person") or data
            name_obj = person.get("name") or {}
            given = ((name_obj.get("given-names") or {}).get("value") or "").strip()
            family = ((name_obj.get("family-name") or {}).get("value") or "").strip()
            credit = ((name_obj.get("credit-name") or {}).get("value") or "").strip()
            activities = data.get("activities-summary") or {}
            works_groups = (activities.get("works") or {}).get("group") or []
            works_count = (
                len(works_groups)
                if isinstance(works_groups, list) and "works" in activities
                else None
            )
            affs: list[dict[str, Any]] = []
            emp_groups = ((activities.get("employments") or {}).get("affiliation-group")) or []
            for grp in emp_groups[:5]:
                for sum_item in grp.get("summaries") or []:
                    emp = sum_item.get("employment-summary") or {}
                    org = (emp.get("organization") or {}).get("name")
                    if org:
                        affs.append({"institution": org, "years": []})
            rec = {
                "orcid": orcid_id,
                "orcid_url": f"https://orcid.org/{orcid_id}",
                "verified": True,
                "display_name": credit or f"{given} {family}".strip() or None,
                "works_count": works_count,
                "affiliations": affs,
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
            _ORCID_CACHE[orcid_id] = rec
            out[orcid_id] = rec
    return out


def orcid_author_observations(orcid_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build separate provider='orcid' author observations from verified ORCID records."""
    obs_list: list[dict[str, Any]] = []
    for orcid_id, rec in orcid_map.items():
        name = rec.get("display_name") or orcid_id
        obs_list.append(
            {
                "id": f"orcid:{orcid_id}",
                "orcid": f"https://orcid.org/{orcid_id}",
                "name": name,
                "aliases": [],
                "identity_status": "orcid_verified",
                "identity_confidence": "high_orcid_verified",
                "enrichment_status": "AVAILABLE",
                "provider": "orcid",
                "source_url": rec.get("orcid_url") or f"https://orcid.org/{orcid_id}",
                "google_scholar_search_url": generate_scholar_author_url(name),
                "google_scholar_profile_url": None,
                "google_scholar_status": "NOT_AVAILABLE",
                "retrieved_at": rec.get("retrieved_at"),
                "orcid_verified": True,
                "orcid_url": rec.get("orcid_url"),
                "metrics": {
                    "publication_count": rec.get("works_count"),
                    "citation_count": None,
                    "h_index": None,
                    "i10_index": None,
                    "definition": "ORCID public record works groups (ORCID does not index citations or h-index)",
                    "coverage": "ORCID public profile; self-asserted or member-pushed works",
                    "author_id": orcid_id,
                },
                "affiliations": rec.get("affiliations") or [],
                "current_affiliations": (rec.get("affiliations") or [])[:1],
                "topics": [],
            }
        )
    return obs_list


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
            ident = str(
                oa_id or author.get("orcid") or s2_id or f"unverified:{paper['paper_id']}:{idx}"
            )
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
        rec = dict(enriched_venues[short])
        if not rec.get("publisher") and metadata.get("publisher"):
            rec["publisher"] = metadata["publisher"]
        if not rec.get("issn") and metadata.get("venue_issn"):
            rec["issn"] = metadata["venue_issn"]
        if metadata.get("venue_provider") and metadata["venue_provider"] != rec.get("provider"):
            rec["contributing_venue_providers"] = sorted(
                {p for p in (rec.get("provider"), metadata.get("venue_provider")) if p}
            )
        return rec
    provider = (
        "openalex"
        if venue_id
        else (
            metadata.get("venue_provider") or paper.get("source") or paper.get("citation_provider")
        )
    )
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
        "source_metadata_url": venue_id
        if isinstance(venue_id, str) and venue_id.startswith("http")
        else None,
        "open_access": metadata.get("venue_is_oa"),
        "provider": provider,
        "retrieved_at": retrieved_at,
        "impact_factor": None,
        "citescore": None,
        "sjr": None,
        "core_rank": None,
        "licensed_metrics_status": "LICENSE_RESTRICTED",
    }


def _attach_provenance(
    paper: dict[str, Any],
    provider: str,
    record_id: str | None,
    source_url: str | None,
    fetched_at: str,
    contribution_type: str = "stage2_enrichment",
) -> None:
    """Attach a verified Stage-2 provider provenance entry without duplicating."""
    prov_list = list(paper.get("provenance") or [])
    if not any(p.get("source_type") == provider for p in prov_list):
        prov_list.append(
            {
                "source_type": provider,
                "source_record_id": record_id,
                "source_url": source_url,
                "fetched_at": fetched_at,
                "contribution_type": contribution_type,
            }
        )
    paper["provenance"] = prov_list
    contribs = list(paper.get("contributing_providers") or [])
    if provider not in contribs:
        contribs.append(provider)
    paper["contributing_providers"] = contribs
    prec = dict(paper.get("provider_records") or {})
    prec.setdefault(
        provider,
        {
            "source": provider,
            "source_record_id": record_id,
            "source_url": source_url,
            "fetched_at": fetched_at,
            "contribution_type": contribution_type,
        },
    )
    paper["provider_records"] = prec


def _record_citation_obs(paper: dict[str, Any], provider: str, count: int | None) -> None:
    """Append a provider-specific citation observation and update primary if higher."""
    if not isinstance(count, int):
        return
    obs = list(paper.get("citation_observations") or [])
    if not any(o.get("provider") == provider for o in obs):
        obs.append({"provider": provider, "count": count})
    paper["citation_observations"] = obs
    best = max(obs, key=lambda o: o["count"])
    paper["citation_count"] = best["count"]
    paper["citation_provider"] = best["provider"]
    year = paper.get("year")
    if isinstance(year, int):
        current_yr = datetime.now(UTC).year
        paper["citations_per_year"] = round(best["count"] / max(1, current_yr - year + 1), 2)


def _safe_json(resp: Any) -> dict[str, Any]:
    """Parse JSON safely, returning an empty dict on truncated or non-JSON responses."""
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def enrich_papers_multi_provider(
    papers: list[dict[str, Any]],
    session: requests.Session | None = None,
    max_per_provider: int = 12,
) -> dict[str, Any]:
    """Perform bounded Stage-2 cross-provider enrichment for selected papers.

    Enriches DOIs / arXiv IDs across Crossref, OpenAlex (for non-OpenAlex papers),
    Semantic Scholar, OpenAIRE, arXiv, and DataCite without fabricating metrics.
    """
    client = session or requests.Session()
    ttl = 900.0 if isinstance(client, requests.Session) else 0.0
    email = os.getenv("ARCHIPELAGO_CONTACT_EMAIL", "researcher@archipelago.local")
    headers = {"User-Agent": f"Archipelago-Research/2.0 (mailto:{email})"}

    audit: dict[str, dict[str, Any]] = {
        prov: {"attempts": 0, "successes": 0, "failures": []}
        for prov in ("openalex", "crossref", "semantic_scholar", "openaire", "arxiv", "datacite")
    }
    secondary_matches: dict[str, int] = dict.fromkeys(audit, 0)

    def _has_prov(paper: dict[str, Any], prov: str) -> bool:
        return any(p.get("source_type") == prov for p in (paper.get("provenance") or []))

    # 1. Batched OpenAlex DOI enrichment for papers NOT already from OpenAlex
    oa_targets = [p for p in papers if p.get("doi") and not _has_prov(p, "openalex")][
        :max_per_provider
    ]
    if oa_targets:
        dois_filter = "|".join(f"https://doi.org/{p['doi'].strip().lower()}" for p in oa_targets)
        audit["openalex"]["attempts"] += len(oa_targets)
        resp, err = reliability_client().get(
            client,
            "openalex",
            "https://api.openalex.org/works",
            params={"filter": f"doi:{dois_filter}", "per-page": len(oa_targets)},
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            ttl_seconds=ttl,
            max_retries=1,
        )
        now = datetime.now(UTC).isoformat()
        if resp is not None and resp.ok:
            by_doi = {}
            for item in _safe_json(resp).get("results") or []:
                d = str(item.get("doi") or "").lower().removeprefix("https://doi.org/")
                if d:
                    by_doi[d] = item
            for p in oa_targets:
                d = p["doi"].strip().lower()
                item = by_doi.get(d)
                if item:
                    oa_id = item.get("id")
                    p.setdefault("identifiers", {})["openalex_id"] = (
                        p["identifiers"].get("openalex_id") or oa_id
                    )
                    meta = p.setdefault("source_metadata", {})
                    if item.get("fwci") is not None and p.get("fwci") is None:
                        p["fwci"] = item.get("fwci")
                    if (
                        item.get("citation_normalized_percentile") is not None
                        and p.get("citation_normalized_percentile") is None
                    ):
                        p["citation_normalized_percentile"] = item["citation_normalized_percentile"]
                    if isinstance(item.get("referenced_works"), list):
                        p["reference_count"] = len(item["referenced_works"])
                        if not p.get("references"):
                            p["references"] = item["referenced_works"]
                    prim_loc = item.get("primary_location") or {}
                    src_obj = prim_loc.get("source") or {}
                    if not meta.get("venue_id") and src_obj.get("id"):
                        meta["venue_id"] = src_obj.get("id")
                    if not meta.get("author_openalex_ids"):
                        meta["author_openalex_ids"] = [
                            (a.get("author") or {}).get("id")
                            for a in (item.get("authorships") or [])
                        ]
                    if not p.get("topics"):
                        p["topics"] = [
                            t.get("display_name")
                            for t in (item.get("topics") or [])[:5]
                            if t.get("display_name")
                        ]
                    _record_citation_obs(p, "openalex", item.get("cited_by_count"))
                    _attach_provenance(p, "openalex", oa_id, oa_id, now)
                    audit["openalex"]["successes"] += 1
                    secondary_matches["openalex"] += 1
        else:
            audit["openalex"]["failures"].append(
                {
                    "entity_id": "batch_doi",
                    "error": err
                    or (f"HTTP {resp.status_code}" if resp is not None else "unavailable"),
                }
            )

    # 2. Crossref DOI enrichment for papers not yet from Crossref
    cr_targets = [p for p in papers if p.get("doi") and not _has_prov(p, "crossref")][
        :max_per_provider
    ]
    for p in cr_targets:
        doi = p["doi"].strip()
        audit["crossref"]["attempts"] += 1
        resp, err = reliability_client().get(
            client,
            "crossref",
            f"https://api.crossref.org/works/{doi}",
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            ttl_seconds=ttl,
            max_retries=1,
        )
        now = datetime.now(UTC).isoformat()
        if resp is not None and resp.ok:
            msg = _safe_json(resp).get("message") or {}
            meta = p.setdefault("source_metadata", {})
            if not meta.get("publisher") and msg.get("publisher"):
                meta["publisher"] = msg.get("publisher")
                p["publisher"] = p.get("publisher") or msg.get("publisher")
            if not meta.get("venue_issn") and msg.get("ISSN"):
                meta["venue_issn"] = msg.get("ISSN")
            if not meta.get("venue_provider"):
                meta["venue_provider"] = "crossref"
            if not p.get("venue") and msg.get("container-title"):
                p["venue"] = msg["container-title"][0]
            if not p.get("license") and msg.get("license"):
                p["license"] = (msg["license"][0] or {}).get("URL")
            if msg.get("funder"):
                grants = list(p.get("grants") or [])
                for f in msg["funder"]:
                    if isinstance(f, dict) and f.get("name"):
                        grants.append(
                            {
                                "funder_name": f.get("name"),
                                "funder_id": f.get("DOI"),
                                "award_id": "; ".join(f.get("award") or []) or None,
                                "provider": "crossref",
                            }
                        )
                p["grants"] = grants
            if msg.get("reference") and not p.get("references"):
                refs = [
                    r.get("DOI") for r in msg["reference"] if isinstance(r, dict) and r.get("DOI")
                ]
                if refs:
                    p["references"] = refs[:50]
            if p.get("reference_count") is None and isinstance(msg.get("reference-count"), int):
                p["reference_count"] = msg["reference-count"]
            # Merge author ORCIDs from Crossref
            cr_authors = msg.get("author") or []
            for idx, ba in enumerate(p.get("authors") or []):
                if idx < len(cr_authors) and not ba.get("orcid") and cr_authors[idx].get("ORCID"):
                    ba["orcid"] = cr_authors[idx]["ORCID"]
            _record_citation_obs(p, "crossref", msg.get("is-referenced-by-count"))
            _attach_provenance(p, "crossref", doi, f"https://doi.org/{doi}", now)
            audit["crossref"]["successes"] += 1
            secondary_matches["crossref"] += 1
        elif resp is None or resp.status_code != 404:
            audit["crossref"]["failures"].append(
                {
                    "entity_id": p["paper_id"],
                    "error": err
                    or (f"HTTP {resp.status_code}" if resp is not None else "unavailable"),
                }
            )

    # 3. Semantic Scholar enrichment (server-side API key if set; stop gracefully on 429)
    s2_headers = {"User-Agent": "Archipelago-Research/2.0"}
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
        s2_headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
    s2_targets = [
        p
        for p in papers
        if not _has_prov(p, "semantic_scholar")
        and (p.get("doi") or (p.get("identifiers") or {}).get("arxiv_id"))
    ][:max_per_provider]
    for p in s2_targets:
        ids = p.get("identifiers") or {}
        lookup_id = f"DOI:{p['doi']}" if p.get("doi") else f"ARXIV:{ids['arxiv_id']}"
        audit["semantic_scholar"]["attempts"] += 1
        resp, err = reliability_client().get(
            client,
            "semantic_scholar",
            f"https://api.semanticscholar.org/graph/v1/paper/{lookup_id}",
            params={
                "fields": "paperId,citationCount,influentialCitationCount,referenceCount,fieldsOfStudy,isOpenAccess,openAccessPdf,authors.authorId,authors.name,url"
            },
            headers=s2_headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            ttl_seconds=ttl,
            max_retries=1,
        )
        now = datetime.now(UTC).isoformat()
        if resp is not None and resp.ok:
            item = _safe_json(resp)
            s2_pid = item.get("paperId")
            if s2_pid:
                ids["semantic_scholar_id"] = ids.get("semantic_scholar_id") or s2_pid
                p["identifiers"] = ids
                meta = p.setdefault("source_metadata", {})
                if not meta.get("author_s2_ids"):
                    meta["author_s2_ids"] = [a.get("authorId") for a in (item.get("authors") or [])]
                if item.get("influentialCitationCount") is not None:
                    p["influential_citations"] = item.get("influentialCitationCount")
                if p.get("reference_count") is None and isinstance(item.get("referenceCount"), int):
                    p["reference_count"] = item["referenceCount"]
                pdf = item.get("openAccessPdf") or {}
                if not p.get("oa_url") and pdf.get("url"):
                    p["oa_url"] = pdf["url"]
                _record_citation_obs(p, "semantic_scholar", item.get("citationCount"))
                _attach_provenance(p, "semantic_scholar", s2_pid, item.get("url"), now)
                audit["semantic_scholar"]["successes"] += 1
                secondary_matches["semantic_scholar"] += 1
        else:
            is_rl = bool((resp is not None and resp.status_code == 429) or (err and "429" in err))
            audit["semantic_scholar"]["failures"].append(
                {
                    "entity_id": p["paper_id"],
                    "error": "HTTP 429 rate_limited"
                    if is_rl
                    else (
                        err or (f"HTTP {resp.status_code}" if resp is not None else "unavailable")
                    ),
                }
            )
            if is_rl:
                break

    # 4. OpenAIRE enrichment by DOI
    oa_air_targets = [p for p in papers if p.get("doi") and not _has_prov(p, "openaire")][
        :max_per_provider
    ]
    for p in oa_air_targets:
        doi = p["doi"].strip()
        audit["openaire"]["attempts"] += 1
        resp, err = reliability_client().get(
            client,
            "openaire",
            "https://api.openaire.eu/graph/v1/researchProducts",
            params={"pid": doi, "pageSize": 1},
            headers={"Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            ttl_seconds=ttl,
            max_retries=1,
        )
        now = datetime.now(UTC).isoformat()
        if resp is not None and resp.ok:
            items = _safe_json(resp).get("results") or []
            if items:
                item = items[0]
                oaire_id = str(item.get("id") or "").strip() or None
                ids = p.setdefault("identifiers", {})
                if oaire_id and not ids.get("openaire_id"):
                    ids["openaire_id"] = oaire_id
                url = (
                    f"https://explore.openaire.eu/search/publication?pid={oaire_id}"
                    if oaire_id
                    else None
                )
                _attach_provenance(p, "openaire", oaire_id or doi, url, now)
                audit["openaire"]["successes"] += 1
                secondary_matches["openaire"] += 1
        else:
            audit["openaire"]["failures"].append(
                {
                    "entity_id": p["paper_id"],
                    "error": err
                    or (f"HTTP {resp.status_code}" if resp is not None else "unavailable"),
                }
            )

    # 5. arXiv enrichment for papers with arxiv_id not yet carrying arXiv provenance
    arx_targets = [
        p
        for p in papers
        if (p.get("identifiers") or {}).get("arxiv_id") and not _has_prov(p, "arxiv")
    ][:max_per_provider]
    for p in arx_targets:
        arx_id = str(p["identifiers"]["arxiv_id"]).strip().removeprefix("https://arxiv.org/abs/")
        audit["arxiv"]["attempts"] += 1
        resp, err = reliability_client().get(
            client,
            "arxiv",
            "https://export.arxiv.org/api/query",
            params={"id_list": arx_id},
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            ttl_seconds=ttl,
            max_retries=1,
        )
        now = datetime.now(UTC).isoformat()
        if resp is not None and resp.ok and b"<entry>" in resp.content:
            _attach_provenance(p, "arxiv", arx_id, f"https://arxiv.org/abs/{arx_id}", now)
            audit["arxiv"]["successes"] += 1
            secondary_matches["arxiv"] += 1
        elif resp is None or not resp.ok:
            audit["arxiv"]["failures"].append(
                {
                    "entity_id": p["paper_id"],
                    "error": err
                    or (f"HTTP {resp.status_code}" if resp is not None else "unavailable"),
                }
            )

    # 6. DataCite enrichment only if DOI is actually registered in DataCite (404 = not a DataCite DOI, not an error)
    dc_targets = [
        p
        for p in papers
        if p.get("doi")
        and not _has_prov(p, "datacite")
        and (
            p["doi"].startswith("10.5281/")
            or p["doi"].startswith("10.48550/")
            or (p.get("identifiers") or {}).get("datacite_doi")
        )
    ][:max_per_provider]
    for p in dc_targets:
        doi = p["doi"].strip()
        audit["datacite"]["attempts"] += 1
        resp, err = reliability_client().get(
            client,
            "datacite",
            f"https://api.datacite.org/dois/{doi}",
            headers={"Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            ttl_seconds=ttl,
            max_retries=1,
        )
        now = datetime.now(UTC).isoformat()
        if resp is not None and resp.ok:
            _attach_provenance(p, "datacite", doi, f"https://doi.org/{doi}", now)
            audit["datacite"]["successes"] += 1
            secondary_matches["datacite"] += 1
        elif resp is None or (resp.status_code not in (200, 404)):
            audit["datacite"]["failures"].append(
                {
                    "entity_id": p["paper_id"],
                    "error": err
                    or (f"HTTP {resp.status_code}" if resp is not None else "unavailable"),
                }
            )

    return {"providers": audit, "secondary_matches": secondary_matches}
