"""S2 acceptance cases for provenance, inventory, and navigation."""

from __future__ import annotations

import pytest

from archipelago.inference.citation_output import render_clean_citation_output
from archipelago.inference.citations.part03_render import render_citation_from_payload
from archipelago.inference.corpus_inventory import inventory_for_books
from archipelago.inference.evidence_contract import evidence_record, retain_observations
from archipelago.inference.reply_inventory import attach_inventory
from host_inference.engine.citation_format import link_answer_sources

pytestmark = pytest.mark.unit


def test_book_with_koha_snapshot_holding(monkeypatch: pytest.MonkeyPatch) -> None:
    """An exact title from a Koha export may show timestamped copy counts."""
    from archipelago.inference import corpus_inventory

    monkeypatch.setattr(
        corpus_inventory,
        "_koha_holdings",
        lambda: {
            "databasebook": {
                "book_title": "Database Book",
                "authors": "A. Author",
                "total_copies": 2,
                "available_copies": 1,
                "accession": "A1",
                "koha_record_verified": True,
                "verification_status": "Catalog snapshot",
                "retrieved_at": "2026-11-10T00:00:00+00:00",
                "opac_url": "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-search.pl?q=Database%20Book",
            }
        },
    )
    reply = attach_inventory(
        "What books are available?", "Catalog result:", books=[{"book_title": "Database Book"}]
    )
    assert (
        "| Title | Author | Edition / ISBN | Call number | Copies | Available | Source |" in reply
    )
    assert "| Database Book | A. Author | — | — | 2 | 1 |" in reply
    assert "2026-11-10" in reply
    assert "Koha snapshot" in reply


def test_book_metadata_has_unknown_stock() -> None:
    row = inventory_for_books(
        [{"book_title": "Unknown Text", "authors": "A. Author", "isbn": "9781234567890"}]
    )[0]
    assert "available_copies" not in row
    assert "total_copies" not in row
    reply = attach_inventory(
        "Is this book available?", "Metadata found.", meta={"title": "Unknown Text"}
    )
    assert "Not verified in the catalog" in reply
    assert "opac-search.pl" in reply


def test_real_local_pdf_page_link() -> None:
    record = evidence_record(
        {
            "evidence_id": "S1",
            "doc_id": "papers/Devlin2018_BERT.pdf",
            "page_number": 2,
            "title": "BERT",
            "passage": "BERT uses bidirectional pretraining.",
        }
    )
    assert record["source_type"] == "ingested_pdf"
    assert record["url"].endswith("&page=2#page=2")
    assert "[S1: BERT, PDF p.2](/api/page-view?" in render_citation_from_payload(record)


def test_doi_without_local_pdf() -> None:
    record = evidence_record(
        {
            "evidence_id": "S2",
            "source_type": "scholarly_record",
            "title": "Verified Paper",
            "doi": "10.1000/example",
            "source_provider": "publisher",
            "verification_status": "Verified",
        }
    )
    assert record["url"] == "https://doi.org/10.1000/example"
    assert "PDF p." not in render_citation_from_payload(record)


def test_multi_source_synthesis_deduplicates_and_rejects_unknown_marker() -> None:
    sources = [
        {
            "evidence_id": "S1",
            "title": "A",
            "doi": "10.1000/a",
            "source_type": "scholarly_record",
            "verification_status": "Verified",
        },
        {
            "evidence_id": "S2",
            "title": "B",
            "doi": "10.1000/b",
            "source_type": "scholarly_record",
            "verification_status": "Verified",
        },
    ]
    answer = render_clean_citation_output(
        "A finds X [S1]. B finds Y [S2]. Unsupported [S9].", sources + sources[:1]
    )
    assert answer.count("**Sources:**") == 1
    assert answer.count("- [S1:") == 1
    assert "[S9]" not in answer
    hosted = link_answer_sources(
        "A [S1: A]. B [S2: B].",
        [
            {**sources[0], "label": "[S1: A]", "url": "https://doi.org/10.1000/a"},
            {**sources[1], "label": "[S2: B]", "url": "https://doi.org/10.1000/b"},
        ],
    )
    assert hosted.count("**Sources:**") == 1
    assert "[S2: B](https://doi.org/10.1000/b)" in hosted


def test_unknown_or_nonmatching_source_cannot_cite() -> None:
    missing = evidence_record(
        {"evidence_id": "S3", "doc_id": "papers/Nonexistent.pdf", "page_number": 1}
    )
    assert "url" not in missing
    assert missing["verification_status"] == "Requires verification"
    reply = attach_inventory("Where is this book?", "No match.", meta={"title": "Nonmatching Book"})
    assert "Not verified in the catalog" in reply
    assert "copies" not in reply


def test_disagreeing_snapshots_remain_separate() -> None:
    records = [
        {
            "title": "Book",
            "source_type": "opac_snapshot",
            "source_provider": "Koha",
            "retrieved_at": "2026-11-01",
            "available_copies": 1,
        },
        {
            "title": "Book",
            "source_type": "live_holdings",
            "source_provider": "Koha API",
            "retrieved_at": "2026-11-11",
            "available_copies": 0,
        },
    ]
    observations = retain_observations(records + records[:1])
    assert len(observations) == 2
    assert [record["available_copies"] for record in observations] == [1, 0]
    assert observations[0]["retrieved_at"] != observations[1]["retrieved_at"]
