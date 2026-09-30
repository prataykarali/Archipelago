from __future__ import annotations

from pathlib import Path

from archipelago.inference.demo_query_books import (
    books_for_query,
    citation_overlays_for_query,
    enrich_reply_with_books,
    match_demo_query_key,
    merge_demo_citations,
    resolve_doc_id,
)
from archipelago.inference.math_text import fix_math_expressions
from archipelago.inference.corpus_inventory import inventory_for_books

QUERIES = [
    "What is Low-Rank Adaptation (LoRA)?",
    "Explain the main components of RAG",
    "What are the prerequisites for BERT?",
    "How does the Attention mechanism work?",
    "DBMS buffer pools in Silberschatz",
    "Virtual memory paging vs segmentation",
    "GraphRAG: graph + RAG synthesis",
    "Rank top PEFT & RAG papers",
    "Multi-topic: RAG + DBMS",
    "Compare LoRA vs BERT",
]


def test_all_ten_demo_queries_match() -> None:
    for q in QUERIES:
        assert match_demo_query_key(q), q
        assert books_for_query(q), q


def test_enrich_appends_table_links_and_book_name() -> None:
    text = enrich_reply_with_books("What is Low-Rank Adaptation (LoRA)?", "LoRA freezes W0.")
    assert "LoRA: Low-Rank Adaptation" in text
    # The Koha export has no LoRA holding, so do not invent physical copies.
    assert "Koha catalogue matches" not in text
    assert "Simulated inventory" not in text
    assert "/api/page-view?doc_id=" in text
    assert "Open source pages" in text


def test_chat_inventory_only_reports_verified_koha_rows() -> None:
    matched = inventory_for_books([{"book_title": "Journal of human resource management"}])[0]
    assert matched["koha_record_verified"] is True
    assert matched["total_copies"] >= matched["available_copies"] >= 0
    assert "accession" in matched
    assert "shelf_location" not in matched
    unmatched = inventory_for_books([{"book_title": "A title absent from the Koha export"}])[0]
    assert not unmatched.get("koha_record_verified")
    assert "total_copies" not in unmatched
    assert "available_copies" not in unmatched


def test_lewis_resolves_to_real_pdf() -> None:
    assert resolve_doc_id("lewis2020_rag") == "papers/Lewis2020_RAG.pdf"
    path = Path("pdfs") / "papers" / "Lewis2020_RAG.pdf"
    assert path.is_file()


def test_overlays_have_page_urls() -> None:
    overlays = citation_overlays_for_query("Explain the main components of RAG")
    assert overlays
    assert "Lewis2020_RAG" in overlays[0]["doc_id"]
    assert overlays[0]["page_url"].startswith("/api/page-view")
    assert overlays[0]["summary"]


def test_merge_citations_titles() -> None:
    merged = merge_demo_citations("Compare LoRA vs BERT", [])
    assert any("LoRA" in str(c.get("title")) for c in merged)
    assert any("BERT" in str(c.get("title")) for c in merged)


def test_math_plain() -> None:
    out = fix_math_expressions(r"W = W_0 + B \\cdot A")
    assert "·" in out or "cdot" not in out
