"""Unit tests for Query Mode Classification (Mode A, Mode B, Mode C)."""

import pytest

from archipelago.inference.query_classifier import QueryMode, classify_query_mode


def test_classify_empty_query():
    assert classify_query_mode("") == QueryMode.MODE_A
    assert classify_query_mode("   ") == QueryMode.MODE_A


def test_classify_mode_a_atomic_queries():
    # Atomic definitions, single concept factual queries
    queries = [
        "What is Low-Rank Adaptation?",
        "Define transformer",
        "Explain self-attention",
        "Tell me about residual connections",
        "What is cross entropy loss?",
    ]
    for q in queries:
        mode = classify_query_mode(q)
        assert mode == QueryMode.MODE_A, f"Query '{q}' expected MODE_A, got {mode}"


def test_classify_mode_b_comparative_queries():
    queries = [
        "Compare LoRA and full fine-tuning",
        "What is the difference between CNN and RNN?",
        "How does BERT differ from GPT?",
        "Transformer vs Recurrent Neural Network",
        "Which is better: Adam or SGD?",
        "Connection between eigenvalues and PCA",
        "Relationship between attention mechanism and memory",
    ]
    for q in queries:
        mode = classify_query_mode(q)
        assert mode == QueryMode.MODE_B, f"Query '{q}' expected MODE_B, got {mode}"


def test_classify_mode_c_curriculum_queries():
    queries = [
        "How can I learn deep learning from scratch?",
        "Give me a step by step roadmap for transformers",
        "Curriculum to master neural networks from the beginning",
        "What are the prerequisites for Low-Rank Adaptation?",
        "Where should I start to learn machine learning?",
        "Comprehensive guide to natural language processing",
        "Study plan from scratch for LLMs",
    ]
    for q in queries:
        mode = classify_query_mode(q)
        assert mode == QueryMode.MODE_C, f"Query '{q}' expected MODE_C, got {mode}"


def test_routing_result_overrides():
    # Out of scope / small talk routes default to Mode A regardless of phrasing
    routing_res = {"route": "out_of_scope"}
    assert classify_query_mode("teach me from scratch how to cook pasta", routing_result=routing_res) == QueryMode.MODE_A

    small_talk = {"route": "small_talk"}
    assert classify_query_mode("hello, tell me a roadmap", routing_result=small_talk) == QueryMode.MODE_A
