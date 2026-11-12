"""Evidence-bound method, dataset and metric extraction from titles and abstracts.

Only terms literally present in provider text are returned, each with the
sentence that supports it. Nothing is inferred and nothing is scored.
"""

from __future__ import annotations

import re
from typing import Any

METHODS = (
    "graph convolutional network",
    "graph attention network",
    "graph neural network",
    "message passing",
    "transformer",
    "convolutional neural network",
    "recurrent neural network",
    "lstm",
    "contrastive learning",
    "self-supervised learning",
    "semi-supervised learning",
    "supervised learning",
    "reinforcement learning",
    "transfer learning",
    "fine-tuning",
    "knowledge distillation",
    "retrieval-augmented generation",
    "dense retrieval",
    "large language model",
    "prompt engineering",
    "experience replay",
    "regularization",
    "elastic weight consolidation",
    "meta-learning",
    "attention mechanism",
    "connectionist temporal classification",
    "end-to-end",
    "data augmentation",
    "ablation study",
    "survey",
    "systematic review",
)
DATASETS = (
    "cora",
    "citeseer",
    "pubmed",
    "ogb",
    "imagenet",
    "cifar-10",
    "cifar-100",
    "mnist",
    "coco",
    "squad",
    "ms marco",
    "natural questions",
    "hotpotqa",
    "librispeech",
    "common voice",
    "openslr",
    "ocr-bench",
    "icdar",
    "tudataset",
    "qm9",
    "mimic",
)
METRICS = (
    "accuracy",
    "f1",
    "f1-score",
    "precision",
    "recall",
    "auc",
    "bleu",
    "rouge",
    "word error rate",
    "wer",
    "character error rate",
    "mean average precision",
    "perplexity",
    "exact match",
)
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _find(vocabulary: tuple[str, ...], sentences: list[str]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for term in vocabulary:
        pattern = re.compile(rf"(?<![\w-]){re.escape(term)}s?(?![\w-])", re.IGNORECASE)
        for sentence in sentences:
            if pattern.search(sentence):
                found.append({"name": term, "evidence": sentence.strip()[:300]})
                break
    return found


def extract_evidence(title: str, abstract: str | None) -> dict[str, Any]:
    """Return supported methods, datasets and metrics; empty when unsupported."""
    text = f"{title}. {abstract or ''}"
    sentences = [part for part in SENTENCE.split(text) if part.strip()]
    return {
        "methods": _find(METHODS, sentences),
        "datasets": _find(DATASETS, sentences),
        "evaluation_metrics": _find(METRICS, sentences),
    }
