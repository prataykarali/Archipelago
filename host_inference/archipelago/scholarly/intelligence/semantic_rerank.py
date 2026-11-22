"""Bounded semantic reranking of scholarly provider candidates."""

from __future__ import annotations

import logging
import math
import os
from statistics import median
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)
RERANK_URL = "https://ai.api.nvidia.com/v1/retrieval/nvidia/nemotron-3.5-rerank-8b/reranking"
RERANK_MODEL = "nvidia/nemotron-3.5-rerank-8b"
MAX_RERANK_CANDIDATES = 120
RERANK_BATCH_SIZE = 40
MAX_PASSAGE_CHARS = 1000
RERANK_TIMEOUT_SECONDS = 25
SEMANTIC_ACCEPT_FRACTION = 0.25
CONTROL_MARGIN = 0.7
CONTROL_PASSAGES = (
    "Medieval pottery conservation and museum display techniques.",
    "Marine ecology and coral reef biodiversity surveys.",
    "Urban road traffic planning and parking policy.",
)


def rerank_candidates(
    topic: str, candidates: list[dict[str, Any]], session: requests.Session | None = None
) -> tuple[dict[int, float], dict[str, Any]]:
    """Return model scores keyed by original candidate index, or an explicit fallback status."""
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        return {}, {"status": "unavailable", "reason": "nvidia_key_missing"}
    selected = candidates[:MAX_RERANK_CANDIDATES]
    if not selected:
        return {}, {"status": "empty", "scored_count": 0}
    client = session or requests.Session()
    scores: dict[int, float] = {}
    control_scores: list[float] = []
    for start in range(0, len(selected), RERANK_BATCH_SIZE):
        batch = selected[start : start + RERANK_BATCH_SIZE]
        passages = []
        for candidate in batch:
            paper = candidate["paper"]
            passage = " ".join((str(paper.title or ""), str(paper.abstract or "")))
            passages.append({"text": passage[:MAX_PASSAGE_CHARS] or "Untitled scholarly record"})
        passages.extend({"text": control} for control in CONTROL_PASSAGES)
        try:
            response = client.post(
                RERANK_URL,
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                json={
                    "model": RERANK_MODEL,
                    "query": {"text": topic},
                    "passages": passages,
                    "truncate": "END",
                },
                timeout=RERANK_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            for entry in response.json().get("rankings", []):
                index = entry.get("index")
                score = entry.get("logit")
                if (
                    isinstance(index, int)
                    and not isinstance(index, bool)
                    and isinstance(score, (int, float))
                    and math.isfinite(score)
                ):
                    if 0 <= index < len(batch):
                        scores[start + index] = float(score)
                    elif len(batch) <= index < len(passages):
                        control_scores.append(float(score))
        except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
            LOGGER.warning("Semantic rerank batch unavailable", exc_info=True)
            continue
    return scores, {
        "status": "available" if scores else "unavailable",
        "model": RERANK_MODEL if scores else None,
        "scored_count": len(scores),
        "control_baseline": median(control_scores) if control_scores else None,
    }


def semantic_rank_cutoff(
    scores: dict[int, float], control_baseline: float | None = None
) -> float | None:
    """Set a relative rank cutoff without treating model logits as calibrated probabilities."""
    if not scores:
        return None
    ordered = sorted(scores.values(), reverse=True)
    count = max(1, math.ceil(len(ordered) * SEMANTIC_ACCEPT_FRACTION))
    cutoff = ordered[count - 1]
    if control_baseline is not None:
        cutoff = max(cutoff, control_baseline + CONTROL_MARGIN)
    return cutoff
