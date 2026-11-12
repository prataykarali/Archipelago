"""Conservative OpenAlex author and venue observations for selected papers."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

import requests

AUTHOR_ID = re.compile(r"^(?:https://openalex\.org/)?(A\d+)$")
MAX_AUTHOR_LOOKUPS = 8
AUTHOR_TIMEOUT_SECONDS = 5


def enrich_authors(
    papers: list[dict[str, Any]], session: requests.Session | None = None
) -> list[dict[str, Any]]:
    """Fetch metrics only for provider-linked IDs, never for name matches."""
    client = session or requests.Session()
    observations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for paper in papers:
        provider_ids = paper.get("source_metadata", {}).get("author_openalex_ids") or []
        for index, author in enumerate(paper["authors"]):
            candidate = provider_ids[index] if index < len(provider_ids) else None
            match = AUTHOR_ID.fullmatch(candidate) if isinstance(candidate, str) else None
            if not match or match.group(1) in seen:
                continue
            author_id = match.group(1)
            seen.add(author_id)
            if len(seen) > MAX_AUTHOR_LOOKUPS:
                return observations
            observed_at = datetime.now(UTC).isoformat()
            try:
                response = client.get(
                    f"https://api.openalex.org/authors/{author_id}",
                    timeout=AUTHOR_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError):
                observations.append(
                    {
                        "id": author_id,
                        "name": author["name"],
                        "identity_status": "provider_linked",
                        "metrics": None,
                        "provider": "openalex",
                        "retrieved_at": observed_at,
                        "error": "author_lookup_unavailable",
                    }
                )
                continue
            if str(data.get("id", "")).rsplit("/", 1)[-1] != author_id:
                observations.append(
                    {
                        "id": author_id,
                        "name": author["name"],
                        "identity_status": "ambiguous",
                        "metrics": None,
                        "provider": "openalex",
                        "retrieved_at": observed_at,
                        "error": "provider_id_mismatch",
                    }
                )
                continue
            stats = data.get("summary_stats") or {}
            observations.append(
                {
                    "id": author_id,
                    "name": data.get("display_name") or author["name"],
                    "orcid": data.get("orcid") or author.get("orcid"),
                    "identity_status": "provider_linked",
                    "provider": "openalex",
                    "retrieved_at": observed_at,
                    "metrics": {
                        "publication_count": data.get("works_count"),
                        "citation_count": data.get("cited_by_count"),
                        "h_index": stats.get("h_index"),
                        "i10_index": stats.get("i10_index"),
                        "definition": "OpenAlex indexed works and citations at retrieval time",
                        "coverage": "OpenAlex corpus; may omit works and citations",
                        "author_id": author_id,
                    },
                    "affiliations": [
                        {
                            "institution": (entry.get("institution") or {}).get("display_name"),
                            "years": entry.get("years") or [],
                        }
                        for entry in data.get("affiliations") or []
                    ],
                    "topics": [
                        entry.get("display_name")
                        for entry in data.get("topics") or []
                        if entry.get("display_name")
                    ],
                }
            )
    return observations


def venue_observation(paper: dict[str, Any], retrieved_at: str) -> dict[str, Any] | None:
    """Retain only provider supplied venue facts and mark licensed metrics absent."""
    metadata = paper.get("source_metadata") or {}
    name = paper.get("venue")
    if not name:
        return None
    venue_id = metadata.get("venue_id")
    provider = "openalex" if venue_id else paper.get("citation_provider")
    return {
        "id": venue_id,
        "name": name,
        "type": metadata.get("venue_type"),
        "publisher": metadata.get("publisher"),
        "issn": metadata.get("venue_issn"),
        "url": metadata.get("venue_url"),
        "open_access": metadata.get("venue_is_oa"),
        "provider": provider,
        "retrieved_at": retrieved_at,
        "impact_factor": None,
        "citescore": None,
        "sjr": None,
        "core_rank": None,
    }
