"""Regression checks for concept matching and provider-backed reranking."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from archipelago.scholarly.contracts.okf_models import PaperIdentifiers, PaperRecord
from archipelago.scholarly.intelligence.extraction import extract_evidence
from archipelago.scholarly.intelligence.relevance_engine import evaluate_relevance
from archipelago.scholarly.intelligence.search import discover
from archipelago.scholarly.intelligence.semantic_rerank import (
    rerank_candidates,
    semantic_rank_cutoff,
)

pytestmark = pytest.mark.unit


def test_fine_tuning_concepts_match_inflected_wording() -> None:
    relevant = evaluate_relevance(
        "trustworthiness from fine tuning",
        "Privacy-Preserving and Trustworthy Fine-Tuning of Large Language Models",
        None,
    )
    unrelated = evaluate_relevance(
        "trustworthiness from fine tuning",
        "From inflation to a zero cosmological constant phase without fine tuning",
        None,
    )
    assert relevant["eligible"] is True
    assert unrelated["eligible"] is False


def test_semantic_acceptance_keeps_provider_evidence() -> None:
    class Provider:
        def discover_with_status(self, query: str, limit: int):
            papers = [
                PaperRecord(
                    paper_id="p1",
                    title="Reliable model adaptation under adversarial updates",
                    abstract="We evaluate whether model adaptation preserves safety and user confidence.",
                    identifiers=PaperIdentifiers(doi="10.1000/reliable-adaptation"),
                    publication_date="2025-01-01",
                ),
                PaperRecord(
                    paper_id="p2",
                    title="Coral reef biodiversity surveys",
                    abstract="We count fish species near marine reefs.",
                    identifiers=PaperIdentifiers(doi="10.1000/coral-survey"),
                    publication_date="2025-01-01",
                ),
            ]
            return [
                {"paper": paper, "source": "openalex", "citation_count": 0, "source_metadata": {}}
                for paper in papers
            ], [{"source": "openalex", "status": "live", "record_count": 2}]

    with patch(
        "archipelago.scholarly.intelligence.search.rerank_candidates",
        return_value=(
            {0: 4.0, 1: -2.0},
            {"status": "available", "model": "test", "control_baseline": -3.0},
        ),
    ):
        result = discover({"topic": "trustworthy fine tuning", "top_k": 10}, Provider())
    assert [paper["doi"] for paper in result["papers"]] == ["10.1000/reliable-adaptation"]


def test_semantic_rerank_requires_configured_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    scores, audit = rerank_candidates("test", [])
    assert scores == {}
    assert audit["status"] == "unavailable"
    assert semantic_rank_cutoff(scores) is None


def test_benchmark_performance_needs_named_benchmark_and_numeric_result() -> None:
    found = extract_evidence(
        "A model evaluation",
        "Our method achieves accuracy 92.1% on ImageNet. We also report F1 0.87 without a named dataset.",
        "https://example.org/paper",
    )
    assert found["benchmark_performance"][0]["name"] == "imagenet: accuracy 92.1%"
    assert len(found["benchmark_performance"]) == 1
