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
SUMMARY_CORRECTIONS: dict[str, tuple[str, str]] = {
    "transformer": (TRANSFORMER_CONFLATION, TRANSFORMER_CORRECTION),
    "gpt": (GPT_CONFLATION, GPT_CORRECTION),
    "gpt_2": (
        "GPT-2, the second generation of GPT, is a left-to-right language model using a "
        "Transformer decoder architecture with 1234 tokens.",
        "GPT-2 is a unidirectional, autoregressive Transformer decoder language model "
        "(1,024-token context window) pretrained with causal next-token prediction on "
        "WebText (Radford et al., 2019).",
    ),
    "bm25": (
        "A bidirectional search engine that evaluates text passages using masked "
        "language modeling on the BM25 corpus.",
        "BM25 (Okapi BM25) is a probabilistic bag-of-words lexical retrieval ranking "
        "function based on term frequency saturation, inverse document frequency, and "
        "document-length normalization (Robertson & Zaragoza, 2009).",
    ),
    "dpr": (
        "DPR: A retrieval-prompt generation model using masked language modeling on "
        "text pairs, extracting factual knowledge for question answering.",
        "Dense Passage Retrieval (DPR) uses a dual-encoder architecture (separate "
        "BERT-based question and passage encoders) trained with contrastive in-batch "
        "and hard negatives to retrieve passages by maximum inner-product search "
        "(Karpukhin et al., 2020).",
    ),
    "transformer_encoder": (
        "The Transformer encoder is a sequence-to-sequence neural network using masked "
        "language modeling and next-token prediction.",
        "The Transformer encoder is a stack of bidirectional multi-head self-attention "
        "and position-wise feed-forward layers that maps an input token sequence to "
        "contextualized continuous representations (Vaswani et al., 2017).",
    ),
}


def corrected_summary(concept_id: str, summary: str) -> str:
    """Replace only known contaminated extraction summaries without mutating okf_graph.json."""
    pair = SUMMARY_CORRECTIONS.get(concept_id)
    if pair is not None and summary == pair[0]:
        return pair[1]
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
