"""Benchmark-style grounded answers (no LLM rewrite, clean structure)."""
from __future__ import annotations

import pytest

from archipelago.inference.grounded_answers import (
    _benchmark_concept_card,
    render_grounded_answer,
)

pytestmark = pytest.mark.unit


def test_benchmark_concept_card_has_definition_and_sections() -> None:
    ctx = {
        "name": "Retrieval-Augmented Generation",
        "summary": (
            "RAG combines retrieval of relevant documents from an external "
            "knowledge source with generation."
        ),
        "cite": "[p.4 ↗](/api/page-view?doc_id=Lewis2020_RAG.pdf&page=4)",
        "prereqs": ["Dense retrieval [p.1 ↗](/api/page-view?doc_id=a.pdf&page=1)"],
        "unlocks": ["Grounded generation"],
        "path_section": "",
        "closer": "Open a citation link to read the indexed passage.",
    }
    text = _benchmark_concept_card(ctx)
    assert text.startswith("### Retrieval-Augmented Generation")
    assert "**Definition.**" in text
    assert "**Learn first**" in text
    assert "**Then explore**" in text
    assert "**Cited resources.**" in text
    assert text.count("/api/page-view") <= 4


def test_render_grounded_rebuilds_learning_path_chip_flood() -> None:
    """Legacy Learning-Path chip rows are rebuilt into a clean card."""
    target = {
        "id": "rag",
        "label": "RAG",
        "name": "RAG",
        "summary": (
            "Retrieval-Augmented Generation combines retrieval of relevant "
            "documents from an external knowledge source and generation."
        ),
    }
    citation_map = {
        "rag": [
            {
                "doc_id": "Lewis2020_RAG.pdf",
                "page_number": 4,
                "section_title": "RAG",
                "evidence_id": "S1",
            },
            {
                "doc_id": "Lewis2020_RAG.pdf",
                "page_number": 6,
                "section_title": "",
                "evidence_id": "S2",
            },
            {
                "doc_id": "other.pdf",
                "page_number": 1,
                "section_title": "",
                "evidence_id": "S3",
            },
            {
                "doc_id": "other.pdf",
                "page_number": 2,
                "section_title": "",
                "evidence_id": "S4",
            },
        ],
    }
    out = render_grounded_answer(
        "hi tell me about RAG",
        target,
        prereqs=[{"id": "emb", "label": "Embeddings", "summary": "Vector spaces."}],
        unlocks=[{"id": "gen", "label": "Grounded generation", "summary": "Use context."}],
        citation_map=citation_map,
    )
    assert out.startswith("### ")
    assert "**Definition.**" in out
    assert "Retrieval-Augmented" in out or "RAG" in out
    # Body must not dump 8+ page chips on one Learning Path line.
    assert out.count("/api/page-view") <= 6
    assert "Learning Path:" not in out
