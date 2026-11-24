"""D10-S3 verification tests for 5-type source resolution, zero-404 citations, and Stack of Books."""

from __future__ import annotations

import csv
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, unquote, urlparse

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


def test_five_source_types_resolution() -> None:
    """All 5 source types (A-E) classify honestly with zero broken 404 URLs."""
    from engine.source_resolution import (
        SOURCE_CAT_MISSING,
        SOURCE_CAT_OA_PAPER,
        SOURCE_CAT_OA_TEXTBOOK,
        SOURCE_CAT_PEARSON,
        SOURCE_CAT_TOC_INDEX,
        resolve_source_target,
    )

    # Type A: OA research paper
    res_a = resolve_source_target(
        raw_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        canonical_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        page_number=2,
    )
    assert res_a["source_category"] == SOURCE_CAT_OA_PAPER
    assert res_a["reader_resolvable"] is True
    assert res_a["page_verified"] is True
    assert res_a["url"].startswith("/read?doc=")
    assert "page=2" in res_a["url"]

    # Type B: Full-text OA textbook (OSTEP + Deisenroth)
    res_b1 = resolve_source_target(
        raw_doc_id="archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
        canonical_doc_id="archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
        page_number=3,
    )
    assert res_b1["source_category"] == SOURCE_CAT_OA_TEXTBOOK
    assert res_b1["reader_resolvable"] is True
    assert res_b1["page_verified"] is True
    assert res_b1["url"].startswith("/read?doc=")

    res_b2 = resolve_source_target(
        raw_doc_id="textbooks/Deisenroth_Math_For_ML.pdf",
        canonical_doc_id="textbooks/Deisenroth_Math_For_ML.pdf",
        page_number=15,
    )
    assert res_b2["source_category"] == SOURCE_CAT_OA_TEXTBOOK
    assert res_b2["reader_resolvable"] is True
    assert res_b2["url"].startswith("/read?doc=")

    # Type C: TOC / index-only textbook
    res_c = resolve_source_target(
        raw_doc_id="data_science_2019/Index_2019_Data-Science.pdf",
        canonical_doc_id="data_science_2019/Index_2019_Data-Science.pdf",
        page_number=8,
    )
    assert res_c["source_category"] == SOURCE_CAT_TOC_INDEX
    assert res_c["reader_resolvable"] is False
    assert res_c["url"] == ""
    assert res_c["page_number"] is None

    # Type D: Pearson catalogue-only textbook (no invented page numbers)
    res_d = resolve_source_target(
        raw_doc_id="doc_computer_networks_6_e",
        canonical_doc_id="doc_computer_networks_6_e",
        page_number=42,
    )
    assert res_d["source_category"] == SOURCE_CAT_PEARSON
    assert res_d["is_pearson"] is True
    assert res_d["book_type"] == "reflowable"
    assert res_d["page_verified"] is False
    assert res_d["page_number"] is None
    assert res_d["url"].startswith("/open/")
    assert "?page=" not in res_d["url"]

    # Type E: Missing / unsupported source
    res_e = resolve_source_target(
        raw_doc_id="papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf",
        canonical_doc_id="papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf",
        page_number=6,
    )
    assert res_e["source_category"] == SOURCE_CAT_MISSING
    assert res_e["reader_resolvable"] is False
    assert res_e["url"] == ""
    assert res_e["page_number"] is None


def test_zero_broken_404_citations_on_36_diagnostic_queries() -> None:
    """None of the 36 D10 diagnostic queries may emit a 404 clickable URL or leak subscriptionId."""
    from engine.answer import Engine
    from library_index import resolve_hf_source
    from remote_cache import load_books

    csv_path = ROOT / "docs" / "sigir" / "D10_ANSWER_GROUNDING_DIAGNOSTICS.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert len(rows) == 36

    eng = Engine()
    pearson_ids = {str(b.get("id")) for b in load_books() if b.get("id")}

    for row in rows:
        res = eng.answer(row["query"])
        text = res.get("text") or ""
        assert "subscriptionId=" not in text, f"Leaked subscriptionId in {row['query_id']}"
        assert "HF_TOKEN" not in text, f"Leaked HF_TOKEN in {row['query_id']}"

        cites = [c for c in ((res.get("payload") or {}).get("citations") or []) if isinstance(c, dict)]
        inline_urls = re.findall(r"\]\((/[^)\s]+|https?://[^)\s]+)\)", text)
        cite_urls = [str(c.get("url") or "") for c in cites if c.get("url")]

        for url in set(cite_urls + inline_urls):
            assert "subscriptionId=" not in url, f"Leaked subscriptionId in URL {url}"
            if url.startswith("/open/"):
                bid = url.split("/open/", 1)[1].split("?")[0].split("#")[0].removeprefix("book/")
                assert bid in pearson_ids, f"Broken Pearson /open/ link in {row['query_id']}: {url}"
            elif url.startswith("/read?"):
                doc = unquote((parse_qs(urlparse(url).query).get("doc") or [""])[0])
                _, hf = resolve_hf_source(doc)
                assert hf, f"Broken 404 /read? link in {row['query_id']}: {url}"
            elif url.startswith("/papers/"):
                doc = unquote(url.split("/papers/", 1)[1].split("#")[0].split("?")[0])
                _, hf = resolve_hf_source(doc)
                assert hf, f"Broken 404 /papers/ link in {row['query_id']}: {url}"


def test_catalog_all_12_domains_and_ui_mirror() -> None:
    """Stack of Books catalog exposes all 12 domains, clean redirects, and mirrored UI files."""
    from hostapp.factory import CONTEXT_KEY, create_app

    app = create_app()

    class _TestAuth:
        def principal(self):
            return {"role": "student", "username": "qa"}, None

        def required(self):
            return False

    app.extensions[CONTEXT_KEY].auth = _TestAuth()
    client = app.test_client()

    resp = client.get("/api/catalog/all")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload["domains"]) == 12
    assert payload["total"] >= 80
    assert "subscriptionId" not in resp.get_data(as_text=True)

    # Verify host_inference/ui/ and ui/chat/ are mirrored identically.
    for rel in (
        "fragments/chat-operations.html",
        "js/02--kw-highlights.js",
        "js/04-start-new-chat.js",
        "js/05-display-books.js",
    ):
        a = (ROOT / "host_inference" / "ui" / rel).read_text(encoding="utf-8")
        b = (ROOT / "ui" / "chat" / rel).read_text(encoding="utf-8")
        assert a == b, f"UI mirror mismatch for {rel}"
