"""Unit tests for cross-provider canonical merging, Stage-2 enrichment, disambiguation, and workbook reporting."""

from __future__ import annotations

from io import BytesIO
import json
from unittest.mock import MagicMock

from openpyxl import load_workbook
import pytest

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.resilient_http import reliability_client
from archipelago.scholarly.intelligence.enrichment import enrich_papers_multi_provider
from archipelago.scholarly.intelligence.relevance_engine import (
    disambiguate_query,
    evaluate_relevance,
)
from archipelago.scholarly.intelligence.workbook import HEADERS, build_workbook

pytestmark = pytest.mark.unit


def _make_cand(
    source: str,
    title: str,
    doi: str | None = None,
    arxiv_id: str | None = None,
    openalex_id: str | None = None,
    s2_id: str | None = None,
    authors: list[str] | None = None,
    pub_date: str | None = "2023-05-01",
    citations: int | None = None,
    abstract: str | None = None,
) -> dict:
    paper = PaperRecord(
        title=title,
        abstract=abstract,
        authors=[PaperAuthor(name=a) for a in (authors or ["Alice Smith"])],
        publication_date=pub_date,
        identifiers=PaperIdentifiers(
            doi=doi,
            arxiv_id=arxiv_id,
            openalex_id=openalex_id,
            semantic_scholar_id=s2_id,
        ),
    )
    return {
        "source": source,
        "paper": paper,
        "provenance": ProvenancePointer(
            source_type=source,
            artifact_sha256="abc",
            source_record_id=openalex_id or doi or arxiv_id or s2_id or "id1",
            source_url=f"https://example.org/{source}/1",
        ),
        "citation_count": citations,
        "source_metadata": {},
    }


def test_canonicalizer_merges_by_title_author_year_and_ids_without_false_merges() -> None:
    canon = Canonicalizer()
    c1 = _make_cand(
        "openalex",
        "Efficiently Modeling Long Sequences with Structured State Spaces",
        openalex_id="https://openalex.org/W100",
        authors=["Albert Gu", "Karan Goel"],
        pub_date="2022-01-01",
        citations=500,
    )
    c2 = _make_cand(
        "arxiv",
        "Efficiently Modeling Long Sequences with Structured State Spaces",
        arxiv_id="2111.00396",
        authors=["Albert Gu", "Christopher Re"],
        pub_date="2021-11-01",
        abstract="We introduce S4.",
    )
    # Same title but completely different author and year -> must NOT merge
    c3 = _make_cand(
        "crossref",
        "Efficiently Modeling Long Sequences with Structured State Spaces",
        doi="10.9999/different",
        authors=["Zed Nobody"],
        pub_date="2015-01-01",
    )
    pool = canon.canonicalize_candidates([c1, c2, c3])
    assert len(pool) == 2
    merged = pool[0]
    assert merged["contributing_providers"] == ["openalex", "arxiv"]
    assert merged["identity_match_confidence"] == "verified_title_author_year"
    assert merged["paper"].abstract == "We introduce S4."
    assert merged["paper"].identifiers.arxiv_id == "2111.00396"
    assert "openalex" in merged["provider_records"] and "arxiv" in merged["provider_records"]
    assert merged["conflicting_observations"]  # pub_date differs (2022 vs 2021)


def test_reordered_compound_relevance_and_disambiguation() -> None:
    # Reordered compound 'space state model' <-> 'state-space model'
    ok = evaluate_relevance(
        "space state model",
        "Mixed effect state space model application for pharmacometrics",
        "A state-space model captures latent temporal dynamics.",
    )
    assert ok["eligible"] is True

    # Scattered false positive must still be rejected
    bad = evaluate_relevance(
        "space state model",
        "Space Weather Operations and Cosmic Explorer",
        "We study solar wind in space. Our steady state analysis uses a linear regression model.",
    )
    assert bad["eligible"] is False

    dis = disambiguate_query("space state model")
    assert dis["rewritten"] is False
    assert dis["raw_query"] == "space state model"
    assert dis["is_ambiguous"] is True
    assert any("state space model" in alt["interpretation"] for alt in dis["alternative_interpretations"])


