"""Regression coverage for target-only evidence and clean citations."""
from __future__ import annotations

import pytest

from archipelago.inference.citation_output import render_clean_citation_output
from archipelago.inference.evidence_filter import select_target_evidence

pytestmark = pytest.mark.unit


def _source(doc_id: str, page: int, text: str) -> dict:
    return {
        "doc_id": doc_id,
        "page_number": page,
        "text_passage": text,
        "source_category": "paper",
    }


def test_lora_evidence_prioritizes_foundational_and_qlora_papers() -> None:
    concept = {
        "id": "low_rank_adaptation",
        "name": "Low-Rank Adaptation",
        "aliases": ["LoRA"],
        "sources": [
            _source(
                "papers/Real-time network security.pdf",
                2,
                "Dynamic graph clustering identifies network anomalies.",
            ),
            _source(
                "papers/Velickovic2017_GAT.pdf",
                3,
                "Graph attention networks aggregate neighboring node features.",
            ),
            _source(
                "papers/Hu2021_LoRA.pdf",
                4,
                "Our method LoRA freezes pretrained weights and learns low-rank matrices.",
            ),
            _source(
                "papers/Dettmers2023_QLoRA.pdf",
                7,
                "QLoRA uses Low-rank Adapters and matches 16-bit finetuning.",
            ),
        ],
    }

    selected = select_target_evidence(concept, "What is LoRA?")
    doc_ids = [item["doc_id"] for item in selected]
    assert "papers/Hu2021_LoRA.pdf" in doc_ids
    assert "papers/Dettmers2023_QLoRA.pdf" in doc_ids
    assert "papers/Real-time network security.pdf" not in doc_ids
    assert "papers/Velickovic2017_GAT.pdf" not in doc_ids


def test_clean_citation_output_keeps_bare_tags_and_human_source_lines() -> None:
    payloads = [
        {
            "evidence_id": "S1",
            "doc_id": "papers/Hu2021_LoRA.pdf",
            "title": "Hu2021_LoRA.pdf",
            "page_number": 4,
        },
        {
            "evidence_id": "S2",
            "doc_id": "papers/Dettmers2023_QLoRA.pdf",
            "title": "Dettmers2023_QLoRA.pdf",
            "page_number": 7,
        },
    ]
    dirty = (
        "LoRA freezes base weights "
        "[S1](/api/page-view?doc_id=Hu2021_LoRA.pdf&page=4). "
        "QLoRA matches 16-bit performance [S2].\n\n"
        "Source Citations:\n"
        "papers/Hu2021_LoRA.pdf_chunk_010, page 4"
    )

    clean = render_clean_citation_output(dirty, payloads)
    assert "/api/page-view" not in clean
    assert "doc_id=" not in clean
    assert "chunk_" not in clean
    assert "[S1]" in clean
    assert "[S2]" in clean
    assert "[S1] Hu2021_LoRA.pdf, Page 4" in clean
    assert "[S2] Dettmers2023_QLoRA.pdf, Page 7" in clean


def test_clean_citation_output_caps_repeated_source_markers() -> None:
    payloads = [
        {
            "evidence_id": "S1",
            "doc_id": "paper.pdf",
            "page_number": 3,
        }
    ]
    clean = render_clean_citation_output(
        "First claim [S1]. Second claim [S1]. Third claim [S1].",
        payloads,
    )
    assert clean.split("Source Citations", maxsplit=1)[0].count("[S1]") == 2
