"""Preserve reader page indices and printed labels during PDF extraction."""

from __future__ import annotations

import fitz
import pytest

from archipelago.ingestion.pdf_io import ingest_document

pytestmark = pytest.mark.unit

BODY_TEXT = "A page of source text keeps its physical page and printed label distinct. " * 16


def test_pdf_page_index_and_printed_label_are_distinct(tmp_path) -> None:
    """Roman front matter must not shift the physical reader page."""
    source = tmp_path / "labeled.pdf"
    document = fitz.open()
    for _ in range(4):
        page = document.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 750), BODY_TEXT)
    document.set_page_labels(
        [
            {"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1},
            {"startpage": 2, "prefix": "", "style": "D", "firstpagenum": 1},
        ]
    )
    document.save(source)
    document.close()

    chunks = ingest_document(str(source))
    assert chunks
    by_page = {chunk["page_number"]: chunk for chunk in chunks}
    assert by_page[1]["pdf_page_index"] == 0
    assert by_page[1]["printed_page"] == "i"
    assert by_page[3]["pdf_page_index"] == 2
    assert by_page[3]["printed_page"] == "1"
    assert by_page[3]["page_label_map"]["1"] == 3
    assert by_page[3]["text_offset_start"] is not None


def test_unlabeled_pdf_does_not_invent_printed_page(tmp_path) -> None:
    """An unlabeled PDF can still link by its physical page."""
    source = tmp_path / "unlabeled.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 550, 750), BODY_TEXT)
    document.save(source)
    document.close()

    chunks = ingest_document(str(source))
    assert chunks[0]["page_number"] == 1
    assert chunks[0]["pdf_page_index"] == 0
    assert chunks[0]["printed_page"] is None
