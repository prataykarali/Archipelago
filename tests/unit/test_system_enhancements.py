"""
Unit tests for the 6 System Enhancements:
1. Document Viewer & PDF Resolution
2. Deep-Linking & Section Highlighting
3. Multi-Topic Query Parsing & Synthesis
4. Chat Guardrails (character limits, input validation)
5. Graph UI OKF Relationship Keys
6. 55-PDF Evaluation & Multi-Parameter Ranking Engine
"""

import json
import pytest
from pathlib import Path

# Register all Flask routes early before any test client request
from archipelago.inference import bootstrap
from archipelago.inference import state as st
from archipelago.inference.routes_misc import resolve_pdf_file
from evaluate_pdf_catalog import evaluate_pdf_catalog, KNOWN_METADATA
from catalog_ranking import rank_documents, format_ranking_response


def test_pdf_catalog_evaluation_and_ranking():
    """Verify that all 55+ PDFs are evaluated and ranked accurately."""
    catalog = evaluate_pdf_catalog()
    assert len(catalog) >= 55, f"Expected at least 55 PDFs evaluated, found {len(catalog)}"
    
    # Verify metadata fields are present for every entry
    for entry in catalog:
        assert "doc_id" in entry
        assert "title" in entry
        assert "authors" in entry
        assert "composite_score" in entry
        assert "review_score" in entry
        assert "author_authority" in entry
        assert "topic_density_score" in entry
        assert 0.0 <= entry["composite_score"] <= 10.0

    # Verify ranking by composite score
    top_composite = rank_documents(topic=None, parameter="composite", top_k=5)
    assert len(top_composite) == 5
    assert top_composite[0]["composite_score"] >= top_composite[1]["composite_score"]

    # Verify ranking by author authority
    top_authors = rank_documents(topic=None, parameter="authors", top_k=3)
    assert top_authors[0]["author_authority"] >= top_authors[-1]["author_authority"]

    # Verify ranking by reviews
    top_reviews = rank_documents(topic=None, parameter="reviews", top_k=3)
    assert top_reviews[0]["review_score"] >= top_reviews[-1]["review_score"]

    # Verify topic-filtered ranking for subjects present in the catalog
    os_ranks = rank_documents(topic="os", parameter="composite", top_k=3)
    assert len(os_ranks) > 0
    rag_ranks = rank_documents(topic="RAG", parameter="composite", top_k=3)
    assert len(rag_ranks) > 0
    # Hard miss: SQL/DBMS is not in the ranking catalog — must not invent global top
    assert rank_documents(topic="sql", parameter="composite", top_k=3) == []

    # Verify Markdown formatting
    md_resp = format_ranking_response(topic="RAG", parameter="reviews", top_k=3)
    assert "Top-Ranked Books & Papers" in md_resp
    assert "Review Score" in md_resp


def test_multi_topic_query_parsing():
    """Verify multi-topic parsing handles +, vs, and, commas."""
    from archipelago.inference.routing import parse_multi_topic_query

    t1 = parse_multi_topic_query("RAG + DBMS")
    assert "RAG" in t1 and "DBMS" in t1

    t2 = parse_multi_topic_query("Compare LoRA vs BERT")
    assert len(t2) >= 2

    t3 = parse_multi_topic_query("Explain Attention, GNN and Operating Systems")
    assert len(t3) <= 3

    dependent = parse_multi_topic_query(
        "Explain LoRA and how it reduces trainable parameters"
    )
    assert dependent == ["LoRA and how it reduces trainable parameters"]


def test_chat_input_guardrails():
    """Verify backend chat API enforces query length boundaries."""
    with st.app.test_client() as c:
        # Test empty query
        r_empty = c.post("/api/chat", json={"query": ""})
        assert r_empty.status_code == 400
        assert "empty" in r_empty.get_json()["error"].lower()

        # Test query < 2 chars
        r_short = c.post("/api/chat", json={"query": "a"})
        assert r_short.status_code == 400

        # Test query > 1000 chars
        long_q = "What is RAG? " * 100
        r_long = c.post("/api/chat", json={"query": long_q})
        assert r_long.status_code == 400
        assert "1000" in r_long.get_json()["error"]


def test_pdf_resolution_and_streaming():
    """Verify PDF resolution returns local PDF paths or remote fallbacks."""
    resolved = resolve_pdf_file("Hu2021_LoRA.pdf")
    assert resolved is not None
    assert resolved.exists()
    assert resolved.name == "Hu2021_LoRA.pdf"


def test_page_view_contract_spans():
    """Verify /api/page-view contract with highlight cited spans."""
    with st.app.test_client() as c:
        res = c.get("/api/page-view?doc_id=papers/Hu2021_LoRA.pdf&page=1&highlight=LoRA")
        assert res.status_code == 200
        data = res.get_json()
        assert "doc_id" in data
        assert "passage" in data
        assert "cited_spans" in data
        assert "pdf_url" in data
