"""Unit tests for ArchipelagoResponseSanitizer in cleanser.py."""

from __future__ import annotations

import pytest

from archipelago.inference.cleanser import ArchipelagoResponseSanitizer

pytestmark = pytest.mark.unit


def test_pass_1_strip_conversational_fluff():
    sanitizer = ArchipelagoResponseSanitizer()
    raw = (
        "Hello! As an AI study assistant, Based on the provided context block, "
        "Low-Rank Adaptation (LoRA) freezes pre-trained weights."
    )
    cleaned = sanitizer.sanitize(raw)
    assert "Hello!" not in cleaned
    assert "As an AI study assistant" not in cleaned
    assert "Low-Rank Adaptation" in cleaned


def test_strip_prompt_artifacts():
    sanitizer = ArchipelagoResponseSanitizer()
    raw = (
        "Common confusion. Trace the path -> tutorial.\n"
        "Clean model. Library pin Low-Rank Adaptation with evidence.\n"
        "Low-Rank Adaptation freezes pre-trained model weights."
    )
    cleaned = sanitizer.sanitize(raw)
    assert "Common confusion" not in cleaned
    assert "Clean model" not in cleaned
    assert "Library pin" not in cleaned
    assert "Low-Rank Adaptation freezes pre-trained model weights." in cleaned


def test_clean_corrupted_summaries():
    sanitizer = ArchipelagoResponseSanitizer()
    raw = "RNN summary: 5.1 Experimental setup We now describe the experimental setup in Appendix B. Recurrent networks pass hidden states."
    cleaned = sanitizer.sanitize(raw)
    assert "Experimental setup" not in cleaned
    assert "Appendix B" not in cleaned
    assert "Recurrent networks pass hidden states." in cleaned


def test_strip_link_dump_header():
    sanitizer = ArchipelagoResponseSanitizer()
    raw = "( Low-Rank Adaptation p.1 ↗ p.8 ↗ p.12 ↗ )\n### Low-Rank Adaptation\nLoRA freezes weights."
    cleaned = sanitizer.sanitize(raw)
    assert not cleaned.startswith("(")
    assert "### Low-Rank Adaptation" in cleaned


def test_pass_2_deduplicate_blocks():
    sanitizer = ArchipelagoResponseSanitizer()
    raw = (
        "### Core Mechanism\n"
        "LoRA injects trainable rank decomposition matrices into transformer layers.\n\n"
        "### Core Mechanism\n"
        "LoRA injects trainable rank decomposition matrices into transformer layers."
    )
    cleaned = sanitizer.sanitize(raw)
    assert cleaned.count("### Core Mechanism") == 1
    assert cleaned.count("rank decomposition matrices") == 1


def test_pass_3_normalize_latex():
    sanitizer = ArchipelagoResponseSanitizer()
    raw = "The equation is \\( W = W_0 + B \\cdot A \\) and \\[ \\Delta W = B \\cdot A \\]"
    cleaned = sanitizer.sanitize(raw)
    assert "\\(" not in cleaned
    assert "\\[" not in cleaned
    assert "$ W = W_0 + B \\cdot A $" in cleaned
    assert "$$ \\Delta W = B \\cdot A $$" in cleaned


def test_pass_4_inject_deep_citation_links():
    sanitizer = ArchipelagoResponseSanitizer()
    raw = "LoRA adapts weights [CITE: Hu2021_LoRA.pdf | 3]."
    cleaned = sanitizer.sanitize(raw)
    assert "[CITE:" not in cleaned
    assert "/api/page-view?doc_id=Hu2021_LoRA.pdf&page=3" in cleaned
    assert "[1: Hu2021_LoRA.pdf, p.3 ↗]" in cleaned


def test_pass_5_format_okf_curriculum_card():
    sanitizer = ArchipelagoResponseSanitizer()
    raw = "LoRA freezes base weights."
    topology = {
        "prerequisites": ["Matrix Rank", "SVD"],
        "target": "LoRA",
        "unlocks": ["QLoRA", "Paged Optimizers"],
    }
    payloads = [
        {"doc_id": "Hu2021_LoRA.pdf", "page_number": 3, "evidence_id": "S1"}
    ]
    cleaned = sanitizer.sanitize(raw, retrieved_concepts=topology, citation_payloads=payloads)
    # New visual Learning Path chain format.
    assert "### Learning Path" in cleaned
    assert "\U0001f9e0" in cleaned  # 🧠 learning path emoji
    assert "Matrix Rank" in cleaned
    assert "LoRA" in cleaned
    assert "QLoRA" in cleaned
    # New grouped Evidence block format.
    assert "### Evidence" in cleaned
    assert "Hu2021 LoRA" in cleaned or "Hu2021_LoRA" in cleaned
    assert "3" in cleaned  # page number present

