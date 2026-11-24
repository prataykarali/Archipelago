"""Regression tests for the two audited OSTEP answer defects."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

HOST_DIR = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

from engine.answer import Engine  # noqa: E402
from engine.source_answer_fixes import OSTEP_ADDRESS_DOC, OSTEP_PAGING_DOC  # noqa: E402


@pytest.fixture(scope="module")
def engine() -> Engine:
    """Load the committed candidate fixture without relying on remote state."""
    return Engine(graph_path=HOST_DIR / "fixtures" / "okf_graph.json")


@pytest.mark.unit
def test_ostep_address_translation_uses_textbook_chapter(engine: Engine) -> None:
    """A same-word GPT-3 paper cannot displace the OSTEP address passage."""
    result = engine.answer("Where does OSTEP explain base-and-bounds address translation?")
    citations = result["payload"]["citations"]

    assert result["route"] == "BOOK_PAGE"
    assert len(citations) == 1
    assert citations[0]["doc_id"] == OSTEP_ADDRESS_DOC
    assert citations[0]["page_number"] == 2
    assert "Brown2020_GPT3" not in result["text"]
    assert "does not identify the exact base-and-bounds section" in result["text"]


@pytest.mark.unit
def test_paging_fault_answer_separates_general_explanation(engine: Engine) -> None:
    """The page-fault nuance is explicit and not falsely attributed to OSTEP p.3."""
    result = engine.answer("Explain virtual memory paging and page faults.")
    citations = result["payload"]["citations"]

    assert result["route"] == "BOOK_PAGE"
    assert len(citations) == 1
    assert citations[0]["doc_id"] == OSTEP_PAGING_DOC
    assert citations[0]["page_number"] == 3
    assert "demand-zero" in result["text"]
    assert "copy-on-write" in result["text"]
    assert "not established by the cited introductory passage" in result["text"]


@pytest.mark.unit
def test_base_bounds_diagnostic_uses_indexed_ostep_page(tmp_path, monkeypatch) -> None:
    """The original D10 query cites the exact approved chapter chunk when attached."""
    index = tmp_path / "passages.jsonl"
    index.write_text(
        json.dumps(
            {
                "doc_id": OSTEP_ADDRESS_DOC,
                "page_number": 7,
                "passage_id": "ostep-address-p7",
                "text": "The base register relocates virtual addresses; bounds reject invalid addresses.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ARCHIPELAGO_CANDIDATE_PASSAGES", str(index))
    candidate = Engine(graph_path=HOST_DIR / "fixtures" / "okf_graph.json")
    result = candidate.answer(
        "How does base-and-bounds hardware address translation relocate a process address space?"
    )
    assert result["route"] == "BOOK_PAGE"
    assert result["payload"]["citations"][0]["doc_id"] == OSTEP_ADDRESS_DOC
    assert result["payload"]["citations"][0]["page_number"] == 7
    assert result["payload"]["citations"][0]["chunk_id"] == "ostep-address-p7"
    assert "Brown2020_GPT3" not in result["text"]
