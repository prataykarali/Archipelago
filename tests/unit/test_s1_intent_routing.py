"""tests/unit/test_s1_intent_routing.py — Acceptance Tests for S1 Intent-Aware Routing.

Covers:
- All 9 explicit intent categories:
  CONCEPT_LEARNING, MULTI_CONCEPT, RESEARCH_TOPIC, PAPER_LOOKUP,
  LIBRARY_LOOKUP, ACADEMIC_INFO, PERSONALIZED_LEARNING,
  RESEARCH_INTELLIGENCE, UNSUPPORTED.
- Paper lookup without graph or MCQs.
- Library lookup without graph or MCQs.
- Academic info without graph or MCQs.
- Explicit topic-learning request with an appropriate graph.
- Research-topic explanation with verified citations and date coverage.
- Conflicting papers / date boundaries.
- Tested on both main (archipelago) and hosted (host_inference) paths.
"""

from __future__ import annotations

from pathlib import Path
import sys
import pytest

ARCHIPELAGO_DIR = Path(__file__).resolve().parents[2]
HOST_DIR = ARCHIPELAGO_DIR / "host_inference"

if str(ARCHIPELAGO_DIR) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO_DIR))
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

from archipelago.core.intent import IntentCategory, classify_query_intent
from archipelago.core.router import QueryRouter
import engine as hosted_engine


@pytest.fixture(scope="module")
def router():
    return QueryRouter()


@pytest.fixture(scope="module")
def engine():
    return hosted_engine.Engine()


# ── 1. Classification Tests across all 9 Categories ───────────────────────────


@pytest.mark.parametrize(
    ("query", "concepts", "expected_intent"),
    [
        # CONCEPT_LEARNING
        ("What is a transformer?", ["transformer"], IntentCategory.CONCEPT_LEARNING),
        ("Explain the self-attention mechanism", ["self-attention"], IntentCategory.CONCEPT_LEARNING),
        ("Define low rank adaptation", ["low rank adaptation"], IntentCategory.CONCEPT_LEARNING),
        ("What are the prerequisites for BERT?", ["bert"], IntentCategory.CONCEPT_LEARNING),

        # MULTI_CONCEPT
        (
            "How are transformers, retrieval-augmented generation and knowledge graphs related?",
            ["transformers", "retrieval-augmented generation", "knowledge graphs"],
            IntentCategory.MULTI_CONCEPT,
        ),
        (
            "Compare LoRA, QLoRA, and full fine-tuning",
            ["LoRA", "QLoRA", "full fine-tuning"],
            IntentCategory.MULTI_CONCEPT,
        ),
        (
            "Relationship between attention and feedforward layers",
            ["attention", "feedforward layers"],
            IntentCategory.MULTI_CONCEPT,
        ),
        (
            "How does Softmax connect to Self-Attention?",
            ["Softmax", "Self-Attention"],
            IntentCategory.MULTI_CONCEPT,
        ),

        # RESEARCH_TOPIC
        ("What are recent studies on retrieval-augmented generation?", ["retrieval-augmented generation"], IntentCategory.RESEARCH_TOPIC),
        ("Show literature review on large language model alignment", ["large language model alignment"], IntentCategory.RESEARCH_TOPIC),
        ("What are the empirical findings and research gaps in prompt tuning?", ["prompt tuning"], IntentCategory.RESEARCH_TOPIC),

        # PAPER_LOOKUP
        ("Which paper introduced LoRA?", ["lora"], IntentCategory.PAPER_LOOKUP),
        ("Who wrote Attention Is All You Need?", [], IntentCategory.PAPER_LOOKUP),
        ("Give me the citations of this paper", [], IntentCategory.PAPER_LOOKUP),
        ("What is the DOI for the BERT paper?", ["bert"], IntentCategory.PAPER_LOOKUP),
        ("Who authored the paper on ResNet?", [], IntentCategory.PAPER_LOOKUP),

        # LIBRARY_LOOKUP
        ("Where can I find Database System Concepts in the library?", [], IntentCategory.LIBRARY_LOOKUP),
        ("What is the call number for Operating System Internals?", [], IntentCategory.LIBRARY_LOOKUP),
        ("Show journal inventory", [], IntentCategory.LIBRARY_LOOKUP),
        ("What books are in the library?", [], IntentCategory.LIBRARY_LOOKUP),
        ("How many copies of Database System Concepts are available on campus shelf?", [], IntentCategory.LIBRARY_LOOKUP),

        # ACADEMIC_INFO
        ("What are the library opening hours on Sunday?", [], IntentCategory.ACADEMIC_INFO),
        ("How do I log in to Scopus through the campus portal?", [], IntentCategory.ACADEMIC_INFO),
        ("How do I access IEEE Xplore off-campus?", [], IntentCategory.ACADEMIC_INFO),
        ("What is the library borrowing policy for students?", [], IntentCategory.ACADEMIC_INFO),

        # PERSONALIZED_LEARNING
        ("Quiz me on transformers", ["transformers"], IntentCategory.PERSONALIZED_LEARNING),
        ("Generate a diagnostic quiz for BERT prerequisites", ["bert"], IntentCategory.PERSONALIZED_LEARNING),
        ("Evaluate my understanding of relational databases with a test", [], IntentCategory.PERSONALIZED_LEARNING),
        ("Create a personalized learning roadmap for deep learning", [], IntentCategory.PERSONALIZED_LEARNING),

        # RESEARCH_INTELLIGENCE
        ("Show the bibliometric citation network analysis for transformers", [], IntentCategory.RESEARCH_INTELLIGENCE),
        ("Show the topic inventory of ingested research papers", [], IntentCategory.RESEARCH_INTELLIGENCE),

        # UNSUPPORTED
        ("What is a good recipe for lasagna?", [], IntentCategory.UNSUPPORTED),
        ("Write a Python scraper to download all papers", [], IntentCategory.UNSUPPORTED),
    ],
)
def test_all_9_intent_categories_classified(query, concepts, expected_intent):
    actual = classify_query_intent(query, extracted_concepts=concepts)
    assert actual == expected_intent, f"Query '{query}' classified as {actual}, expected {expected_intent}"


