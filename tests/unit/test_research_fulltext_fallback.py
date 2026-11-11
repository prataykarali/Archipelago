"""Preserve page-linked evidence when Indra does not classify headings."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from archipelago.scholarly.bridge import fulltext

pytestmark = pytest.mark.unit


def test_preamble_fallback_keeps_pdf_page_and_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    """A readable first-page abstract still produces verified PDF fields."""
    monkeypatch.setattr(fulltext, "indra_available", lambda: True)
    monkeypatch.setattr(
        fulltext.ArtifactFetcher,
        "fetch_pdf",
        lambda *_args: {"file_path": "paper.pdf", "sha256": "known-sha"},
    )
    monkeypatch.setattr(
        fulltext,
        "parse_with_indra",
        lambda *_args: {
            "num_pages": 4,
            "sections": {
                "preamble": [
                    {
                        "page": 1,
                        "section": "preamble",
                        "text": "Abstract—This paper introduces the Bengali speech digits dataset.",
                    }
                ]
            },
        },
    )
    monkeypatch.setattr(fulltext, "extract_slm_paper_fields", lambda *_args: [])
    monkeypatch.setattr(fulltext, "extract_abstract_fields", lambda *_args: [])
    paper = SimpleNamespace(paper_id="paper-1", is_open_access=True, license="cc-by")
    record: dict = {"metadata": {}}

    state = fulltext.enrich_fulltext(
        {"paper": paper, "pdf_url": "https://arxiv.org/pdf/2403.13465"}, record
    )

    assert state == "FULLTEXT_EXTRACTED"
    fields = record["metadata"]["verified_extractions"]
    assert any(field["field"] == "datasets" for field in fields)
    assert all(field["pdf_page"] == 1 for field in fields)
    assert all(field["pdf_sha256"] == "known-sha" for field in fields)
    assert all(field["evidence_text"] in "Abstract—This paper introduces the Bengali speech digits dataset." for field in fields)
