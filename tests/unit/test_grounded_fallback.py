"""Unit tests for false-OOS detection and benchmark grounded cards."""
from __future__ import annotations

from archipelago.inference.grounded_fallback import (
    build_benchmark_grounded_answer,
    clean_weird_symbols,
    is_false_out_of_scope_refusal,
    looks_garbled_or_template_leaky,
    true_out_of_scope_message,
)


def test_detects_false_oos_banner() -> None:
    text = (
        "That topic falls outside the current scope of this library assistant. "
        "Indexed domains: Vector RAG, GraphRAG."
    )
    assert is_false_out_of_scope_refusal(text) is True


def test_real_answer_not_flagged() -> None:
    text = (
        "Vector RAG retrieves passages with a dense index and augments the LLM "
        "prompt for grounded generation [1: Edge2024_GraphRAG.pdf, p.2 ↗]."
    )
    assert is_false_out_of_scope_refusal(text) is False


def test_clean_weird_symbols_strips_controls_and_style_labels() -> None:
    dirty = "LoRA\ufb01ne-tuning\u200b  Style 12:  LAYOUT #3/100  [END]\n:\nworks"
    clean = clean_weird_symbols(dirty)
    assert "\u200b" not in clean
    assert "Style 12" not in clean
    assert "LAYOUT" not in clean
    assert "[END]" not in clean
    assert "fine-tuning" in clean or "LoRAfine" in clean or "LoRA" in clean


def test_benchmark_card_has_topology_and_citations() -> None:
    card = build_benchmark_grounded_answer(
        query="How are vector indices used in RAG?",
        anchor_id="vector_rag",
        anchor_name="Vector RAG",
        anchor_summary="Dense vector retrieval augments generation.",
        prerequisites=[{"id": "retrieval", "name": "Retrieval"}],
        unlocks=[{"id": "graph_rag", "name": "GraphRAG"}],
        chunks=[
            {
                "doc_id": "papers/Edge2024_GraphRAG.pdf",
                "chunk_id": "chunk_006",
                "page_number": 2,
                "text_passage": "Vector RAG uses an embedding index over the corpus.",
            }
        ],
    )
    lower = card.lower()
    assert "vector rag" in lower
    assert "okf graph traversal topology" in lower
    assert "requires (prerequisites)" in lower
    assert "graphrag" in lower
    assert "cited resources" in lower
    assert "edge2024_graphrag.pdf" in lower
    assert "falls outside" not in lower


def test_true_oos_message_lists_pilot_domains() -> None:
    msg = true_out_of_scope_message().lower()
    assert "outside the current scope" in msg
    assert "rag" in msg
    assert "database" in msg


def test_strips_template_section_headers() -> None:
    raw = (
        "### 1. Direct Technical Opening\n"
        "Vector RAG uses a dense index [1: Edge2024_GraphRAG.pdf, p.2 ↗].\n\n"
        "### 4. OKF Graph Traversal Topology Card\n"
        "Requires Prerequisites: Retrieval\n"
        "Target Concept: Vector RAG\n"
    )
    clean = clean_weird_symbols(raw)
    assert "Direct Technical Opening" not in clean
    assert "### 1" not in clean
    assert "Requires (Prerequisites):" in clean
    assert "Vector RAG uses a dense index" in clean


def test_garbled_fragments_flagged() -> None:
    bad = (
        "In RAG frameworks, generation modelsine content retrieved frultiple "
        "documents across vector spaces [1: x.pdf, p.1 ↗]."
    )
    assert looks_garbled_or_template_leaky(bad) is True


def test_letter_drop_and_fused_unity_flagged() -> None:
    bad = (
        "The mechanism typically operates byparing vector representations or "
        "token-level retrieval tndition the generation posterior. Models canine "
        "content across blocks and hierarchicalunity summaries [1: x.pdf, p.1 ↗]."
    )
    assert looks_garbled_or_template_leaky(bad) is True
    clean = (
        "Vector RAG retrieves passages with a dense index and conditions "
        "generation on those passages [1: Edge2024_GraphRAG.pdf, p.2 ↗]."
    )
    assert looks_garbled_or_template_leaky(clean) is False