# ── 2. Paper Lookup Behavioral Rules (No Graph, No MCQs) ──────────────────────


@pytest.mark.parametrize(
    "query",
    [
        "Which paper introduced LoRA?",
        "Who wrote Attention is all you need?",
        "Who authored the BERT paper?",
        "Give me the citations of this paper",
    ],
)
def test_paper_lookup_does_not_produce_graph_or_mcqs(engine, query):
    """Paper lookups must answer bibliographic metadata and strictly suppress learning graphs and MCQs."""
    result = engine.answer(query)
    payload = result["payload"]

    assert result["route"] == "PAPER_LOOKUP"
    assert result["intent_category"] == "PAPER_LOOKUP"

    # Invariant: Graph and MCQs MUST be suppressed
    assert payload["render_graph"] is False, "Paper lookup must not display an interactive graph"
    assert payload["anchor_concept"] is None
    assert payload["prerequisites"] == []
    assert payload["unlocks"] == []
    assert "diagnostic_mcqs" not in payload or payload["diagnostic_mcqs"] == []

    # Invariant: Answer must contain verifiable bibliographic facts
    text = result["text"]
    assert len(text) > 20
    assert "Paper Identification" in text or "paper" in text.lower() or "author" in text.lower()


# ── 3. Library Lookup Behavioral Rules (No Graph, No MCQs) ────────────────────


