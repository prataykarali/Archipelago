"""Source-link integrity: every book, paper, and dataset resolves to an EXACT page.

These tests are the regression gate for docs/01 §5 ("Direct Source Links —
NON-NEGOTIABLE"): a rendered link must never degrade to a generic homepage
while an exact verified page exists, and no URL may be fabricated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archipelago.inference.citations import (
    _resolve_printed_page,
    build_citation_link,
    citation_payload,
    render_citation_from_payload,
)
from archipelago.inference.library_catalog_api import build_library_data_payload
from archipelago.resolver.pearson import (
    _load_pearson_catalog,
    build_reader_url,
    resolve,
    resolve_pearson_url,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
HF_BLOB_PREFIX = "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/"
HF_REPO_ROOT = "https://huggingface.co/datasets/Prataykarali/Library_books"
PEARSON_READER_PREFIX = "https://ebooks.elibrary.in.pearson.com/wr/"
PEARSON_PORTAL = "https://elibrary.in.pearson.com/"
MIN_PAGE = 1
MAX_PAGE = 500


@pytest.fixture(scope="module")
def pearson_catalog() -> list[dict]:
    books = _load_pearson_catalog()
    assert books, "pearson_bookshelf.json must contain the institutional catalog"
    return books


@pytest.fixture(scope="module")
def library_payload() -> dict:
    return build_library_data_payload(REPO_ROOT)


# ── Pearson: exact reader page for every catalog title ────────────────────────


def test_every_pearson_book_resolves_to_exact_reader_url(pearson_catalog):
    """All 40 institutional titles must resolve to a #book/{uuid} reader page."""
    unresolved = [
        b.get("id") for b in pearson_catalog if not resolve(str(b.get("id")), page=MIN_PAGE)
    ]
    assert not unresolved, f"Pearson books without an exact reader URL: {unresolved}"


def test_pearson_reader_urls_carry_book_uuid_and_page(pearson_catalog):
    """Reader URLs must be page-anchored and book-specific, not the portal."""
    for book in pearson_catalog:
        url = resolve(str(book.get("id")), page=MAX_PAGE)
        assert url is not None, book.get("title")
        assert url.startswith(PEARSON_READER_PREFIX), f"{book.get('title')}: {url}"
        assert "#book/" in url, f"{book.get('title')} missing #book fragment: {url}"
        assert f"/page/{MAX_PAGE}" in url, f"{book.get('title')} missing page anchor: {url}"
        assert PEARSON_PORTAL not in url, f"{book.get('title')} degraded to portal: {url}"


def test_pearson_catalog_entries_expose_exact_reader_url(pearson_catalog):
    """build_reader_url keeps the catalog viewer and subscription per title."""
    for book in pearson_catalog[:10]:
        url = build_reader_url(book, page=7)
        assert "#book/" in url
        assert "/page/7" in url
        assert str(book.get("id")) in url, f"wrong book id for {book.get('title')}: {url}"


def test_unmatched_pearson_lookup_is_flagged_not_fabricated():
    """An unknown title must report not-found rather than invent a working URL."""
    result = resolve_pearson_url(title="Zzzz Not A Real Book Title Xyzzy 42")
    assert result["working"] is False
    assert result["verified"] is False
    assert result["error_code"] == "PEARSON_NOT_FOUND"


def test_non_pearson_identifier_returns_no_pearson_url():
    """A Hugging Face paper must not be handed a Pearson reader URL."""
    assert resolve("papers/Hu2021_LoRA.pdf", page=1) is None


# ── Hugging Face: exact dataset file page, never the repo root ───────────────


def test_hf_resources_use_exact_per_file_pages(library_payload):
    """Every HF shelf entry points at its own file page, not the dataset root."""
    hf_entries = [
        b for b in library_payload["ebook_shelf"] if "huggingface.co" in str(b.get("pdfUrl", ""))
    ]
    assert hf_entries, "expected indexed Hugging Face resources"
    for entry in hf_entries:
        url = entry["pdfUrl"]
        assert url.startswith(HF_BLOB_PREFIX), f"not an exact file page: {url}"
        assert url != HF_REPO_ROOT, "HF entry degraded to the dataset homepage"
        assert url.rstrip("/") != HF_REPO_ROOT, "HF entry degraded to the dataset homepage"
        # The file segment must name a real path, not just the repo.
        assert url[len(HF_BLOB_PREFIX) :], f"HF entry has no file path: {url}"


def test_hf_resources_expose_direct_download_url(library_payload):
    """Each HF entry also exposes a resolve/ download URL for the same file."""
    hf_entries = [
        b for b in library_payload["ebook_shelf"] if "huggingface.co" in str(b.get("pdfUrl", ""))
    ]
    for entry in hf_entries:
        assert "/resolve/main/" in str(entry.get("resolveUrl", "")), entry.get("id")


