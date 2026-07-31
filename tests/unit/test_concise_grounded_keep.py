"""Concise answers + keep grounded first-paint over rambling model rewrites."""
from __future__ import annotations

import re

import pytest

from archipelago.inference import synthesis

pytestmark = pytest.mark.unit


def test_strip_residual_s_hash_and_fake_model_brackets() -> None:
    noisy = (
        "RAG retrieves passages [S#] to (p.4 ↗). "
        "[RWC+19]: trained on proprietary data. "
        "[GPT-2]: also trained. [S3] leftover."
    )
    cleaned = synthesis._strip_residual_markers(noisy)
    assert "[S#]" not in cleaned
    assert "[S3]" not in cleaned
    assert "RWC+19" not in cleaned
    assert "GPT-2" not in cleaned or "[" not in cleaned


def test_citation_spam_detector_flags_user_rag_dump() -> None:
    dump = (
        "### RAG\n\n"
        "[S#] to (p.4 ↗): jointly train.\n"
        "[RWC+19]: left-to-right model.\n"
        "[GPT-2]: left-to-right model.\n"
        "The model is trained. The model is trained. The model is trained."
    )
    assert synthesis._looks_like_citation_spam(dump)


def test_verbose_trim_caps_word_count() -> None:
    long = (
        "### Topic\n\n"
        + ("Retrieval helps generation with external memory. " * 80)
    )
    trimmed = synthesis._trim_verbose_study_answer(long, max_words=120)
    assert synthesis._count_words(trimmed) <= 130
    assert trimmed.endswith((".", "!", "?", "…")) or len(trimmed) < len(long)


def test_model_unusable_when_too_verbose_vs_rich_grounded() -> None:
    grounded = (
        "### Understanding RAG\n\n"
        "RAG retrieves passages before generation "
        "[p.1 ↗](/api/page-view?doc_id=a.pdf&page=1).\n\n"
        "Students learn dense retrieval, then the generator conditions on hits."
    )
    ramble = (
        "### RAG\n\n"
        + ("The model is trained on a diverse set of texts from various domains. " * 50)
        + "[S#] to more noise " * 5
    )
    assert not synthesis._model_answer_is_usable(ramble, "What is RAG?", grounded)


def test_finalize_keeps_grounded_over_s_hash_spam() -> None:
    grounded = (
        "### Understanding Retrieval-Augmented Generation\n\n"
        "RAG pairs a retriever with a generator so answers stay grounded in "
        "indexed passages "
        "[p.2 ↗](/api/page-view?doc_id=Lewis2020_RAG.pdf&page=2&highlight=RAG).\n\n"
        "**Learn first**\n"
        "- Dense retrieval\n"
        "- Attention over context\n"
    )
    model = (
        "### RAG\n\n"
        "Definition long essay...\n"
        "[S#] to (p.4 ↗)\n"
        "[RWC+19]: evaluation chatter\n"
        "[GPT-2]: more chatter\n"
        + ("The model is trained. " * 30)
    )
    final = synthesis._finalize_stream_answer(
        model,
        grounded,
        grounded,
        {"S1"},
        [{
            "evidence_id": "S1",
            "topic": "RAG",
            "doc_id": "Lewis2020_RAG.pdf",
            "page_number": 2,
        }],
        sterile=False,
        offline=False,
        user_query="tell me about RAG",
    )
    assert "[S#]" not in final
    assert "RWC+19" not in final
    assert "Retrieval-Augmented" in final or "RAG" in final
    assert "/api/page-view" in final
    # Must not ship the rambling training-loop monologue.
    assert final.lower().count("the model is trained") < 3
