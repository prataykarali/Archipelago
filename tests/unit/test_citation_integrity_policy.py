"""Focused regression tests for Issue #11 — Evidence and Citation Integrity.

Verifies the deterministic evidence selection and provenance integrity policy:
1. No arbitrary padding to 10 citations; no overbroad neighborhood expansion.
2. Anchor-relevant, primary-source passages preferred; low-signal end-matter filtered.
3. Withdrawn and metadata-only sources handled safely without fallback dilution.
4. Unique canonical ``chunk_id`` verification; unmatched/ambiguous chunks marked
   explicitly rather than mapping every same-page chunk.
5. Provenance verification distinguished from semantic claim support (never
   labeled "Grounded" without semantic claim-support assessment).
6. Q39 clean abstention and Q21 primary Vaswani references preserved.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host_inference"))

from engine import Engine  # noqa: E402
from engine.evidence_selection import (  # noqa: E402
    CLAIM_SUPPORT_NOT_ASSESSED,
    MAX_ANCHOR_CITATIONS,
    PROVENANCE_CHUNK_AMBIGUOUS,
    PROVENANCE_CHUNK_UNMATCHED,
    PROVENANCE_METADATA_ONLY,
    PROVENANCE_NONE,
    PROVENANCE_VERIFIED,
    PROVENANCE_WITHDRAWN,
    is_low_signal_passage,
    verify_chunk_provenance,
)

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def engine() -> Engine:
    """Shared deterministic Engine instance for citation integrity tests."""
    return Engine()


class TestNoPaddingOrNeighborhoodDilution:
    """Verify citations stay focused on anchor/query-relevant evidence."""

    def test_q01_transformer_no_padding_and_primary_vaswani_only(self, engine: Engine) -> None:
        """Q01 must return <= MAX_ANCHOR_CITATIONS, all from Vaswani2017, zero neighbor dilution."""
        res = engine.answer("What is Transformer?")
        payload = res["payload"]
        citations = payload["citations"]

        assert 1 <= len(citations) <= MAX_ANCHOR_CITATIONS
        spurious_docs = ("AlexNet", "DDPM", "ReAct", "Bahdanau", "FlashAttention")
        for cite in citations:
            doc_id = str(cite.get("doc_id") or "")
            assert doc_id == "papers/Vaswani2017_Attention_Is_All_You_Need.pdf"
            assert not any(bad in doc_id for bad in spurious_docs)
            assert cite.get("chunk_id") != "chunk_037", "Appendix/legal end-matter must be excluded"
            assert cite["provenance_status"] == PROVENANCE_VERIFIED
            assert cite["chunk_provenance_match"] == "exact_unique_canonical_chunk"
            assert cite["canonical_passage_id"] == f"{doc_id}::{cite['chunk_id']}"
            assert cite["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED

        # Distinct chunks on the same page (e.g. p.2 chunk_007 & chunk_008) stay distinct.
        canonical_ids = [c["canonical_passage_id"] for c in citations]
        assert len(canonical_ids) == len(set(canonical_ids))

    def test_q08_flashattention_no_spurious_neighbors_and_unmatched_upload_marked(
        self, engine: Engine
    ) -> None:
        """Q08 must avoid GPT-3/vLLM/unverified upload dilution and flag upload chunk as unmatched."""
        res = engine.answer("Explain FlashAttention")
        payload = res["payload"]
        citations = payload["citations"]

        assert len(citations) == 1
        cite = citations[0]
        assert cite["doc_id"] == "papers/Dao2022_FlashAttention.pdf"
        assert cite["page_number"] == 2
        assert cite["chunk_id"] == "upload_cb7badb2_p2_2"
        assert cite["provenance_status"] == PROVENANCE_CHUNK_UNMATCHED
        assert cite["chunk_provenance_match"] == "upload_chunk_unmatched"
        assert cite["canonical_passage_id"] is None
        assert cite["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED

        trace = payload["trace"]
        assert trace["provenance_status"] == PROVENANCE_CHUNK_UNMATCHED
        assert trace["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED
        assert "grounded" not in trace["grounding_badge"].lower()

    def test_q23_dpr_bm25_no_spurious_neighbors(self, engine: Engine) -> None:
        """Q23 must cite Karpukhin2020_DPR and never pad with Outlines/ConstitutionalAI/GPT-3."""
        res = engine.answer("How does DPR compare to BM25 in open-domain QA?")
        citations = res["payload"]["citations"]

        assert 1 <= len(citations) <= MAX_ANCHOR_CITATIONS
        assert any(
            c["doc_id"] == "papers/Karpukhin2020_DPR.pdf" and c["chunk_id"] == "chunk_007"
            for c in citations
        )
        forbidden = ("Vaswani2017", "Outlines", "ConstitutionalAI", "GPT3")
        for cite in citations:
            assert not any(bad in str(cite.get("doc_id") or "") for bad in forbidden)


class TestProvenanceVsClaimSupportAndAbstention:
    """Verify honest provenance-vs-support labels, Q21 preservation, and Q39 abstention."""

    def test_q21_preserves_primary_vaswani_references_without_grounded_overclaim(
        self, engine: Engine
    ) -> None:
        """Q21 preserves both Vaswani passages while distinguishing provenance from claim support."""
        res = engine.answer("How does self-attention relate to the Transformer?")
        payload = res["payload"]
        citations = payload["citations"]

        assert len(citations) == 2
        assert all(
            c["doc_id"] == "papers/Vaswani2017_Attention_Is_All_You_Need.pdf" for c in citations
        )
        assert {c["chunk_id"] for c in citations} == {"chunk_013", "chunk_031"}
        assert all(c["provenance_status"] == PROVENANCE_VERIFIED for c in citations)
        assert all(c["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED for c in citations)

        trace = payload["trace"]
        assert trace["provenance_status"] == PROVENANCE_VERIFIED
        assert trace["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED
        assert "grounded" not in trace["grounding_badge"].lower()

    def test_q39_preserves_clean_abstention(self, engine: Engine) -> None:
        """Q39 unindexed topic must cleanly abstain with 0 citations and no graph."""
        res = engine.answer("Explain Spanner TrueTime and its prerequisites.")
        payload = res["payload"]

        assert payload["citations"] == []
        assert payload["anchor_concept"] is None
        assert payload["render_graph"] is False
        trace = payload["trace"]
        assert trace["grounding_status"] == "unmatched"
        assert trace["provenance_status"] == PROVENANCE_NONE
        assert trace["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED

    def test_metadata_only_textbook_handled_without_neighbor_padding(self, engine: Engine) -> None:
        """Metadata-only textbook concept emits no broken URL and no neighbor padding."""
        res = engine.answer("What is deadlock?")
        payload = res["payload"]
        citations = payload["citations"]

        assert len(citations) == 1
        cite = citations[0]
        assert cite["doc_id"] == "textbooks/operating_system_concepts_silberschatz.pdf"
        assert cite["url"] == ""
        assert cite["page_number"] is None
        assert cite["provenance_status"] == PROVENANCE_METADATA_ONLY
        assert cite["canonical_passage_id"] is None
        assert cite["verification_status"] == "Source linked — not independently audited"
        assert cite["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED

        trace = payload["trace"]
        assert trace["provenance_status"] == PROVENANCE_METADATA_ONLY
        assert trace["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED
        assert "grounded" not in trace["grounding_badge"].lower()

    def test_withdrawn_anchor_source_never_falls_back_to_unrelated_neighbor(
        self, engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When an anchor's sole source is withdrawn, emit withdrawal notice with no URL."""
        retired = {"papers/Karpukhin2020_DPR.pdf"}
        monkeypatch.setattr("engine.evidence_selection.withdrawn_documents", lambda: retired)
        monkeypatch.setattr("engine.graph.withdrawn_documents", lambda: retired)

        res = engine.answer("How does DPR compare to BM25 in open-domain QA?")
        payload = res["payload"]
        citations = payload["citations"]

        assert len(citations) == 1
        cite = citations[0]
        assert cite["withdrawn"] is True
        assert cite["url"] == ""
        assert cite["pdf_url"] == ""
        assert cite["provenance_status"] == PROVENANCE_WITHDRAWN
        assert cite["canonical_passage_id"] is None
        assert payload.get("withdrawn_notice")
        assert payload["trace"]["provenance_status"] == PROVENANCE_WITHDRAWN


