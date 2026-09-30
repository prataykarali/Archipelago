"""Unit tests for SynthesisService, citation retention, and topic suggestions."""
from __future__ import annotations

import pytest
from src.core.synthesis_service import SynthesisService


@pytest.fixture
def service():
    return SynthesisService(synthesis_model="qwen3.5:0.8b")


def test_topic_suggestions_formatting(service):
    candidates = [
        {
            "id": "attention_mechanism",
            "name": "Attention Mechanism",
            "difficulty": "foundational",
            "summary": "Soft token alignment.",
            "prerequisites": ["Linear Algebra"],
            "unlocks": ["Transformer"],
        },
        {
            "id": "multi_head_attention",
            "name": "Multi-Head Attention",
            "difficulty": "intermediate",
            "summary": "Parallel attention projections.",
            "prerequisites": ["Attention Mechanism"],
            "unlocks": ["Transformer"],
        },
    ]
    res = service.generate_topic_suggestions("attentn", candidates)
    assert res["type"] == "TOPIC_SUGGESTION"
    assert "attentn" in res["message"]
    assert len(res["suggestions"]) == 2
    assert res["suggestions"][0]["name"] == "Attention Mechanism"
    assert "display_roadmap" in res["suggestions"][0]


def test_diagnostic_mcq_generation(service):
    prereqs = [{"name": "Linear Algebra"}, {"name": "Matrix Calculus"}]
    quiz = service.generate_diagnostic_mcq("Singular Value Decomposition", prereqs)
    assert quiz["type"] == "MCQ_DIAGNOSTIC"
    assert quiz["target_concept"] == "Singular Value Decomposition"
    assert len(quiz["questions"]) >= 2
    q1 = quiz["questions"][0]
    assert "A" in q1["options"]
    assert "B" in q1["options"]
    assert "C" in q1["options"]
    assert "D" in q1["options"]
    assert q1["correct_option"] == "A"


def test_grounded_fallback_offline(service):
    payload = {
        "anchor_concept": "Low-Rank Adaptation",
        "topological_summary": "REQUIRES: Linear Algebra -> UNLOCKS: QLoRA",
        "citation_lineage": [
            {"badge": "S1", "doc_title": "Hu2021_LoRA.pdf", "page_number": 2},
        ],
        "system_prompt": "Test system prompt",
        "user_prompt": "Test user prompt",
    }
    # Direct test of grounded fallback
    out = service._grounded_fallback(
        payload["anchor_concept"],
        payload["topological_summary"],
        payload["citation_lineage"],
    )
    assert "Low-Rank Adaptation" in out
    assert "[S1]" in out
    assert "Hu2021_LoRA.pdf" in out