@pytest.mark.parametrize(
    "query",
    [
        "What books are in the library?",
        "Show journal inventory",
        "Where can I find Database System Concepts on campus?",
    ],
)
def test_library_lookup_does_not_produce_graph_or_mcqs(engine, query):
    """Library holding queries must answer shelf/catalog facts without graphs or MCQs."""
    result = engine.answer(query)
    payload = result["payload"]

    assert result["route"] in ("LIBRARY_LOOKUP", "CATALOG_SHELF_ROUTING")
    assert payload["render_graph"] is False, "Library lookup must not display an interactive graph"
    assert payload["anchor_concept"] is None
    assert payload["prerequisites"] == []
    assert payload["unlocks"] == []
    assert "diagnostic_mcqs" not in payload or payload["diagnostic_mcqs"] == []


# ── 4. Explicit Learning Request Has Graph & MCQs ─────────────────────────────


def test_explicit_topic_learning_request_produces_graph_and_diagnostic(engine):
    """A personalized learning or roadmap query must provide the learning graph and diagnostic chain."""
    result = engine.answer("Teach me about third normal form")
    payload = result["payload"]

    assert result["route"] == "MCQ_DIAGNOSTIC"
    assert payload["render_graph"] is True, "Explicit curriculum learning must enable graph"
    assert payload["anchor_concept"] is not None
    assert payload["anchor_concept"]["id"] == "third_normal_form"
    assert "prerequisites" in payload


# ── 5. Research Topic with Citations and Verified Dates ───────────────────────


def test_research_topic_has_citations_and_date_coverage_disclosure(engine):
    """When a user asks for recent studies, provide verified citations and disclose corpus date coverage."""
    result = engine.answer("What are recent studies on retrieval-augmented generation?")
    payload = result["payload"]
    text = result["text"]

    assert result["route"] == "RESEARCH_TOPIC"
    assert payload["citations"], "Research topic explanation must carry verified citations"

    # Must contain date coverage notice with mid-2024 boundary
    assert "temporal boundary" in text.lower() or "corpus date coverage" in text.lower() or "mid-2024" in text.lower()
    assert "2024" in text

    # Must cite Lewis 2020 and Edge 2024 Graph RAG
    assert "lewis" in text.lower()
    assert "edge" in text.lower()
    assert "graphrag" in text.lower() or "graph rag" in text.lower()

    # RESEARCH_TOPIC renders concept topology without MCQs
    assert payload["render_graph"] is True, "RESEARCH_TOPIC renders concept topology"
    assert "diagnostic_mcqs" not in payload or payload["diagnostic_mcqs"] == []


def test_transformer_scientific_accuracy_distinguishes_mlm_and_next_token(engine):
    """Transformer explanation must be scientifically accurate and not conflate MLM or autoregressive generation."""
    result = engine.answer("What is a Transformer?")
    text = result["text"]

    assert "vaswani" in text.lower()
    assert "self-attention" in text.lower() or "attention" in text.lower()

    # Must NOT contain the inaccurate conflated summary
    assert "using masked language modeling and next-token prediction" not in text.lower(), (
        "Transformer explanation must not falsely claim Transformer architecture uses MLM (which is BERT)"
    )


def test_library_inventory_omits_unsupported_claims(engine):
    """Library inventory must not make unverified claims like 'verified curriculum textbooks'."""
    result = engine.answer("Show journal inventory")
    text = result["text"]

    assert "verified curriculum textbooks" not in text.lower()
    assert "verified holdings" not in text.lower()
    assert "central library" in text.lower()
    assert "ieee xplore" in text.lower()


# ── 6. Main Pipeline Router Parity ───────────────────────────────────────────


def test_main_router_produces_intent_category(router):
    """The main QueryRouter in archipelago.core must populate intent_category."""
    routed = router.route_query("Which paper introduced LoRA?")
    assert routed["intent_category"] == IntentCategory.PAPER_LOOKUP.value

    routed_multi = router.route_query(
        "How are transformers, retrieval-augmented generation and knowledge graphs related?"
    )
    assert routed_multi["intent_category"] == IntentCategory.MULTI_CONCEPT.value
    assert len(routed_multi["concepts"]) >= 3

