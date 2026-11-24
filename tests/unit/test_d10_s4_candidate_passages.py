"""Candidate PDF passages are available to catalog retrieval with exact pages."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import fitz
import pytest

from scripts.ops.build_d10_candidate_passages import extract_pdf

HOST_INFERENCE = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST_INFERENCE) not in sys.path:
    sys.path.insert(0, str(HOST_INFERENCE))

pytestmark = pytest.mark.unit


def test_deterministic_index_preserves_original_page_and_offsets(tmp_path) -> None:
    """Reader page and source offsets come from the original PDF bytes."""
    source = tmp_path / "sample.pdf"
    document = fitz.open()
    for line in ("Front matter", "Base and bounds translates a virtual address"):
        page = document.new_page()
        page.insert_text((50, 50), line)
    document.save(source)
    document.close()

    first = extract_pdf(source, "books/textbooks/sample.pdf", "a" * 64)
    second = extract_pdf(source, "books/textbooks/sample.pdf", "a" * 64)
    assert first == second
    assert first[1]["page_number"] == 2
    assert first[1]["pdf_page_index"] == 1
    assert first[1]["text_offset_start"] == 0
    assert "Base and bounds" in first[1]["text"]


def test_catalog_loads_candidate_body_chunk_for_document_lookup(tmp_path, monkeypatch) -> None:
    """A missing graph source can still return an approved indexed PDF passage."""
    from library_index import Catalog

    index = tmp_path / "candidate.jsonl"
    index.write_text(
        json.dumps(
            {
                "doc_id": "books/textbooks/sample.pdf",
                "page_number": 2,
                "passage_id": "sample:p2:c0",
                "printed_page": "i",
                "pdf_page_index": 1,
                "text_offset_start": 0,
                "text_offset_end": 74,
                "text": "Base and bounds hardware translates a virtual address to physical memory.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ARCHIPELAGO_CANDIDATE_PASSAGES", str(index))
    catalog = Catalog({}, [])
    passage = catalog.best_passage(
        "How does base and bounds hardware translate a virtual address?", "sample.pdf"
    )
    assert passage is not None
    assert passage["page"] == 2
    assert passage["passage_id"] == "sample:p2:c0"
    assert passage["printed_page"] == "i"
    assert passage["pdf_page_index"] == 1
