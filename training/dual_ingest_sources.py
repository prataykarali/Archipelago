"""Fetch source-linked abstracts for the dual-ingestion training set."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import re
from typing import Any

import requests

from archipelago.scholarly.discovery.live_sources import LiveResearchSources

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
QUERY_RESULTS = 50
REQUEST_TIMEOUT_SECONDS = 30
MIN_ABSTRACT_CHARS = 220
MAX_ABSTRACT_CHARS = 1800
SOURCE_TOPICS = {
    "openalex": (
        "graph neural network",
        "retrieval augmented generation",
        "diffusion model",
        "federated learning",
        "contrastive learning",
    ),
    "crossref": (
        "graph neural network",
        "protein structure prediction",
        "machine learning",
        "large language model",
        "Bayesian optimization",
        "reinforcement learning",
    ),
    "arxiv": (
        "graph neural network",
        "retrieval augmented generation",
        "diffusion model",
        "federated learning",
        "contrastive learning",
        "transformer",
    ),
    "europe_pmc": (
        "protein structure prediction",
        "machine learning",
        "large language model",
        "Bayesian optimization",
        "reinforcement learning",
    ),
    "semantic_scholar": ("graph neural network",),
}


@dataclass(frozen=True)
class SourcePaper:
    """A paper abstract with an independently inspectable source pointer."""

    provider: str
    identifier: str
    url: str
    title: str
    abstract: str
    doi: str | None
    topic: str


def _clean(value: object) -> str:
    """Normalize API XML/HTML fragments into plain sentence text."""
    source = html.unescape(str(value or ""))
    source = re.sub(r"<[^>]+>", " ", source)
    return " ".join(source.split())


def _bounded_abstract(value: object) -> str:
    """Keep complete sentences when a provider returns a long abstract."""
    abstract = _clean(value)
    if len(abstract) <= MAX_ABSTRACT_CHARS:
        return abstract
    last_stop = abstract.rfind(". ", MIN_ABSTRACT_CHARS, MAX_ABSTRACT_CHARS)
    return abstract[: last_stop + 1] if last_stop >= 0 else abstract[:MAX_ABSTRACT_CHARS]


def _api_papers(provider: str, topic: str) -> tuple[list[SourcePaper], dict[str, Any]]:
    """Reuse the production source adapter, preserving upstream status."""
    response = LiveResearchSources().search(provider, topic, QUERY_RESULTS)
    papers = []
    for item in response.records:
        record = item["paper"]
        identifiers = record.identifiers
        identifier = (
            identifiers.doi
            or identifiers.arxiv_id
            or identifiers.openalex_id
            or identifiers.semantic_scholar_id
            or record.title
        )
        url = item["provenance"].source_url or ""
        papers.append(
            SourcePaper(
                provider=provider,
                identifier=str(identifier),
                url=str(url),
                title=_clean(record.title),
                abstract=_bounded_abstract(record.abstract),
                doi=identifiers.doi,
                topic=topic,
            )
        )
    return papers, {**response.summary(), "query": topic}


def _europe_pmc_papers(topic: str) -> tuple[list[SourcePaper], dict[str, Any]]:
    """Use Europe PMC's core response so biomedical abstracts are included."""
    response = requests.get(
        EUROPE_PMC_URL,
        params={"query": topic, "format": "json", "pageSize": QUERY_RESULTS, "resultType": "core"},
        headers={"User-Agent": "ArchipelagoResearch/2.0 (training corpus audit)"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    items = response.json().get("resultList", {}).get("result", [])
    papers = []
    for item in items:
        identifier = f"{item.get('source', 'MED')}/{item.get('id', '')}"
        doi = item.get("doi")
        papers.append(
            SourcePaper(
                provider="europe_pmc",
                identifier=identifier,
                url=f"https://doi.org/{doi}"
                if doi
                else f"https://europepmc.org/article/{identifier}",
                title=_clean(item.get("title")),
                abstract=_bounded_abstract(item.get("abstractText")),
                doi=str(doi) if doi else None,
                topic=topic,
            )
        )
    return papers, {
        "source": "europe_pmc",
        "query": topic,
        "status": "live" if papers else "live_empty",
        "record_count": len(papers),
        "http_status": response.status_code,
        "raw_sha256": hashlib.sha256(response.content).hexdigest(),
    }


def fetch(provider: str, topic: str) -> tuple[list[SourcePaper], dict[str, Any]]:
    """Fetch one topic while preserving source failures for the manifest."""
    try:
        return (
            _europe_pmc_papers(topic) if provider == "europe_pmc" else _api_papers(provider, topic)
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        return [], {"source": provider, "query": topic, "status": "failed", "error": str(exc)}
