from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

pytestmark = pytest.mark.unit


def test_library_payload_restores_catalog_and_huggingface_shelves():
    from archipelago.inference.library_catalog_api import build_library_data_payload

    payload = build_library_data_payload(Path(__file__).parents[2])

    assert payload["total_ebooks"] >= 140
    assert payload["total_pearson_books"] >= 40
    assert len(payload["hf_resources"]) >= 50
    assert len(payload["holdings"]) >= 100

    lora = next(
        item for item in payload["ebook_shelf"] if Path(str(item["id"])).name == "Hu2021_LoRA.pdf"
    )
    assert lora["resolveUrl"].endswith("Hu2021_LoRA.pdf")


def test_pearson_reader_urls_keep_query_parameters_and_book_id():
    from archipelago.resolver.pearson import build_reader_url

    url = build_reader_url("4268f15e-ac2c-40dd-bd12-aca2f02dd0ae", page=340)
    parsed = urlsplit(url)

    assert parse_qs(parsed.query)["subscriptionId"]
    assert parsed.fragment == "book/4268f15e-ac2c-40dd-bd12-aca2f02dd0ae"


@pytest.mark.parametrize(
    ("query", "route"),
    [
        ("What is Low-Rank Adaptation (LoRA)?", "graph_strong"),
        ("Explain the main components of retrieval augmented generation (RAG)", "graph_strong"),
        ("What are the prerequisites for BERT model training?", "graph_strong"),
        ("How does the Attention mechanism handle sequence alignment?", "graph_strong"),
        ("How do DBMS buffer pools optimize query retrieval in Silberschatz?", "graph_strong"),
        ("Explain virtual memory paging vs segmentation in OSTEP.", "graph_strong"),
        ("How does GraphRAG combine graph databases with RAG synthesis?", "graph_strong"),
        (
            "Rank the most critical PEFT and RAG papers in the corpus by contribution.",
            "graph_strong",
        ),
        ("What are the library hours and weekend issue rules?", "library_hours"),
        ("What e-resource portals does the central library provide?", "library_resources"),
        ("How do I access Pearson eLibrary textbooks?", "library_resources"),
        ("Suggest books on operating systems", "library_books"),
        ("RAG + DBMS", "graph_strong"),
        ("LoRA vs BERT", "graph_strong"),
    ],
)
def test_every_suggested_chat_query_has_a_supported_route(query: str, route: str):
    from archipelago.inference.routing import _resolve_query_routing

    routing = _resolve_query_routing(query)

    assert routing["route"] == route


def test_demo_citations_keep_pearson_page_number_without_fake_deep_link():
    from archipelago.inference.demo_query_books import merge_demo_citations

    citations = merge_demo_citations("How do DBMS buffer managers work?", [])
    pearson = next(
        citation
        for citation in citations
        if citation["doc_id"] == "4268f15e-ac2c-40dd-bd12-aca2f02dd0ae"
    )

    assert pearson["page_number"] == 1
    assert "#book/4268f15e-ac2c-40dd-bd12-aca2f02dd0ae" in pearson["page_url"]
    assert "/page/1" not in pearson["page_url"]
