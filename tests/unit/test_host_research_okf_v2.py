"""OKF v2 emits every requested category without inventing source metrics."""

from __future__ import annotations

from pathlib import Path
import sys

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.research_okf import build_paper_okf  # noqa: E402
from hostapp.research_okf_fields import PARAMETER_FIELDS  # noqa: E402


def test_okf_v2_all_fields_and_missing_states() -> None:
    record = {
        "kind": "paper",
        "record_key": "a" * 64,
        "title": "Graph neural networks",
        "source_name": "OpenAlex",
        "source_url": "https://openalex.org/W1",
        "content": "",
        "published_at": "2020-01-01",
        "metadata": {"citation_count": 12, "source_timestamp": "2026-10-21T00:00:00Z"},
    }
    result = build_paper_okf(record, "graph networks")
    assert result["okf_version"] == "2.1.0"
    assert set(result["parameters"]) == set(PARAMETER_FIELDS)
    for group, fields in PARAMETER_FIELDS.items():
        assert set(result["parameters"][group]) == set(fields)
        for observation in result["parameters"][group].values():
            assert observation["observed_at"]
            assert observation["provenance"][0]["source_timestamp"]
            assert "confidence" in observation
            assert observation["extractor_version"]
    citation = result["parameters"]["citation_metrics"]
    assert citation["citation_count"]["value"] == 12
    assert citation["age_normalized_citations"]["status"] == "derived"
    assert citation["field_normalized_citation_impact"]["value"] is None
    assert result["parameters"]["author_metrics"]["h_index"]["status"] == "unknown"
    assert result["parameters"]["experiments"]["datasets"]["status"] == "unknown"


def test_okf_v2_uses_only_verified_source_history() -> None:
    record = {
        "kind": "paper",
        "record_key": "b" * 64,
        "title": "Diffusion models",
        "source_name": "OpenAlex",
        "source_url": "https://openalex.org/W2",
        "topic": "diffusion models",
        "content": "Diffusion models for images",
        "metadata": {
            "counts_by_year": [
                {"year": 2024, "cited_by_count": 3},
                {"year": 2025, "cited_by_count": 8},
            ],
            "authors": [{"name": "Researcher", "orcid": "https://orcid.org/0000"}],
            "source_timestamp": "2026-10-21T00:00:00Z",
        },
    }
    result = build_paper_okf(record)["parameters"]
    assert result["citation_metrics"]["citation_velocity"]["value"] == 8
    assert result["citation_metrics"]["citation_acceleration"]["value"] == 5
    assert result["paper_identity"]["orcid"]["value"] == ["https://orcid.org/0000"]
    assert result["author_metrics"]["total_citations"]["value"] is None


def test_pdf_extraction_needs_page_and_matching_evidence() -> None:
    record = {
        "kind": "paper",
        "record_key": "c" * 64,
        "title": "Evidence paper",
        "source_name": "arXiv",
        "source_url": "https://arxiv.org/abs/1",
        "metadata": {
            "source_timestamp": "2026-10-21T00:00:00Z",
            "pdf_sha256": "source-pdf",
            "verified_extractions": [
                {
                    "group": "experiments",
                    "field": "datasets",
                    "value": "MNIST",
                    "verification_status": "verified",
                    "pdf_page": 3,
                    "pdf_sha256": "source-pdf",
                    "evidence_text": "We evaluated on the MNIST dataset.",
                },
                {
                    "group": "efficiency",
                    "field": "flops",
                    "value": 123,
                    "verification_status": "verified",
                    "pdf_page": None,
                    "evidence_text": "123 FLOPs",
                },
            ],
        },
    }
    result = build_paper_okf(record)["parameters"]
    assert result["experiments"]["datasets"]["value"] == ["MNIST"]
    assert result["experiments"]["datasets"]["provenance"][0]["pdf_page"] == 3
    assert result["efficiency"]["flops"]["value"] is None


def test_full_evidence_log_keeps_multiple_verified_values_for_one_field() -> None:
    record = {
        "kind": "paper",
        "record_key": "e" * 64,
        "title": "Graph methods",
        "source_name": "openalex",
        "source_url": "https://openalex.org/W5",
        "content": "We introduce GraphSAGE. We propose a sampling algorithm.",
        "metadata": {
            "verified_extractions": [
                {
                    "group": "methodology",
                    "field": "contributions",
                    "value": "GraphSAGE",
                    "evidence_text": "We introduce GraphSAGE.",
                    "verification_status": "abstract_quote_matched",
                },
                {
                    "group": "methodology",
                    "field": "contributions",
                    "value": "a sampling algorithm",
                    "evidence_text": "We propose a sampling algorithm.",
                    "verification_status": "abstract_quote_matched",
                },
                {
                    "group": "methodology",
                    "field": "contributions",
                    "value": "unsupported claim",
                    "evidence_text": "A quote absent from the source.",
                    "verification_status": "abstract_quote_matched",
                },
            ]
        },
    }
    okf = build_paper_okf(record)
    assert [item["value"] for item in okf["verified_evidence"]] == [
        "GraphSAGE",
        "a sampling algorithm",
    ]


def test_source_metrics_and_abstract_quotes_stay_separate() -> None:
    record = {
        "kind": "paper",
        "record_key": "d" * 64,
        "title": "GraphSAGE",
        "source_name": "openalex",
        "source_url": "https://openalex.org/W123",
        "published_at": "2024-01-01",
        "content": "We propose GraphSAGE for node embeddings.",
        "metadata": {
            "openalex_id": "https://openalex.org/W123",
            "reference_count": 42,
            "keywords": ["Graph neural networks"],
            "source_timestamp": "2026-10-23T00:00:00Z",
            "first_author_metrics": {
                "author_id": "https://openalex.org/A123",
                "name": "Researcher",
                "h_index": 12,
                "i10_index": 8,
                "total_citations": 100,
                "publication_count": 20,
                "source_url": "https://openalex.org/A123",
                "source_timestamp": "2026-10-23T00:00:00Z",
            },
            "verified_extractions": [
                {
                    "group": "methodology",
                    "field": "techniques",
                    "value": "GraphSAGE",
                    "evidence_text": "We propose GraphSAGE for node embeddings.",
                    "verification_status": "abstract_quote_matched",
                    "json_pointer": "/content",
                    "section": "abstract",
                    "extraction_confidence": 0.8,
                    "extractor_version": "abstract-quote-slm-1.0.0",
                }
            ],
        },
    }
    params = build_paper_okf(record, "node embeddings")["parameters"]
    assert params["paper_identity"]["openalex_id"]["value"] == "https://openalex.org/W123"
    assert params["citation_metrics"]["reference_count"]["value"] == 42
    assert params["author_metrics"]["h_index"]["provenance"][0]["source_api"] == "openalex_authors"
    assert params["author_metrics"]["average_citations_per_publication"]["value"] == 5
    assert params["methodology"]["techniques"]["value"] == "GraphSAGE"
    assert params["methodology"]["techniques"]["provenance"][0]["pdf_page"] is None
    assert params["methodology"]["techniques"]["confidence"] == 0.8
    assert params["author_metrics"]["g_index"]["status"] == "unknown"