def test_no_shelf_entry_links_a_bare_portal_or_repo_homepage(library_payload):
    """No rendered shelf link may be just a portal/repo root."""
    bare = ("https://elibrary.in.pearson.com", HF_REPO_ROOT)
    offenders = [
        (b.get("id"), b.get("pdfUrl"))
        for b in library_payload["ebook_shelf"]
        if any(str(b.get("pdfUrl", "")).rstrip("/") == root for root in bare)
    ]
    assert not offenders, f"generic homepage links rendered: {offenders}"


# ── Prominent e-books: title must match the document it links to ──────────────


def test_prominent_ebooks_link_to_their_own_document(library_payload):
    """Guard against a book title pointing at an unrelated file."""
    by_id = {b.get("id"): b for b in library_payload["ebook_shelf"]}
    expectations = {
        "paper_attention_is_all_you_need_2017": "Vaswani2017_Attention_Is_All_You_Need.pdf",
        "book_math_for_machine_learning_2020": "Deisenroth_Math_For_ML.pdf",
    }
    for book_id, expected_file in expectations.items():
        entry = by_id.get(book_id)
        assert entry is not None, f"{book_id} missing from the shelf"
        assert expected_file in entry["pdfUrl"], (
            f"{book_id} points at the wrong document: {entry['pdfUrl']}"
        )


def test_generative_adversarial_nets_is_labelled_as_the_gan_paper(library_payload):
    """The GAN PDF must not be presented as the 'Deep Learning' textbook."""
    by_id = {b.get("id"): b for b in library_payload["ebook_shelf"]}
    gan = by_id.get("paper_goodfellow_2014_gan")
    assert gan is not None
    assert gan["title"] == "Generative Adversarial Nets"
    assert "Goodfellow2014_GAN.pdf" in gan["pdfUrl"]
    # No entry may claim the 2016 textbook while linking the 2014 GAN paper.
    for entry in library_payload["ebook_shelf"]:
        if "Goodfellow2014_GAN.pdf" in str(entry.get("pdfUrl", "")):
            assert entry.get("year") != "2016", (
                "GAN paper is dated as the 2016 Deep Learning textbook"
            )


# ── Page links: encoded doc id, page anchor, and printed-page mapping ─────────


def test_page_view_link_is_encoded_and_page_anchored():
    payload = citation_payload(
        {"doc_id": "papers/Hu2021_LoRA.pdf", "page_number": 3, "text": "rank decomposition"},
        "LoRA",
    )
    assert payload["url"] == "/api/page-view?doc_id=papers%2FHu2021_LoRA.pdf&page=3#page=3"
    assert payload["page_number"] == 3
    # The slash in the doc id must be percent-encoded or the query breaks.
    assert "papers/Hu2021" not in payload["url"]


def test_rendered_citation_contains_a_clickable_page_link():
    payload = citation_payload(
        {"doc_id": "papers/Hu2021_LoRA.pdf", "page_number": 5, "text": "x"},
        "LoRA",
        evidence_id="S1",
    )
    rendered = render_citation_from_payload(payload)
    assert "[S1:" in rendered
    assert "](/api/page-view?" in rendered
    assert "#page=5" in rendered


def test_printed_page_label_resolves_from_page_label_map():
    evidence = {"page_number": 3, "page_label_map": {"1": 3, "2": 4}}
    assert _resolve_printed_page(evidence) == "1"
    # An unmapped page must stay unresolved rather than guess a label.
    assert _resolve_printed_page({"page_number": 99, "page_label_map": {"1": 3}}) is None
    assert _resolve_printed_page({"page_number": 3}) is None


def test_build_citation_link_anchors_the_requested_page():
    url = build_citation_link(
        {"doc_id": "papers/Hu2021_LoRA.pdf", "page_number": 7}, {"title": "LoRA"}
    )
    assert "#page=7" in url
    assert "papers%2FHu2021_LoRA.pdf" in url


# ── Institutional portals: exact, not generic ────────────────────────────────


def test_institutional_portal_urls_are_exact(library_payload):
    assert library_payload["opac_url"] == "https://uemk-opac.l2c2.co.in"
    assert library_payload["credentials"]["pearson_portal"] == "https://elibrary.in.pearson.com/"


def test_landing_page_keeps_exact_institutional_links():
    landing = (REPO_ROOT / "ui" / "chat" / "landing.html").read_text(encoding="utf-8")
    assert "https://iemcrp.com/" in landing
    assert "uemk-opac.l2c2.co.in" in landing


def test_library_stats_are_computed_from_data_not_hardcoded(library_payload):
    """Docs/01 §6: statistics must derive from the authoritative data layer."""
    shelf = library_payload["ebook_shelf"]
    assert library_payload["total_ebooks"] == len(shelf)
    assert library_payload["total_papers"] == len([b for b in shelf if b.get("isPaper")])
    assert library_payload["total_pearson_books"] == library_payload["pearson_books"].__len__()
    assert library_payload["holdings_stats"]["total_records"] == len(library_payload["holdings"])


