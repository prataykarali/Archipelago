"""Research-only discovery from domain-selected machine-readable scholarly sources."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.live_sources import LiveResearchSources
from archipelago.scholarly.discovery.provider_selector import select_providers
from archipelago.scholarly.pipeline.relevance import relevance_score

RESEARCH_SOURCES = ("openalex", "crossref", "arxiv", "semantic_scholar")


class DiscoveryOrchestrator:
    """Search official APIs while retaining exact source status and skip provenance."""

    def __init__(self, sources: LiveResearchSources | None = None) -> None:
        self.sources = sources or LiveResearchSources()
        self.canonicalizer = Canonicalizer()
        self.last_selection: dict[str, Any] = {}

    def discover_with_status(
        self,
        query: str,
        limit_per_source: int = 10,
        explicit_sources: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return canonical candidates and source summaries without fake success."""
        plan = select_providers(query, explicit_sources=explicit_sources)
        active = plan["selected"] or list(RESEARCH_SOURCES)
        with ThreadPoolExecutor(max_workers=len(active)) as executor:
            futures = [
                executor.submit(self.sources.search, source, query, limit_per_source)
                for source in active
            ]
            responses = [future.result() for future in futures]
        raw = [item for response in responses for item in response.records]
        candidates = self.canonicalizer.canonicalize_candidates(raw)
        candidates.sort(key=lambda item: -relevance_score(item, query)[0])
        summaries = [response.summary() for response in responses]
        for skipped in plan["skipped"]:
            summaries.append(
                {
                    "source": skipped["source"],
                    "requested_at": None,
                    "status": "skipped",
                    "record_count": 0,
                    "raw_sha256": None,
                    "request_id": None,
                    "http_status": None,
                    "error": skipped["reason"],
                    "rate_limited": False,
                }
            )
        self.last_selection = {
            "domain": plan["domain"],
            "providers_queried": active,
            "providers_skipped": plan["skipped"],
            "candidate_count": len(raw),
            "deduplicated_count": len(candidates),
        }
        return candidates, summaries

    def discover_topic(
        self,
        query: str,
        limit: int = 10,
        include_preprints: bool = True,
    ) -> list[dict[str, Any]]:
        """Return relevant metadata candidates; this does not create a job."""
        candidates, _sources = self.discover_with_status(query, limit_per_source=limit)
        if not include_preprints:
            candidates = [item for item in candidates if item.get("source") != "arxiv"]
        return candidates[:limit]
