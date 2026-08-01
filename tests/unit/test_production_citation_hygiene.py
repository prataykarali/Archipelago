"""Production ban: no doc_id lineage or bare p.N ↗ spam in user-facing text."""
from __future__ import annotations

import pytest

from archipelago.inference.citations import render_citation_from_payload
from archipelago.inference.grounded_fallback import build_benchmark_grounded_answer
from archipelago.inference.sanitizer import sanitize_stream_final, strip_production_leaks

pytestmark = pytest.mark.unit


def test_strip_production_leaks_removes_doc_id_lineage():
    dirty = (
        "GraphRAG builds communities [doc_id: Edge2024_GraphRAG.pdf -> chunk_006 -> page 2] "
        "and more text."
    )
    clean = strip_production_leaks(dirty)
    assert "doc_id:" not in clean
    assert "chunk_006" not in clean
    assert "GraphRAG" in clean


def test_strip_production_leaks_removes_page_arrow_spam():
    dirty = "Vector RAG fails globally (p.2 ↗ p.6 ↗ p.8 ↗ p.4 ↗) while GraphRAG helps."
    clean = strip_production_leaks(dirty)
    assert "↗" not in clean
    assert "p.2" not in clean
    assert "GraphRAG" in clean


def test_strip_production_leaks_removes_linked_page_chip_and_legacy_lineage():
    dirty = (
        "Flat search [p.2 ↗](/api/page-view?doc_id=Edge.pdf&page=2) "
        "[Edge2024_GraphRAG.pdf: papers/Edge2024_GraphRAG.pdf_chunk_006 -> page 2] "
        "while GraphRAG aggregates communities [S1](/api/page-view?doc_id=Edge.pdf&page=2)."
    )
    clean = strip_production_leaks(dirty)
    assert "p.2 ↗" not in clean
    assert "chunk_006" not in clean
    assert "-> page 2" not in clean
    assert "[S1](/api/page-view" in clean


def test_strip_production_leaks_removes_live_raw_source_lines():
    dirty = (
        "GraphRAG aggregates community summaries [S1].\n\n"
        "Source Citations:\n"
        " papers/Edge2024_GraphRAG.pdf_chunk_030, page 8\n"
        " papers/Edge2024_GraphRAG.pdf_chunk_006, page 2"
    )
    clean = strip_production_leaks(dirty)
    assert "chunk_030" not in clean
    assert "chunk_006" not in clean
    assert "Source Citations:" not in clean
    assert clean == "GraphRAG aggregates community summaries [S1]."


def test_sanitize_stream_final_runs_production_strip():
    dirty = "Answer [doc_id: x.pdf -> chunk_001 -> page 1] p.3 ↗ done."
    clean = sanitize_stream_final(dirty)
    assert "doc_id:" not in clean
    assert "↗" not in clean


def test_grounded_fallback_uses_s_tags_only():
    text = build_benchmark_grounded_answer(
        query="Compare Vector RAG vs GraphRAG",
        anchor_id="graph_rag",
        anchor_name="Graph RAG",
        anchor_summary="Entity graph retrieval.",
        prerequisites=[{"name": "Dense Embeddings"}],
        unlocks=[{"name": "Global Sensemaking"}],
        chunks=[{
            "doc_id": "papers/Edge2024_GraphRAG.pdf",
            "chunk_id": "chunk_006",
            "page_number": 2,
            "text_passage": "Community summaries support global queries.",
        }],
    )
    assert "[S1]" in text
    assert "doc_id:" not in text
    assert "↗" not in text
    assert "chunk_006" not in text
    assert "Source Citations:" in text or "OKF Graph" in text


def test_render_citation_payload_label_is_s_tag_not_page_arrow():
    link = render_citation_from_payload({
        "evidence_id": "S1",
        "doc_id": "papers/Edge2024_GraphRAG.pdf",
        "page_number": 2,
        "topic": "GraphRAG",
    })
    assert "S1" in link
    assert "↗" not in link
    assert "page-view" in link or "page=" in link
