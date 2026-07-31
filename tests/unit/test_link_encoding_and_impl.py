"""Link encoding (spaces in PDF names) + build-SQL implementation refusal."""

from archipelago.inference.aliases import pdf_page_url, page_view_markdown_link
from archipelago.inference.citations import (
    _cite_with_link, render_citation_from_payload, build_library_source_payloads,
)
from archipelago.inference.intent_gate import classify_intent, INTENT_IMPLEMENTATION


MESSY_DOC = "papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf"


def test_page_view_link_encodes_messy_doc_id():
    md = page_view_markdown_link("PDF page 9", MESSY_DOC, 9, highlight="SQL")
    assert "/api/page-view?" in md
    assert "doc_id=" in md
    assert "%20" in md  # spaces encoded
    assert " " not in md[md.index("(") + 1 : md.rindex(")")]
    assert "page=9" in md
    assert "highlight=SQL" in md or "highlight=SQL" in md.replace("+", " ")


def test_cite_with_link_uses_page_view_not_raw_pdf_with_spaces():
    evidence = [{
        "evidence_id": "S1",
        "doc_id": MESSY_DOC,
        "page_number": 9,
        "section_title": "SQL",
        "text": "SQL is a query language",
    }]
    out = _cite_with_link("SQL", evidence)
    assert "/api/page-view?" in out
    assert "%20" in out or "doc_id=" in out
    # Must not emit a bare-space /pdfs/ href that markdown would truncate
    if "/pdfs/" in out:
        href_start = out.find("](") + 2
        href_end = out.find(")", href_start)
        href = out[href_start:href_end]
        assert " " not in href.split("#")[0]


def test_render_citation_payload_encodes_doc():
    payload = {
        "evidence_id": "S1",
        "topic": "SQL",
        "doc_id": MESSY_DOC,
        "page_number": 9,
        "printed_page": None,
    }
    out = render_citation_from_payload(payload)
    assert "p.9" in out  # clean single page-view link, not the old [S1: label
    assert "highlight=SQL" in out
    assert "/api/page-view?" in out
    # Extract the markdown href: …](URL)
    href = out[out.rindex("](") + 2 : out.rindex(")")]
    assert href.startswith("/api/page-view?")
    assert " " not in href
    assert "%20" in href


def test_build_sql_table_is_implementation_not_theory():
    info = classify_intent("hi i wanna build a sql table")
    assert info["intent"] == INTENT_IMPLEMENTATION, info
    info2 = classify_intent("create table students in SQL")
    assert info2["intent"] == INTENT_IMPLEMENTATION, info2


def test_pdf_page_url_path_encoding():
    url = pdf_page_url(MESSY_DOC, 9)
    assert url.endswith("#page=9")
    path = url.split("#")[0]
    assert " " not in path
    assert "%20" in path


def test_library_source_payloads_are_clickable_and_exclude_unindexed_seeds():
    payloads = build_library_source_payloads(
        [{
            "id": MESSY_DOC,
            "title": "A real indexed document",
            "matched": ["SQL"],
        }],
        "SQL",
    )
    assert len(payloads) == 1
    source = payloads[0]
    assert source["evidence_id"] == "S1"
    assert source["source_type"] == "indexed_document"
    assert source["page_number"] == 1
    assert source["url"].startswith("http")
    assert "/api/page-view?" in source["url"]
    assert "%20" in source["url"]
