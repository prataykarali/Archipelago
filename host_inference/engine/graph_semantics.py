"""Candidate-only corrections for known graph extraction defects."""

from __future__ import annotations

from typing import Any

RAG_CONCEPTS = frozenset({"rag", "retrieval_augmented_generation"})
SUPPORTED_RAG_DEPENDENCIES = frozenset(
    {
        ("vector_rag", "retrieval_augmented_generation", "REQUIRES"),
        ("advanced_rag", "rag", "REQUIRES"),
        ("retrieval_augmented_generation", "vector_rag", "UNLOCKS"),
        ("rag", "advanced_rag", "UNLOCKS"),
    }
)
TRANSFORMER_CONFLATION = (
    "Transformer: A bidirectional, generative sequence-to-sequence neural network "
    "using masked language modeling and next-token prediction."
)
TRANSFORMER_CORRECTION = (
    "The original Transformer is an attention-based encoder-decoder architecture "
    "for sequence transduction. Its encoder attends across input positions; its "
    "decoder generates outputs autoregressively. BERT's masked-language-model "
    "training and GPT-style next-token pretraining are later model-specific choices."
)
GPT_CONFLATION = (
    "GPT stands for GPT-3, a generative pre-trained transformer model that uses "
    "masked language modeling and next-token prediction to generate language."
)
GPT_CORRECTION = (
    "GPT (Generative Pre-trained Transformer) is an autoregressive decoder-only "
    "Transformer model family pretrained with causal next-token prediction, "
    "not masked language modeling."
)


def corrected_summary(concept_id: str, summary: str) -> str:
    """Replace only known contaminated extraction summaries without mutating okf_graph.json."""
    if concept_id == "transformer" and summary == TRANSFORMER_CONFLATION:
        return TRANSFORMER_CORRECTION
    if concept_id == "gpt" and summary == GPT_CONFLATION:
        return GPT_CORRECTION
    return summary


def quarantine_reason(edge: dict[str, Any]) -> str | None:
    """Return why a RAG edge cannot be used as a validated learning relation."""
    source = str(edge.get("from_id") or "")
    target = str(edge.get("to_id") or "")
    kind = str(edge.get("edge_type") or edge.get("relation") or "RELATED").upper()
    if source not in RAG_CONCEPTS and target not in RAG_CONCEPTS:
        return None
    if kind in {"REQUIRES", "UNLOCKS"}:
        if (source, target, kind) in SUPPORTED_RAG_DEPENDENCIES:
            return None
        return "Dependency direction or prerequisite semantics lack claim-level review"
    if kind == "RELATED" and edge.get("relation") != "co_mention":
        return "Extracted related subtype lacks claim-level semantic review"
    return None
