"""Unit tests for D12 retrieval, NLU, graph semantics, and contextual follow-ups.

Covers all systemic defects and unseen paraphrases without hardcoded query answers:
1. Query understanding & concept resolution (operation separation, phrase parsing,
   uncertainty-based rejection).
2. Domain-aware retrieval & evidence grounding (cross-domain pollution prevention,
   legitimate interdisciplinary retrieval, zero-padding honest abstention, paging priority).
3. Graph semantics (cross-domain noise quarantine, inverted generic prerequisites,
   contradictory cycles, Paging/Virtual Memory/Address Translation direction).
4. Contextual follow-ups (domain-consistent neighbors & citations, intent awareness,
   max-3 fallback bank preservation).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest

HOST_INFERENCE_DIR = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST_INFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_INFERENCE_DIR))

from engine import compose  # noqa: E402
from engine.answer import Engine  # noqa: E402
from engine.evidence_selection import (  # noqa: E402
    DOMAIN_DB,
    DOMAIN_DSA,
    DOMAIN_MATH,
    DOMAIN_ML_AI,
    DOMAIN_NETWORKS,
    DOMAIN_OS,
    domains_compatible,
    infer_doc_domains,
    infer_text_domains,
    select_catalog_passages,
    select_evidence_citations,
)
from engine.followups import build_follow_up_questions  # noqa: E402
from engine.graph import LibraryGraph  # noqa: E402
from engine.intent import (  # noqa: E402
    clean_concept_fragment,
    extract_clean_concept_clause,
    is_operation_fragment,
    strip_requested_operations,
)
from engine.suggestions import NON_AI_FALLBACK_SUGGESTION_COUNT  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def full_engine() -> Engine:
    """Loaded hosted Engine backed by the repository graph fixture."""
    return Engine()


# ── 1. Query Understanding & Concept Resolution ────────────────────────────────


def test_strip_requested_operations_separates_concepts_from_modifiers() -> None:
    clause, ops = strip_requested_operations("Explain Third Normal Form (3NF) with an example")
    assert clause == "Explain Third Normal Form (3NF)"
    assert "with_example" in ops
    assert "explain" in ops

    clause2, ops2 = strip_requested_operations(
        "What is the difference between TCP and UDP? Explain their reliability"
    )
    assert clause2 == "What is the difference between TCP and UDP?"
    assert "follow_on_instruction" in ops2

    # Unseen paraphrases
    clause3, ops3 = strip_requested_operations(
        "Derive Bayes theorem step by step and give a worked example"
    )
    assert "example" not in clause3.lower()
    assert "step" not in clause3.lower()
    assert "bayes theorem" in clause3.lower()
    assert "derive" in ops3

    clause4, ops4 = strip_requested_operations(
        "Compare TCP versus UDP. Discuss their trade-offs and performance"
    )
    assert clause4 == "Compare TCP versus UDP."
    assert "follow_on_instruction" in ops4


def test_operation_fragments_are_rejected_and_cleaned() -> None:
    assert is_operation_fragment("with an example")
    assert is_operation_fragment("example")
    assert is_operation_fragment("a concrete worked example")
    assert is_operation_fragment("step by step")
    assert is_operation_fragment("Explain their reliability")
    assert not is_operation_fragment("Third Normal Form (3NF)")
    assert not is_operation_fragment("UDP")
    assert not is_operation_fragment("Priority Queue")

    assert clean_concept_fragment("UDP? Explain their reliability") == "UDP"
    assert clean_concept_fragment("Third Normal Form (3NF) with an example") == "Third Normal Form (3NF)"


def test_fast_recovery_does_not_resolve_to_fast_or_flashattention(full_engine: Engine) -> None:
    g = full_engine.graph
    for query in (
        "Explain TCP congestion control (Slow Start, Congestion Avoidance, Fast Recovery)",
        "What is Fast Recovery in TCP?",
        "How does fast recovery avoid resetting cwnd to one segment?",
    ):
        hits = g.phrase_hits(query)
        assert "fast" not in hits
        assert "flashattention" not in hits
        res = full_engine.answer(query)
        assert res["anchor"] != "fast"
        assert res["anchor"] != "flashattention"
        for cite in res["payload"].get("citations") or []:
            doc_id = str(cite.get("doc_id") or "").lower()
            assert "flashattention" not in doc_id
            assert "dao2022" not in doc_id

    cc_res = full_engine.answer(
        "Explain TCP congestion control (Slow Start, Congestion Avoidance, Fast Recovery)"
    )
    assert cc_res["anchor"] == "tcp_congestion_control"
    assert cc_res["route"] == "GRAPH_SYNTHESIS"


def test_with_an_example_never_becomes_missing_concept(full_engine: Engine) -> None:
    for query in (
        "Explain Third Normal Form (3NF) with an example",
        "Define 3NF and give a concrete example",
        "Explain ACID properties step by step with a worked example",
    ):
        res = full_engine.answer(query)
        assert res["route"] != "MULTI_CONCEPT"
        multi_hop = res["payload"].get("multi_hop") or {}
        missing = [str(m).lower() for m in multi_hop.get("missing") or []]
        assert not any("example" in m for m in missing)


def test_tcp_vs_udp_trailing_clause_split_cleanly(full_engine: Engine) -> None:
    query = "What is the difference between TCP and UDP? Explain their reliability"
    clean_clause = extract_clean_concept_clause(query)
    pair = compose.split_pair(clean_clause)
    assert pair is not None
    assert clean_concept_fragment(pair[0]) == "TCP"
    assert clean_concept_fragment(pair[1]) == "UDP"

    # Unseen paraphrase
    paraphrase = "Compare TCP and UDP? Demonstrate their congestion behavior"
    pair2 = compose.split_pair(extract_clean_concept_clause(paraphrase))
    assert pair2 is not None
    assert clean_concept_fragment(pair2[0]) == "TCP"
    assert clean_concept_fragment(pair2[1]) == "UDP"

    res = full_engine.answer(query)
    assert "UDP? Explain their reliability" not in res["text"]
    assert res["payload"]["citations"] == []


def test_arrays_and_linked_lists_never_resolve_to_data(full_engine: Engine) -> None:
    g = full_engine.graph
    for query in (
        "Compare arrays and linked lists",
        "Compare arrays and linked lists data structures",
        "How do dynamic arrays differ from singly linked lists?",
    ):
        assert "data" not in g.phrase_hits(query)
        res = full_engine.answer(query)
        assert res["anchor"] != "data"
        assert res["payload"]["citations"] == []


def test_priority_queue_and_binary_heap_resolve_cleanly(full_engine: Engine) -> None:
    g = full_engine.graph
    assert "priority_queue_mechanics" in g.phrase_hits("Explain priority queue and binary heap")
    assert "priority_queue_mechanics" in g.phrase_hits("What is a priority queue?")
    assert "binary_classification" not in g.phrase_hits("Explain priority queue and binary heap")

    res = full_engine.answer("Explain priority queue and binary heap")
    assert res["anchor"] == "priority_queue_mechanics"
    for cite in res["payload"].get("citations") or []:
        doc_id = str(cite.get("doc_id") or "").lower()
        assert "real-time network security" not in doc_id


def test_paging_resolves_to_paging_not_virtual_memory(full_engine: Engine) -> None:
    for query in (
        "Explain paging in operating systems",
        "How does paging work in virtual memory?",
        "Explain virtual memory paging and page tables",
    ):
        res = full_engine.answer(query)
        assert res["anchor"] == "paging"
        cites = res["payload"].get("citations") or []
        assert cites
        assert "08_paging" in str(cites[0].get("doc_id") or "").lower()


def test_uncertainty_based_rejection_of_weak_matches(full_engine: Engine) -> None:
    g = full_engine.graph
    assert not g.is_confident_match(0.42, "factuality", "What is Fast Recovery in TCP?")
    assert not g.is_confident_match(0.95, "fast", "What is Fast Recovery in TCP?")
    assert not g.is_confident_match(0.95, "translation", "Explain OS address translation")
    assert g.is_confident_match(0.95, "paging", "Explain paging in operating systems")

    res = full_engine.answer("What is Fast Recovery in TCP?")
    assert res["anchor"] is None
    assert res["route"] == "GENERAL_EXPLANATION"
    assert res["payload"]["citations"] == []


# ── 2. Domain-Aware Retrieval & Evidence Grounding ─────────────────────────────


def _mock_catalog_with_cross_domain_distractors() -> SimpleNamespace:
    """Simulated catalog mirroring the 3,025-passage OSTEP + ML + Math + 3NF card mix."""
    passages = [
        {
            "doc_id": "books/papers/Yao2022_ReAct.pdf",
            "page": 3,
            "passage_id": "react_p3",
            "text": (
                "ReAct interleaves reasoning traces and task-specific actions in a normal "
                "form state transition loop for language agents with consistency checks."
            ),
        },
        {
            "doc_id": "books/papers/Yao2022_ReAct.pdf",
            "page": 8,
            "passage_id": "react_p8",
            "text": (
                "We evaluate ReAct properties on HotpotQA and Fever benchmarks comparing "
                "normal action sequences and third-party tool feedback."
            ),
        },
        {
            "doc_id": "pilot/silberschatz_3nf_card.txt",
            "page": 1,
            "passage_id": "3nf_card",
            "text": (
                "Third Normal Form (3NF) removes transitive dependencies in relational database "
                "tables using linked attribute lists and ordered key arrays."
            ),
        },
        {
            "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/15_RAID.pdf",
            "page": 4,
            "passage_id": "raid_p4",
            "text": (
                "RAID improves disk reliability and fault tolerance across block arrays using "
                "parity striping and checksums for reliable storage transfer."
            ),
        },
        {
            "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/16_Log_Structured_FS.pdf",
            "page": 5,
            "passage_id": "lfs_p5",
            "text": (
                "Log-structured file systems buffer writes sequentially in segments to improve "
                "throughput and reliability during crash recovery."
            ),
        },
        {
            "doc_id": "books/textbooks/Deisenroth_Math_For_ML.pdf",
            "page": 225,
            "passage_id": "deisenroth_p225",
            "text": (
                "Constrained optimization uses Lagrange multipliers to solve primal and dual "
                "problems, and singular value decomposition (SVD) factorizes matrices."
            ),
        },
        {
            "doc_id": "books/papers/Brown2020_GPT3.pdf",
            "page": 7,
            "passage_id": "gpt3_p7",
            "text": (
                "GPT-3 is a 175B parameter autoregressive language model with 96 transformer "
                "layers trained on internet text."
            ),
        },
        {
            "doc_id": "books/papers/Velickovic2017_GAT.pdf",
            "page": 3,
            "passage_id": "gat_p3",
            "text": (
                "Graph Attention Networks stack masked self-attention layers in a neural "
                "network model over graph-structured neighborhoods."
            ),
        },
        {
            "doc_id": "books/papers/Dao2022_FlashAttention.pdf",
            "page": 1,
            "passage_id": "flash_p1",
            "text": (
                "FlashAttention achieves fast and memory-efficient exact attention using "
                "tiling and IO-aware SRAM control."
            ),
        },
        {
            "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf",
            "page": 1,
            "passage_id": "addr_p1",
            "text": (
                "The Abstraction: Address Spaces. In the early days, building computer systems "
                "was easy before virtual memory and paging existed."
            ),
        },
        {
            "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
            "page": 3,
            "passage_id": "paging_p3",
            "text": (
                "Paging divides virtual address space into fixed-sized pages and maps virtual "
                "page numbers to physical page frames via a per-process page table."
            ),
        },
        {
            "doc_id": "books/papers/Kwon2023_vLLM.pdf",
            "page": 4,
            "passage_id": "vllm_p4",
            "text": (
                "PagedAttention is inspired by OS virtual memory and paging to manage KV cache "
                "blocks non-contiguously for LLM serving."
            ),
        },
    ]
    return SimpleNamespace(passages=passages)


def test_cross_domain_catalog_pollution_is_blocked_with_honest_empty_list() -> None:
    catalog = _mock_catalog_with_cross_domain_distractors()

    # 3NF & ACID must NOT retrieve ReAct pages 3 and 8.
    cites_acid = select_catalog_passages(
        catalog, "Explain ACID properties in DBMS", concept_label="ACID Properties", anchor_cid="acid_properties"
    )
    assert all("react" not in str(c.get("doc_id") or "").lower() for c in cites_acid)
    assert cites_acid == []

    # Arrays and linked lists must NOT retrieve 3NF text card.
    cites_dsa = select_catalog_passages(
        catalog, "Compare arrays and linked lists", concept_label="Arrays and Linked Lists"
    )
    assert cites_dsa == []

    # TCP and UDP must NOT retrieve RAID, Log-Structured FS, or constrained optimization.
    cites_tcp_udp = select_catalog_passages(
        catalog, "What is the difference between TCP and UDP? Explain their reliability"
    )
    assert cites_tcp_udp == []

    # OSI must NOT retrieve GPT-3 or Graph Attention Networks.
    cites_osi = select_catalog_passages(
        catalog, "Explain the OSI model layers", concept_label="OSI Model", anchor_cid="osi_model"
    )
    assert cites_osi == []

    # TCP congestion control must NOT retrieve FlashAttention.
    cites_cc = select_catalog_passages(
        catalog,
        "Explain TCP congestion control (Slow Start, Congestion Avoidance, Fast Recovery)",
        concept_label="TCP Congestion Control",
        anchor_cid="tcp_congestion_control",
    )
    assert cites_cc == []


def test_paging_prioritizes_substantive_paging_over_address_space_intro() -> None:
    catalog = _mock_catalog_with_cross_domain_distractors()
    cites = select_catalog_passages(
        catalog,
        "Explain paging and page tables in operating systems",
        concept_label="Paging",
        anchor_cid="paging",
    )
    assert cites
    assert "08_paging" in str(cites[0].get("doc_id") or "").lower()


def test_legitimate_interdisciplinary_retrieval_is_preserved() -> None:
    catalog = _mock_catalog_with_cross_domain_distractors()

    # OS + ML_AI interdisciplinary query (PagedAttention + OS paging)
    cites_vllm = select_catalog_passages(
        catalog,
        "How does PagedAttention use OS virtual memory paging for KV cache?",
        concept_label="PagedAttention",
        anchor_cid="paged_attention",
    )
    docs = {str(c.get("doc_id") or "").lower() for c in cites_vllm}
    assert any("vllm" in d for d in docs)

    # MATH + ML_AI interdisciplinary query (SVD in machine learning)
    cites_svd = select_catalog_passages(
        catalog,
        "Explain singular value decomposition (SVD) in machine learning",
        concept_label="SVD",
    )
    assert any("deisenroth" in str(c.get("doc_id") or "").lower() for c in cites_svd)

    assert domains_compatible({DOMAIN_MATH}, {DOMAIN_ML_AI})
    assert not domains_compatible({DOMAIN_DB}, {DOMAIN_ML_AI})
    assert not domains_compatible({DOMAIN_NETWORKS}, {DOMAIN_OS})
    assert not domains_compatible({DOMAIN_DSA}, {DOMAIN_DB})
    assert DOMAIN_OS in infer_text_domains("Explain paging in virtual memory")
    assert DOMAIN_ML_AI in infer_doc_domains("books/papers/Yao2022_ReAct.pdf")


# ── 3. Graph Semantics ─────────────────────────────────────────────────────────


def test_graph_quarantines_cross_domain_inverted_and_contradictory_edges(
    full_engine: Engine, tmp_path: Path
) -> None:
    g = full_engine.graph

    # TCP -> Constitutional Principle quarantined
    assert "constitutional_principle" not in g.related("tcp")
    # Data -> advanced ML prerequisites quarantined
    assert g.prereqs("data", 1) == []
    # Paging <-> Virtual Memory <-> Address Translation inverted edge quarantined
    assert "address_translation" not in g.prereqs("virtual_memory", 1)
    assert "address_translation" not in g.prereqs("paging", 2)
    assert "virtual_memory" in g.prereqs("paging", 2)
    # Noise unigram edges quarantined
    assert not g.out.get("fast")
    # Every quarantined edge preserves pending-review labeling
    assert g.quarantined_edges
    assert all("review" in str(e.get("quarantine_reason") or "").lower() for e in g.quarantined_edges)

    # Contradictory directional edges (both REQUIRES and UNLOCKS same direction) quarantined
    graph_path = tmp_path / "contradictory_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "concept_a", "label": "Transformer", "summary": "Attention model."},
                    {"id": "concept_b", "label": "Self-Attention", "summary": "Attention layer."},
                ],
                "edges": [
                    {"from_id": "concept_a", "to_id": "concept_b", "edge_type": "REQUIRES"},
                    {"from_id": "concept_a", "to_id": "concept_b", "edge_type": "UNLOCKS"},
                ],
            }
        ),
        encoding="utf-8",
    )
    sg = LibraryGraph(graph_path)
    assert sg.prereqs("concept_a", 1) == []
    assert sg.unlocks("concept_a", 1) == []
    assert len(sg.quarantined_edges) == 2


# ── 4. Contextual Follow-Ups ───────────────────────────────────────────────────


def test_followups_reject_cross_domain_neighbors_and_unrelated_citations(
    full_engine: Engine,
) -> None:
    g = full_engine.graph
    # Inject noisy cross-domain neighbor and unrelated OS chapter citation into a TCP payload.
    poisoned_payload: dict[str, Any] = {
        "anchor_concept": {"id": "tcp", "label": "TCP"},
        "prerequisites": [],
        "unlocks": [],
        "related_concepts": [
            {"id": "constitutional_principle", "label": "Constitutional Principle"},
            {"id": "flow_control", "label": "Flow Control"},
        ],
        "citations": [
            {
                "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/15_RAID.pdf",
                "doc_title": "OSTEP Chapter 15: RAID",
                "text_passage": "RAID improves disk reliability across storage arrays.",
                "withdrawn": False,
            }
        ],
    }
    followups = build_follow_up_questions(
        g, poisoned_payload, "Explain TCP with an example", "GRAPH_SYNTHESIS"
    )
    joined = " | ".join(followups).lower()
    assert "constitutional principle" not in joined
    assert "raid" not in joined
    # Respects user intent: user already asked "with an example"
    assert "walk through a concrete example" not in joined
    # Keeps valid domain-consistent neighbor
    assert any("flow control" in f.lower() for f in followups)


def test_followups_preserve_max_3_fallback_bank_for_non_ai_and_unanchored_turns(
    full_engine: Engine,
) -> None:
    g = full_engine.graph
    fallback_oob = build_follow_up_questions(
        g,
        {"anchor_concept": None, "citations": []},
        "How do I cook lasagna?",
        "GUARDRAIL_INTERCEPT",
        reason="out_of_scope",
    )
    assert len(fallback_oob) <= NON_AI_FALLBACK_SUGGESTION_COUNT

    fallback_unanchored = build_follow_up_questions(
        g,
        {"anchor_concept": None, "citations": []},
        "Compare arrays and linked lists",
        "GENERAL_EXPLANATION",
        reason="academic_comparison_general",
    )
    assert len(fallback_unanchored) <= NON_AI_FALLBACK_SUGGESTION_COUNT


def test_select_evidence_citations_filters_cross_domain_node_sources(tmp_path: Path) -> None:
    graph_path = tmp_path / "mixed_sources.json"
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "tcp_congestion_control",
                        "label": "TCP Congestion Control",
                        "summary": "Congestion control in TCP using slow start and fast recovery.",
                        "sources": [
                            {
                                "doc_id": "papers/Dao2022_FlashAttention.pdf",
                                "page_number": 1,
                                "text_passage": "FlashAttention: Fast and memory-efficient exact attention.",
                            }
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    sg = LibraryGraph(graph_path)
    cites = select_evidence_citations(sg, "tcp_congestion_control", "Explain TCP congestion control")
    assert cites == []