class TestChunkProvenanceAndLowSignalFilters:
    """Direct unit tests for canonical chunk verification and low-signal passage detection."""

    def test_verify_chunk_provenance_distinguishes_unique_missing_and_ambiguous(self) -> None:
        """Missing or ambiguous chunk_id must be marked unmatched/ambiguous, never guessed."""
        unique_index = {("papers/Vaswani2017.pdf", "chunk_008"): {"abc123"}}
        ambiguous_index = {("papers/Vaswani2017.pdf", "chunk_008"): {"abc123", "def456"}}

        ok = verify_chunk_provenance(
            raw_doc_id="papers/Vaswani2017.pdf",
            canonical_doc_id="papers/Vaswani2017.pdf",
            chunk_id="chunk_008",
            page_number=2,
            hf_url="/read?doc=papers%2FVaswani2017.pdf&page=2",
            text_passage="The Transformer uses stacked self-attention layers.",
            all_withdrawn=False,
            chunk_index=unique_index,
        )
        assert ok["provenance_status"] == PROVENANCE_VERIFIED
        assert ok["canonical_passage_id"] == "papers/Vaswani2017.pdf::chunk_008"
        assert ok["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED

        missing = verify_chunk_provenance(
            raw_doc_id="papers/Vaswani2017.pdf",
            canonical_doc_id="papers/Vaswani2017.pdf",
            chunk_id=None,
            page_number=2,
            hf_url="/read?doc=papers%2FVaswani2017.pdf&page=2",
            text_passage="The Transformer uses stacked self-attention layers.",
            all_withdrawn=False,
            chunk_index=unique_index,
        )
        assert missing["provenance_status"] == PROVENANCE_CHUNK_UNMATCHED
        assert missing["chunk_provenance_match"] == "missing_chunk_id"
        assert missing["canonical_passage_id"] is None

        ambig = verify_chunk_provenance(
            raw_doc_id="papers/Vaswani2017.pdf",
            canonical_doc_id="papers/Vaswani2017.pdf",
            chunk_id="chunk_008",
            page_number=2,
            hf_url="/read?doc=papers%2FVaswani2017.pdf&page=2",
            text_passage="The Transformer uses stacked self-attention layers.",
            all_withdrawn=False,
            chunk_index=ambiguous_index,
        )
        assert ambig["provenance_status"] == PROVENANCE_CHUNK_AMBIGUOUS
        assert ambig["chunk_provenance_match"] == "ambiguous_chunk_id"
        assert ambig["canonical_passage_id"] is None

    def test_low_signal_passage_filters_appendix_index_and_bibliography(self) -> None:
        """Attention-vis word-per-line dumps, indexes, and bibliographies are flagged."""
        word_per_line = "\n".join(
            ["It", "is", "in", "this", "spirit", "that", "a", "majority", "of", "governments"]
        )
        index_dump = "assimilation, 34 production readiness, 32-33 remodeling, 34 response time, 33"
        bib_dump = "Bengio (2012). Theano. Cho (2014). GRU. Sutskever (2014). Seq2Seq."
        good_prose = (
            "The Transformer is the first sequence transduction model relying entirely "
            "on self-attention to compute representations of its input and output."
        )

        assert is_low_signal_passage(word_per_line) is True
        assert is_low_signal_passage(index_dump) is True
        assert is_low_signal_passage(bib_dump) is True
        assert is_low_signal_passage("Too short.") is True
        assert is_low_signal_passage(good_prose) is False
