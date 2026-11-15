"""Targeted regressions for security hardening, source-to-chat routing, and librarian UX."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST_INF = ROOT / "host_inference"
HOST_RES = ROOT / "host_research"

if str(HOST_INF) not in sys.path:
    sys.path.insert(0, str(HOST_INF))

from engine import Engine  # noqa: E402
from engine.diagnostics import diagnostic_payload  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def hosted_engine():
    return Engine()


def test_agi_and_pagerank_route_to_general_explanation(hosted_engine):
    for query in ("What is AGI?", "Explain artificial general intelligence.", "Explain PageRank."):
        res = hosted_engine.answer(query)
        assert res["route"] == "GENERAL_EXPLANATION"


def test_institutional_eresources_and_opac_routing(hosted_engine):
    for query in (
        "What are the e-resources?",
        "Where can I access the e-books?",
        "Give me the OPAC link.",
    ):
        res = hosted_engine.answer(query)
        assert res["route"] == "LIBRARY_LOOKUP"
        assert "uemk-opac.l2c2.co.in" in res["text"]
        assert "ebooks.elibrary.in.pearson.com" in res["text"]


def test_catalog_books_and_kv_papers_routing(hosted_engine):
    os_books = hosted_engine.answer("Show me books about operating systems.")
    assert os_books["route"] == "LIBRARY_LOOKUP"
    assert "Verified books" in os_books["text"]

    kv_papers = hosted_engine.answer("Show me papers about KV caching.")
    assert kv_papers["route"] == "RESEARCH_TOPIC"
    assert "Kwon2023" in kv_papers["text"]


def test_unindexed_hessian_diagnostic_does_not_fallback_to_convolution(hosted_engine):
    payload = diagnostic_payload(hosted_engine, "hessian_matrix")
    assert payload["available"] is False
    assert payload["success"] is False
    assert payload["target_concept"] == "hessian_matrix"
    assert payload["mcqs"] == []


def test_textbooks_pdf_quarantined_in_cite_record(hosted_engine):
    hosted_engine.graph.nodes["_quarantine_test"] = {
        "label": "Quarantine Test",
        "evidence": [{"doc_id": "textbooks/missing_book.pdf", "page": 42}],
    }
    try:
        rec = hosted_engine.graph.cite_record("_quarantine_test", "Quarantine Test", 1)
        assert rec["pdf_url"] == ""
        assert rec["page_number"] is None
        assert rec["access_status"] == "Unavailable"
        assert rec["source_type"] == "metadata_only"
    finally:
        hosted_engine.graph.nodes.pop("_quarantine_test", None)


def test_host_inference_csp_allows_katex_cdn():
    os.environ.setdefault("SUPABASE_URL", "https://spllaastefjwclllfndp.supabase.co")
    os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-key")
    os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret")
    from hostapp.factory import create_app

    app = create_app()
    resp = app.test_client().get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "https://cdn.jsdelivr.net" in csp


def test_host_research_csp_and_rbac():
    os.environ.setdefault("SUPABASE_URL", "https://spllaastefjwclllfndp.supabase.co")
    os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-key")
    os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret")
    if str(HOST_RES) not in sys.path:
        sys.path.insert(0, str(HOST_RES))
    import app as research_app

    client = research_app.app.test_client()
    resp = client.get("/librarian")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "object-src 'none'" in csp
    assert client.get("/api/librarian/overview").status_code == 401


def test_librarian_and_graph_ux_structure():
    lib_html = (HOST_RES / "ui" / "librarian.html").read_text(encoding="utf-8")
    assert 'id="traffic-body" hidden' in lib_html
    assert 'class="secondary-drawer"' in lib_html

    graph_html = (HOST_RES / "ui" / "academic_graph.html").read_text(encoding="utf-8")
    assert 'id="domain-filter"' in graph_html
    assert 'id="advanced-filters"' in graph_html
    assert 'id="clear-filters"' in graph_html
    assert ".graph-toolbar { position: relative;" in graph_html