def test_stage2_multi_provider_enrichment_handles_429_and_preserves_providers() -> None:
    reliability_client().clear_cache()
    sess = MagicMock()

    def _fake_get(url: str, **kwargs):
        resp = MagicMock()
        if "api.crossref.org/works/" in url:
            resp.status_code = 200
            resp.ok = True
            resp.json.return_value = {
                "message": {
                    "publisher": "IEEE",
                    "ISSN": ["1234-5678"],
                    "container-title": ["IEEE Trans. Signal Processing"],
                    "is-referenced-by-count": 42,
                    "funder": [{"name": "NSF", "DOI": "10.13039/100000001", "award": ["CCF-1"]}],
                }
            }
            return resp
        if "api.semanticscholar.org" in url:
            resp.status_code = 429
            resp.ok = False
            resp.headers = {}
            return resp
        if "api.openaire.eu" in url:
            resp.status_code = 200
            resp.ok = True
            resp.json.return_value = {"results": [{"id": "openaire::123"}]}
            return resp
        resp.status_code = 404
        resp.ok = False
        return resp

    sess.get.side_effect = _fake_get
    papers = [
        {
            "paper_id": "p1",
            "title": "A State-Space Model",
            "year": 2022,
            "doi": "10.1109/tsp.2022.1",
            "identifiers": {"doi": "10.1109/tsp.2022.1", "openalex_id": "https://openalex.org/W1"},
            "authors": [{"name": "Alice Smith"}],
            "provenance": [{"source_type": "openalex", "source_record_id": "W1", "source_url": "https://openalex.org/W1"}],
            "citation_observations": [{"provider": "openalex", "count": 40}],
            "source_metadata": {},
        }
    ]
    audit = enrich_papers_multi_provider(papers, session=sess)
    assert audit["secondary_matches"]["crossref"] == 1
    assert audit["secondary_matches"]["openaire"] == 1
    assert audit["providers"]["semantic_scholar"]["failures"]
    provs = {p["source_type"] for p in papers[0]["provenance"]}
    assert {"openalex", "crossref", "openaire"}.issubset(provs)
    assert papers[0]["publisher"] == "IEEE"
    assert papers[0]["citation_count"] == 42
    assert papers[0]["citation_provider"] == "crossref"


def test_workbook_14_sheets_and_accurate_manifest() -> None:
    run = {
        "schema": "archipelago.research_intelligence.v2",
        "options": {"topic": "space state model", "top_k": 20, "sort": "relevance"},
        "retrieved_at": "2026-11-16T00:00:00Z",
        "ordering": "relevance",
        "sort_metadata": {"selected": "relevance", "version": "archipelago.sort.v2", "definition": "Sorted by relevance"},
        "candidate_count": 10,
        "filtered_count": 2,
        "sources": [{"source": "openalex", "status": "live"}, {"source": "crossref", "status": "live"}],
        "provider_selection": {
            "waterfall": {"openalex": {"raw_records": 5, "selected_primary": 1}},
            "source_contributions": {"openalex": 1, "crossref": 1},
        },
        "query_disambiguation": {"raw_query": "space state model", "is_ambiguous": True},
        "enrichment_audit": {"providers": {"semantic_scholar": {"failures": [{"entity_id": "p1", "error": "HTTP 429"}]}}},
        "papers": [
            {
                "paper_id": "p1",
                "title": "State-Space Model",
                "year": 2024,
                "publication_date": "2024-01-01",
                "doi": "10.1000/ssm1",
                "url": "https://doi.org/10.1000/ssm1",
                "identifiers": {"doi": "10.1000/ssm1", "openalex_id": "W1"},
                "authors": [{"name": "Alice Smith", "orcid": "0000-0001-0002-0003"}],
                "venue": "Journal of SSM",
                "citation_count": 10,
                "citation_provider": "crossref",
                "citation_observations": [{"provider": "openalex", "count": 8}, {"provider": "crossref", "count": 10}],
                "evidence_status": "ABSTRACT_AVAILABLE",
                "references": [],
                "provenance": [
                    {"source_type": "openalex", "source_record_id": "W1", "source_url": "https://openalex.org/W1", "fetched_at": "2026-11-16T00:00:00Z", "contribution_type": "discovery_primary"},
                    {"source_type": "crossref", "source_record_id": "10.1000/ssm1", "source_url": "https://doi.org/10.1000/ssm1", "fetched_at": "2026-11-16T00:00:00Z", "contribution_type": "stage2_enrichment"},
                ],
                "identity_review": [],
                "eligibility_reason": "exact_phrase_or_concept_in_title_and_context",
                "relevance_classification": {"label": "HIGHLY_RELEVANT", "rule_version": "archipelago.relevance.v2"},
                "source_metadata": {"author_openalex_ids": ["A1"]},
            }
        ],
        "author_observations": [
            {"id": "A1", "name": "Alice Smith", "provider": "openalex", "enrichment_status": "AVAILABLE", "metrics": {"publication_count": 10, "citation_count": 100, "h_index": 5}},
            {"id": "orcid:0000-0001-0002-0003", "name": "Alice Smith", "provider": "orcid", "enrichment_status": "AVAILABLE", "metrics": {"publication_count": 12, "citation_count": None, "h_index": None}},
        ],
    }
    bio: BytesIO = build_workbook(run)
    wb = load_workbook(bio)
    assert len(wb.sheetnames) == 14
    assert set(wb.sheetnames) == set(HEADERS.keys())

    manifest = {r[0]: r[1] for r in wb["Run_Manifest"].iter_rows(min_row=2, values_only=True)}
    assert "ranking_policy" not in manifest
    assert manifest["sort_algorithm"] == "relevance"
    assert manifest["sort_version"] == "archipelago.sort.v2"
    assert "candidate_waterfall" in manifest
    assert "source_contributions" in manifest

    prov_rows = list(wb["Sources_Provenance"].iter_rows(min_row=2, values_only=True))
    assert len(prov_rows) == 2
    assert {r[1] for r in prov_rows} == {"openalex", "crossref"}

    author_rows = list(wb["Authors"].iter_rows(min_row=2, values_only=True))
    assert len(author_rows) == 2
    assert {r[16] for r in author_rows} == {"openalex", "orcid"}
