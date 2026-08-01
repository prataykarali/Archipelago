"""Regression suite for the three Archipelago systemic bugs.

1. Truncated LLM responses (token budget must never exceed free context)
2. Insufficient page/source links (cleanse + ensure top-up to a useful set)
3. Intermittent paper-card spawn (payload contract + UI remount contract)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from archipelago.inference import stream_budget as sb
from archipelago.inference.citations import (
    citation_payload,
    cleanse_model_citations,
)
from archipelago.inference import synthesis
from archipelago.inference.reply_styles import (
    _MAX_INLINE_CITATIONS_REQUESTED,
    _MIN_INLINE_CITATIONS_REQUESTED,
    style_instruction,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CHAT_UI = ROOT / "ui" / "chat" / "index.html"

# Useful page-link floor when graph evidence is plentiful.
_MIN_USEFUL_LINKS = 5


# ── Bug 1: Truncation ─────────────────────────────────────────────────


def test_stream_budget_never_requests_more_than_free_context() -> None:
    """num_predict must fit inside free KV slots (no mid-word length cuts)."""
    # Large study-style prompt that used to force max(MIN, free) > free.
    big_prompt = "concept notes " * 800  # ~10k+ chars
    num_ctx, num_predict = sb.stream_token_budget(
        big_prompt,
        reserve_tokens=sb.STUDY_RESERVE_TOKENS,
    )
    prompt_tokens = sb.estimate_prompt_tokens(big_prompt)
    free = max(0, num_ctx - prompt_tokens - sb.CTX_SAFETY_TOKENS)
    assert num_predict <= free or free == 0
    assert num_predict >= 1
    assert num_ctx <= sb.MAX_NUM_CTX


def test_stream_budget_study_reserve_is_roomy() -> None:
    """Short prompts still get a full study completion budget."""
    short = "What is RAG?"
    _num_ctx, num_predict = sb.stream_token_budget(
        short,
        reserve_tokens=sb.STUDY_RESERVE_TOKENS,
    )
    assert num_predict >= sb.MIN_NUM_PREDICT
    # Concise study answers: enough room to finish, not a monologue budget.
    assert sb.STUDY_RESERVE_TOKENS >= 480
    assert sb.STUDY_RESERVE_TOKENS <= 960


def test_trim_to_completion_boundary_cuts_mid_sentence() -> None:
    # Keep the completed prefix ≥ MIN_BOUNDARY_KEEP_CHARS so the guard trims
    # the ragged tail instead of preserving the whole stub.
    text = (
        "Retrieval-augmented generation pairs a dense retriever with a "
        "sequence generator so that external memory can ground each claim. "
        "The retriever fetches passages and the model then synthesi"
    )
    trimmed = sb.trim_to_completion_boundary(text)
    assert trimmed.endswith(".")
    assert "synthesi" not in trimmed
    assert "external memory" in trimmed


def test_finalize_always_trims_and_keeps_complete_tail() -> None:
    payloads = [
        {
            "evidence_id": "S1",
            "topic": "RAG",
            "doc_id": "rag.pdf",
            "page_number": 2,
        }
    ]
    stub = (
        "### Retrieval-Augmented Generation\n\n"
        "RAG retrieves external passages before generation. The model then "
        "conditions on those passages to reduce hallucin"
    )
    final = synthesis._finalize_stream_answer(
        stub,
        stub,
        stub,
        {"S1"},
        payloads,
        sterile=False,
        offline=False,
        user_query="What is RAG?",
    )
    assert final
    assert not final.rstrip().endswith("hallucin")
    assert re.search(r"[.!?…][\"'”’)]?\s*$", final.rstrip()) or "/api/page-view" in final


# ── Bug 2: Insufficient links ─────────────────────────────────────────


def _payloads(n: int) -> list[dict]:
    return [
        {
            "evidence_id": f"S{i}",
            "topic": "RAG",
            "doc_id": f"doc_{i}.pdf",
            "page_number": i,
        }
        for i in range(1, n + 1)
    ]


def test_style_instruction_requests_concise_citation_budget() -> None:
    prompt = style_instruction("Explain RAG")
    assert _MIN_INLINE_CITATIONS_REQUESTED >= 3
    assert _MAX_INLINE_CITATIONS_REQUESTED >= _MIN_INLINE_CITATIONS_REQUESTED
    assert _MAX_INLINE_CITATIONS_REQUESTED <= 8
    assert f"at least {_MIN_INLINE_CITATIONS_REQUESTED}" in prompt
    assert f"at most {_MAX_INLINE_CITATIONS_REQUESTED}" in prompt
    assert "CONCISE" in prompt or "concise" in prompt.lower() or "90–220" in prompt


def test_cleanse_tops_up_sparse_model_markers_to_useful_set() -> None:
    """A single bare [S1] must expand and top up toward a useful link set."""
    body = (
        "### Retrieval-Augmented Generation\n\n"
        "RAG retrieves passages before generation [S1]. "
        "This reduces hallucination on knowledge-intensive tasks."
    )
    out = cleanse_model_citations(body, _payloads(8))
    link_count = out.count("/api/page-view")
    assert link_count >= _MIN_USEFUL_LINKS, (
        f"expected ≥{_MIN_USEFUL_LINKS} page links, got {link_count} in:\n{out}"
    )


def test_ensure_inline_page_links_reaches_useful_set() -> None:
    body = "### RAG\n\nRetrieval augments generation with external memory."
    out = synthesis._ensure_inline_page_links(body, _payloads(8), max_links=10)
    assert out.count("/api/page-view") >= _MIN_USEFUL_LINKS


def test_max_inline_page_links_is_bounded_for_readable_bodies() -> None:
    # Enough chips for study answers; not a 35-link flood.
    assert 4 <= synthesis._MAX_INLINE_PAGE_LINKS <= 12
    assert synthesis._MAX_INLINE_PAGE_LINKS_GROUNDED <= synthesis._MAX_INLINE_PAGE_LINKS


# ── Bug 3: Paper cards ────────────────────────────────────────────────


def test_citation_payload_always_has_spawnable_page_and_url() -> None:
    """UI cards need doc_id + positive page_number + url even on sparse evidence."""
    sparse = {
        "doc_id": "notes/lora.pdf",
        "page_number": None,  # historically broke citationPageUrl
        "section_title": "",
        "text": "LoRA freezes base weights.",
        "evidence_id": "S1",
    }
    payload = citation_payload(sparse, "LoRA")
    assert payload["page_number"] >= 1
    assert payload["doc_id"] == "notes/lora.pdf"
    assert payload["url"]
    assert payload.get("page_url") == payload["url"]
    assert "/api/page-view" in payload["url"]
    assert "&page=1" in payload["url"]
    assert payload.get("title")


def test_chat_ui_remounts_evidence_rail_after_flush_race() -> None:
    """Paper cards must re-attach after innerHTML paints (STREAM_DONE race)."""
    src = CHAT_UI.read_text(encoding="utf-8")
    assert "function appendEvidenceRail" in src
    # Must remove prior rail before re-add (no sticky early-return).
    assert "prior.remove()" in src or "prior) prior.remove()" in src or "existing.remove()" in src or ".evidence-rail')" in src
    assert "data-evidence-count" in src
    # Terminal stream path re-mounts cards after flush.
    assert "appendEvidenceRail(msgEl, window._lastChatMetadata)" in src
    # paintAssistant re-attaches once bubbleFinalized.
    assert "bubbleFinalized && window._lastChatMetadata" in src
    # citationPageUrl defaults invalid pages to 1.
    assert "if (!Number.isFinite(page) || page < 1) page = 1" in src
    # finalize is idempotent remount, not a one-shot early return that blocks re-add.
    assert "Always re-mount paper cards after markdown paint" in src or (
        "firstFinalize" in src and "appendEvidenceRail(msgEl, window._lastChatMetadata)" in src
    )
