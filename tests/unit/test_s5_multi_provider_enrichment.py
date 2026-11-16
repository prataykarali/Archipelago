"""Comprehensive unit tests for multi-provider discovery, Google Research/Scholar, citation graph, and XLSX."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

from openpyxl import load_workbook
import pytest

from archipelago.scholarly.discovery.google_research import classify_google_research_paper
from archipelago.scholarly.discovery.live_sources import LiveResearchSources
from archipelago.scholarly.discovery.resilient_http import reliability_client
from archipelago.scholarly.intelligence.enrichment import (
    classify_venue_category,
    detect_author_collisions,
)
from archipelago.scholarly.intelligence.graph import build_graph
from archipelago.scholarly.intelligence.search import validate_options
from archipelago.scholarly.intelligence.workbook import build_workbook

pytestmark = pytest.mark.unit


def test_provider_http_429_reports_rate_limited_never_empty() -> None:
    reliability_client().clear_cache()
    sess = MagicMock()
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.ok = False
    resp_429.headers = {"Retry-After": "0"}
    resp_429.content = b'{"error":"rate limit"}'
    sess.get.return_value = resp_429

    src = LiveResearchSources(session=sess)
    res = src.search("semantic_scholar", "omni ai models", 5)
    assert res.status == "rate_limited"
    assert res.rate_limited is True
    assert res.http_status == 429
    assert res.records == []


def test_google_research_affiliation_not_misclassified_as_official_listing() -> None:
    paper = {
        "title": "Multimodal Omni Modeling",
        "doi": "10.1000/omni1",
        "identifiers": {"arxiv_id": "2501.00001"},
        "authors": [
            {"name": "Alice Google", "institutions": ["Google DeepMind"]},
            {"name": "Bob Univ", "institutions": ["MIT"]},
        ],
        "author_institutions": [[{"name": "Google DeepMind", "ror": "https://ror.org/05k576t58"}], [{"name": "MIT"}]],
    }
    res = classify_google_research_paper(paper, official_listings=set())
    assert res["official_listing"] is False
    assert "GOOGLE_RESEARCH_OFFICIAL_LISTING" not in res["classifications"]
    assert "GOOGLE_AUTHOR_AFFILIATION" in res["classifications"]
    assert "GOOGLE_COLLABORATOR" in res["classifications"]

    official = classify_google_research_paper(paper, official_listings={"10.1000/omni1"})
    assert official["official_listing"] is True
    assert "GOOGLE_RESEARCH_OFFICIAL_LISTING" in official["classifications"]


def test_same_name_author_collision_flagged_and_not_merged() -> None:
    papers = [
        {
            "paper_id": "p1",
            "authors": [{"name": "Wei Zhang", "institutions": ["Tsinghua"]}],
            "source_metadata": {"author_openalex_ids": ["https://openalex.org/A100"]},
        },
        {
            "paper_id": "p2",
            "authors": [{"name": "Wei Zhang", "institutions": ["Stanford"]}],
            "source_metadata": {"author_openalex_ids": ["https://openalex.org/A200"]},
        },
    ]
    collisions = detect_author_collisions(papers)
    assert collisions == ["wei zhang"]


def test_preprint_vs_published_venue_classification() -> None:
    assert classify_venue_category("arXiv", "repository") == "preprint_repository"
    assert classify_venue_category("ICML Workshop on Agents", "conference") == "workshop"
    assert classify_venue_category("Nature Machine Intelligence", "journal") == "peer_reviewed_journal"
    assert classify_venue_category("NeurIPS Proceedings", "conference") == "peer_reviewed_conference"


def test_citation_graph_resolves_doi_and_deduplicates_edges() -> None:
    run = {
        "options": {"topic": "omni ai models"},
        "retrieved_at": "2026-11-16T00:00:00Z",
        "papers": [
            {
                "paper_id": "p1",
                "title": "Paper One",
                "url": "https://doi.org/10.1000/p1",
                "doi": "10.1000/p1",
                "identifiers": {"doi": "10.1000/p1", "openalex_id": "https://openalex.org/W1"},
                "authors": [{"name": "A. One"}],
                "references": ["10.1000/p2", "https://doi.org/10.1000/p2", "https://openalex.org/W999"],
                "source": "crossref",
                "citation_provider": "crossref",
            },
            {
                "paper_id": "p2",
                "title": "Paper Two",
                "url": "https://doi.org/10.1000/p2",
                "doi": "10.1000/p2",
                "identifiers": {"doi": "10.1000/p2", "openalex_id": "https://openalex.org/W2"},
                "authors": [{"name": "B. Two"}],
                "references": [],
                "source": "openalex",
                "citation_provider": "openalex",
            },
        ],
    }
    graph = build_graph(run)
    cites = [e for e in graph["edges"] if e["type"] == "CITES"]
    assert len(cites) == 1
    assert cites[0]["source"] == "paper:p1"
    assert cites[0]["target"] == "paper:p2"
    assert graph["coverage_report"]["total_reference_links"] == 3
    assert graph["coverage_report"]["in_collection_edges"] == 1


def test_conflicting_citations_and_unavailable_scholar_in_xlsx() -> None:
    run = {
        "schema": "archipelago.research_intelligence.v2",
        "options": validate_options({"topic": "omni ai models", "sort": "citations_per_year"}),
        "retrieved_at": "2026-11-16T00:00:00Z",
        "ordering": "citations_per_year",
        "sources": [{"source": "openalex", "status": "live", "record_count": 1}],
        "papers": [
            {
                "paper_id": "p1",
                "title": "Omni AI",
                "year": 2025,
                "publication_date": "2025-05-01",
                "doi": None,
                "url": "https://arxiv.org/abs/2505.00001",
                "identifiers": {"arxiv_id": "2505.00001"},
                "publication_type": "preprint",
                "published_vs_preprint": "preprint",
                "authors": [{"name": "Author A", "institutions": ["Google Research"]}],
                "topics": ["Omni AI"],
                "research_field": "Computer Science",
                "methods": [],
                "datasets": [],
                "evaluation_metrics": [],
                "claims": [],
                "abstract": "We study omni ai models.",
                "venue": "arXiv",
                "citation_count": 12,
                "citations_per_year": 6.0,
                "citation_provider": "semantic_scholar",
                "citation_observations": [
                    {"provider": "semantic_scholar", "count": 12},
                    {"provider": "openalex", "count": 9},
                ],
                "references": [],
                "provenance": [{"source_type": "arxiv", "source_url": "https://arxiv.org/abs/2505.00001", "fetched_at": "2026-11-16T00:00:00Z"}],
                "evidence_status": "ABSTRACT_AVAILABLE",
                "identity_review": [],
                "google_research": {"classifications": ["GOOGLE_AUTHOR_AFFILIATION"]},
                "google_scholar_url": "https://scholar.google.com/scholar?q=%22Omni%20AI%22",
                "venue_details": {"name": "arXiv", "venue_category": "preprint_repository", "provider": "arxiv"},
            }
        ],
        "author_observations": [],
    }
    book = load_workbook(BytesIO(build_workbook(run).getvalue()))
    assert len(book.sheetnames) == 14
    metric_rows = list(book["Metric_Observations"].iter_rows(min_row=2, values_only=True))
    cit_providers = {(r[2], r[4], r[3]) for r in metric_rows if r[0] == "Paper"}
    assert ("citation_count", "semantic_scholar", 12) in cit_providers
    assert ("citation_count", "openalex", 9) in cit_providers
    author_headers = [c.value for c in book["Authors"][1]]
    gs_prof_idx = author_headers.index("Google Scholar profile") + 1
    assert book["Authors"].cell(2, gs_prof_idx).value == "NOT_AVAILABLE"