# ── Pearson canonical reader URLs (exact book + page + pinned version) ──────


def test_pearson_reader_url_pins_the_reader_version(pearson_catalog):
    """Catalog reader URLs must carry the pinned version, not rely on browser JS."""
    from archipelago.resolver.pearson import PEARSON_READER_VERSION, resolve_pearson_url

    for book in pearson_catalog[:12]:
        result = resolve_pearson_url(book_id=str(book.get("id")), title=book.get("title"))
        url = result["url"]
        assert f"version={PEARSON_READER_VERSION}" in url, (
            f"{book.get('title')} missing version: {url}"
        )


def test_build_reader_url_keeps_version_and_page(pearson_catalog):
    from archipelago.resolver.pearson import PEARSON_READER_VERSION, build_reader_url

    for book in pearson_catalog[:12]:
        url = build_reader_url(book, page=17)
        assert f"version={PEARSON_READER_VERSION}" in url
        assert "/page/17" in url
        assert str(book.get("id")) in url


# ── Citations expose the exact Hugging Face dataset file page ───────────────


def test_citation_payload_exposes_exact_hf_dataset_page():
    """A citation from an indexed PDF must link to its exact dataset file page."""
    payload = citation_payload(
        {
            "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            "page_number": 3,
            "text": "self attention",
            "doc_title": "Attention Is All You Need",
        },
        "Attention",
    )
    assert payload["source_dataset"] == "huggingface"
    hf_url = payload["hf_url"]
    assert hf_url.startswith(HF_BLOB_PREFIX)
    assert "Vaswani2017_Attention_Is_All_You_Need.pdf" in hf_url
    # Never the dataset homepage.
    assert hf_url.rstrip("/") != HF_REPO_ROOT


def test_citation_payload_keeps_page_precise_reader_link():
    """The internal reader link stays page-anchored alongside the dataset page."""
    payload = citation_payload(
        {"doc_id": "papers/Hu2021_LoRA.pdf", "page_number": 7, "text": "x"}, "LoRA"
    )
    assert payload["url"].endswith("&page=7#page=7")
    assert payload["hf_url"].endswith(".pdf")


def test_non_pdf_citation_has_no_hf_link():
    payload = citation_payload({"doc_id": "chapters/notes.md", "page_number": 1, "text": "x"}, "x")
    assert "hf_url" not in payload


# ── Chat must emit a real graph ─────────────────────────────────────────────


def test_chat_response_carries_a_real_graph():
    """The in-chat graph must come from the live graph, not be empty."""
    import json

    from archipelago.apps.inference_app import create_app

    app = create_app()
    client = app.test_client()
    response = client.post(
        "/api/chat", json={"query": "What is attention mechanism?", "synthesis": False}
    )
    assert response.status_code == 200
    raw = response.get_data(as_text=True)
    meta = json.loads(raw.split("\n[STREAM_START]\n")[0])

    subgraph = meta.get("subgraph") or {}
    assert subgraph.get("node_count", 0) >= 1, "graph must not be empty"
    assert subgraph.get("nodes"), "graph must carry nodes"
    # Edges must reference real nodes so the SVG can draw them.
    node_ids = {n["id"] for n in subgraph["nodes"]}
    for edge in subgraph.get("edges", []):
        assert edge["from_id"] in node_ids
        assert edge["to_id"] in node_ids
        assert edge.get("relation")


def test_chat_graph_node_contract_matches_frontend():
    """The frontend SVG reads these exact keys, so the payload must provide them."""
    import json

    from archipelago.apps.inference_app import create_app

    app = create_app()
    client = app.test_client()
    response = client.post(
        "/api/chat", json={"query": "What is attention mechanism?", "synthesis": False}
    )
    meta = json.loads(response.get_data(as_text=True).split("\n[STREAM_START]\n")[0])
    for node in (meta.get("subgraph") or {}).get("nodes", []):
        assert {"id", "label", "role", "summary", "hop"} <= set(node)
    for edge in (meta.get("subgraph") or {}).get("edges", []):
        assert {"from_id", "to_id", "relation"} <= set(edge)


# ── Reader gateway: exact book plus honest page handoff ──────────────────────


def test_open_gateway_links_to_book_and_explains_manual_page_navigation():
    """Both gateway forms name the page without promising Pearson will jump."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "host_inference"))
    from hostapp.factory import create_app

    app = create_app()
    client = app.test_client()
    book_id = "0fcd531f-3ba1-495e-9c9e-b43b034b88d9"

    for path in (f"/open/{book_id}?page=12", f"/open/book/{book_id}?page=12"):
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"
        body = response.get_data(as_text=True)
        assert "ebooks.elibrary.in.pearson.com" in body
        assert f"#book/{book_id}" in body
        assert "/page/12" not in body
        assert "page 12" in body
        assert "Automatic page navigation is not verified" in body
