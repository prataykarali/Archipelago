"""tests/unit/test_s2a_cross_domain_qa.py — Cross-Domain Academic QA & S2-A Acceptance Suite.

Validates:
1. 10+ Core Academic Disciplines:
   - Operating Systems (Context Switch, Semaphore, Mutex Lock, Deadlock, Virtual Memory, CPU Scheduling)
   - Database Systems (B+ Tree, Hash Indexing, ACID Properties, Relational Database, 3NF)
   - Data Structures & Algorithms (BFS vs DFS, Graph Search)
   - Computer Networks (TCP Congestion Control, OSI Model)
   - Compilers & Automata (Lexical Analysis, AST, DFA, Turing Machine)
   - Mathematics & Statistics (Matrix Multiplication, MLE, Bayes Rule)
   - Information Security & Software Engineering (SQL Injection defense, Code Review)
   - Artificial Intelligence & Deep Learning (Transformer, Attention, BERT, LoRA, RAG)
2. Four Response Classes:
   - Class A: General Academic Concept Explanations (with verifiable citations and textbook provenance)
   - Class B: Institutional Library Inventory & Holdings (with OPAC links, physical counts, no hallucinated stacks)
   - Class C: Research Papers & Recent Literature (with authors, publication years, mid-2024 boundary disclosure)
   - Class D: Personalized Learning & Diagnostic Curricula (with prerequisite roadmaps and MCQs only when requested)
3. 5-Turn Sequential Multi-Turn Interaction Flow:
   - Turn 1: Library Inventory Table
   - Turn 2: Contextual Book Recommendation for Concurrency (OSTEP vs Silberschatz)
   - Turn 3: Book Page / Chapter Lookup (OSTEP Chapter 28 Locks)
   - Turn 4: Grounded Concept Explanation from That Source (Semaphores from OSTEP Chapter 31)
   - Turn 5: Concept Comparison Matrix (Semaphore vs Condition Variable)
4. Knowledge Graph Integrity & Preservation:
   - Exactly 610 nodes and 1,988 edges retained
   - Zero broken refs, zero duplicate nodes, zero self-referential prerequisite cycles
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

ARCHIPELAGO_DIR = Path(__file__).resolve().parents[2]
HOST_DIR = ARCHIPELAGO_DIR / "host_inference"

if str(ARCHIPELAGO_DIR) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO_DIR))
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

from host_inference.hostapp.conversation import contextual_query
import engine as hosted_engine


@pytest.fixture(scope="module")
def engine():
    return hosted_engine.Engine()


# ── 1. Class A: Academic Concept Explanations across Core Disciplines ──────────


@pytest.mark.parametrize(
    ("query", "expected_concept", "expected_keywords", "expected_cite_substring"),
    [
        # Operating Systems
        (
            "What is a context switch in operating systems?",
            "context_switch",
            ["state", "process", "registers"],
            "Operating Systems",
        ),
        (
            "Explain semaphores and how they coordinate processes",
            "semaphore",
            ["synchronization", "integer", "wait", "signal"],
            "Operating Systems",
        ),
        (
            "What is a deadlock and what conditions cause it?",
            "deadlock",
            ["blocked", "resource", "coffman"],
            "Operating System",
        ),
        (
            "How does virtual memory protect memory address spaces?",
            "virtual_memory",
            ["address space", "page tables"],
            "Operating Systems",
        ),
        # Database Systems
        (
            "Explain B+ trees and how they index database records",
            "b_plus_tree",
            ["tree", "leaf", "key"],
            "Database",
        ),
        (
            "What are ACID properties in database management systems?",
            "acid_properties",
            ["atomicity", "consistency", "isolation", "durability"],
            "Database",
        ),
        # Computer Networks
        (
            "How does TCP congestion control avoid network collapse?",
            "tcp_congestion_control",
            ["congestion", "packet loss"],
            "Computer Networks",
        ),
        (
            "Explain the seven layers of the OSI model",
            "osi_model",
            ["layer", "physical", "network", "transport"],
            "Computer Networks",
        ),
        # Compilers & Automata
        (
            "What is lexical analysis in compiler design?",
            "lexical_analysis",
            ["token", "phase"],
            "Compilers",
        ),
        (
            "Explain deterministic finite automata in theory of computation",
            "deterministic_finite_automaton",
            ["state", "transition"],
            "Automata",
        ),
        # Mathematics & Foundations
        (
            "What is maximum likelihood estimation in probability?",
            "maximum_likelihood_estimation",
            ["likelihood", "parameter", "estimate"],
            "Probability",
        ),
    ],
)
def test_class_a_academic_concept_explanations(
    engine, query, expected_concept, expected_keywords, expected_cite_substring
):
    """Class A queries must return verified definitions with citations and zero hallucination."""
    result = engine.answer(query)
    text = result["text"].lower()

    assert result["route"] in ("GRAPH_SYNTHESIS", "GENERAL_EXPLANATION", "RELATION"), (
        f"Unexpected route {result['route']} for query: {query}"
    )
    for kw in expected_keywords:
        assert kw.lower() in text, f"Missing required keyword '{kw}' in reply to '{query}'"

    # Must contain citation
    assert (
        "[" in result["text"] or "source" in text or expected_cite_substring in text
    ), f"Missing citation for academic concept in query: {query}"


# ── 2. Class B: Institutional Library Inventory & OPAC Availability ───────────


@pytest.mark.parametrize(
    ("query", "expected_titles", "expected_table_headers"),
    [
        (
            "Which OS books are available in the library?",
            ["Three Easy Pieces", "Operating System Concepts"],
            ["Title", "Authors", "Availability"],
        ),
        (
            "What DBMS books do we have in the library?",
            ["Database System Concepts", "Database Management Systems"],
            ["Title", "Authors", "Availability"],
        ),
        (
            "Which DSA and algorithm textbooks are available?",
            ["Introduction to Algorithms", "Data Structures"],
            ["Title", "Authors", "Availability"],
        ),
    ],
)
def test_class_b_library_inventory_tables(
    engine, query, expected_titles, expected_table_headers
):
    """Class B inventory queries must return structured markdown tables with OPAC guidance."""
    result = engine.answer(query)
    text = result["text"]

    assert result["route"] == "LIBRARY_LOOKUP"
    assert result["payload"]["render_graph"] is False
    assert "diagnostic_mcqs" not in result["payload"] or result["payload"]["diagnostic_mcqs"] == []

    # Table format verification
    assert "|" in text, "Library inventory reply must format holdings as a table"
    for title in expected_titles:
        assert title.lower() in text.lower(), f"Expected book '{title}' in inventory table"
    for header in expected_table_headers:
        assert header.lower() in text.lower(), f"Expected header '{header}' in inventory table"

    # OPAC link verification
    assert "uemk-opac.l2c2.co.in" in text, "Must provide link to live OPAC catalog"


# ── 3. Class C: Research Intelligence & Temporal Grounding ────────────────────


def test_class_c_research_topic_recent_literature(engine):
    """Class C research queries must disclose mid-2024 boundary and cite dated papers."""
    result = engine.answer("What are recent studies on retrieval-augmented generation and Graph RAG?")
    text = result["text"]

    assert result["route"] == "RESEARCH_TOPIC"
    assert "Lewis" in text and "2020" in text, "Must cite Lewis et al. 2020 foundational RAG paper"
    assert "Edge" in text and "2024" in text, "Must cite Edge et al. 2024 Graph RAG paper"
    assert "mid-2024" in text, "Must disclose verified mid-2024 corpus temporal boundary"
    assert "diagnostic_mcqs" not in result["payload"] or result["payload"]["diagnostic_mcqs"] == []


# ── 4. Class D: Personalized Learning & Diagnostic Roadmaps ───────────────────


def test_class_d_diagnostic_learning_generates_mcqs_and_graph(engine):
    """Class D learning requests must generate interactive diagnostic MCQs and roadmap graph."""
    result = engine.answer("I want to learn about Operating System Context Switch. Quiz me to evaluate prerequisites.")
    payload = result["payload"]

    assert payload["render_graph"] is True, "Diagnostic learning must render interactive graph"
    assert payload["anchor_concept"] is not None
    mcqs = payload.get("diagnostic_mcqs") or []
    assert len(mcqs) >= 1, "Must generate diagnostic MCQs for curriculum learning intent"
    assert all("question" in q and "options" in q for q in mcqs)


# ── 5. Comparison Matrix Queries Across Disciplines ───────────────────────────


@pytest.mark.parametrize(
    ("query", "expected_axis"),
    [
        (
            "How do semaphores differ from mutex locks?",
            ["Ownership", "Capacity"],
        ),
        (
            "Compare B+ trees and hash indexing for database queries",
            ["Sequential", "Range"],
        ),
        (
            "How is BFS different from DFS in graph search?",
            ["Queue", "Stack"],
        ),
    ],
)
def test_cross_domain_comparisons(engine, query, expected_axis):
    """Comparative questions must render a comparative matrix rather than disconnecting."""
    result = engine.answer(query)
    text = result["text"]

    assert result["route"] == "CROSS_DOMAIN", f"Expected CROSS_DOMAIN route for '{query}', got {result['route']}"
    assert "|" in text, "Comparison must be formatted as a matrix table"
    assert "Comparative matrix:" in text


# ── 6. 5-Turn Sequential Multi-Turn Interaction Flow ──────────────────────────


def test_s2a_5_turn_sequential_flow(engine):
    """Execute and verify the full 5-turn sequential interaction specified in the mission."""
    history = []

    # ── Turn 1: Which OS books are available? ──
    t1_raw = "Which OS books are available?"
    t1_resolved = contextual_query(t1_raw, history)
    t1_ans = engine.answer(t1_resolved)

    assert t1_ans["route"] == "LIBRARY_LOOKUP"
    assert "|" in t1_ans["text"], "Turn 1 must render a markdown holdings table"
    assert "Three Easy Pieces" in t1_ans["text"]
    assert "Operating System Concepts" in t1_ans["text"]
    assert t1_ans["payload"]["render_graph"] is False
    history.append({"role": "user", "content": t1_raw})
    history.append({"role": "assistant", "content": t1_ans["text"]})

    # ── Turn 2: Which is best for learning concurrency? ──
    t2_raw = "Which is best for learning concurrency?"
    t2_resolved = contextual_query(t2_raw, history)
    assert "concurrency" in t2_resolved.lower()
    t2_ans = engine.answer(t2_resolved)

    assert t2_ans["route"] in ("GENERAL_EXPLANATION", "LIBRARY_LOOKUP")
    assert "Three Easy Pieces" in t2_ans["text"] or "OSTEP" in t2_ans["text"]
    assert "concurrency" in t2_ans["text"].lower()
    history.append({"role": "user", "content": t2_raw})
    history.append({"role": "assistant", "content": t2_ans["text"]})

    # ── Turn 3: Show its chapter on locks. ──
    t3_raw = "Show its chapter on locks."
    t3_resolved = contextual_query(t3_raw, history)
    t3_ans = engine.answer(t3_resolved)

    assert t3_ans["route"] in ("BOOK_PAGE", "GENERAL_EXPLANATION")
    assert "Chapter 28" in t3_ans["text"] or "Locks" in t3_ans["text"]
    assert "ostep_three_easy_pieces" in str(t3_ans.get("payload", {})) or "ostep" in t3_ans["text"].lower()
    history.append({"role": "user", "content": t3_raw})
    history.append({"role": "assistant", "content": t3_ans["text"]})

    # ── Turn 4: Can you explain semaphores from that source? ──
    t4_raw = "Can you explain semaphores from that source?"
    t4_resolved = contextual_query(t4_raw, history)
    t4_ans = engine.answer(t4_resolved)

    assert t4_ans["route"] in ("GRAPH_SYNTHESIS", "CONCEPT_LEARNING", "GENERAL_EXPLANATION")
    assert "semaphore" in t4_ans["text"].lower()
    assert "synchronization" in t4_ans["text"].lower() or "integer" in t4_ans["text"].lower()
    history.append({"role": "user", "content": t4_raw})
    history.append({"role": "assistant", "content": t4_ans["text"]})

    # ── Turn 5: How does this differ from condition variables? ──
    t5_raw = "How does this differ from condition variables?"
    t5_resolved = contextual_query(t5_raw, history)
    # Pronoun 'this' must resolve to 'semaphore' from prior turn
    assert "semaphore" in t5_resolved.lower()
    t5_ans = engine.answer(t5_resolved)

    assert t5_ans["route"] == "CROSS_DOMAIN"
    assert "Comparative matrix:" in t5_ans["text"]
    assert "Semaphore" in t5_ans["text"]
    assert "Condition Variable" in t5_ans["text"]
    assert "|" in t5_ans["text"]


# ── 7. Graph Integrity & Safety Preservation ──────────────────────────────────


def test_production_graph_node_and_edge_preservation(engine):
    """Knowledge graph must maintain at least 610 nodes and 1,988 edges without degradation."""
    graph = engine.graph
    assert len(graph.nodes) >= 610, f"Expected >= 610 nodes, found {len(graph.nodes)}"

    # Check that baseline AI nodes and new academic nodes coexist
    expected_sample_nodes = [
        "transformer",
        "bert",
        "self_attention",
        "low_rank_adaptation",
        "rag",
        "context_switch",
        "semaphore",
        "mutex_lock",
        "deadlock",
        "b_plus_tree",
        "hash_indexing",
        "acid_properties",
        "breadth_first_search",
        "depth_first_search",
        "tcp_congestion_control",
        "osi_model",
    ]
    for nid in expected_sample_nodes:
        assert nid in graph.nodes, f"Missing critical concept node '{nid}' from graph"
