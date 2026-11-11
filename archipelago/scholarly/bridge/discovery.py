"""Find and rank a bounded cross-source paper set on the local GPU."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from archipelago.scholarly.acquisition.rights_resolver import RightsResolver
from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.live_sources import LiveResearchSources
from archipelago.scholarly.pipeline.relevance import relevance_score

SOURCES = ("openalex", "crossref", "arxiv", "semantic_scholar")
PER_SOURCE_RESULTS = 30
EMBEDDING_MODEL = "Snowflake/snowflake-arctic-embed-m-v1.5"
EMBED_BATCH_SIZE = 16
SEMANTIC_WEIGHT = 0.65
LEXICAL_WEIGHT = 0.35
MAX_ABSTRACT_CHARS = 1800
MIN_PERMITTED_PDFS = 6
MIN_RELEVANCE_SCORE = 0.5
MIN_RELATIVE_RELEVANCE = 0.6


def select_relevant_papers(
    ranked: list[tuple[float, dict[str, Any]]], paper_limit: int
) -> list[tuple[float, dict[str, Any]]]:
    """Reserve a few source-relevant, legally readable PDFs for full OKF extraction."""
    selected = list(ranked[:paper_limit])
    if not selected:
        return selected
    rights = RightsResolver()

    def readable(item: dict[str, Any]) -> bool:
        paper = item["paper"]
        return bool(
            rights.resolve_access(paper.is_open_access, paper.license, item.get("pdf_url"))[
                "can_fetch_fulltext"
            ]
        )

    quota = min(MIN_PERMITTED_PDFS, paper_limit)
    readable_count = sum(readable(item) for _, item in selected)
    cutoff = max(MIN_RELEVANCE_SCORE, ranked[0][0] * MIN_RELATIVE_RELEVANCE)
    for score, item in ranked[paper_limit:]:
        if readable_count >= quota or score < cutoff:
            break
        if not readable(item):
            continue
        replace_index = next(
            (
                index
                for index in range(len(selected) - 1, -1, -1)
                if not readable(selected[index][1])
            ),
            None,
        )
        if replace_index is None:
            break
        selected[replace_index] = (score, item)
        readable_count += 1
    return sorted(selected, key=lambda pair: -pair[0])


def discover_ranked_papers(
    topic: str, paper_limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, dict[str, Any]]:
    """Use official APIs, conservative deduplication, and CUDA embeddings."""

    def search(source: str) -> Any:
        return LiveResearchSources().search(source, topic, PER_SOURCE_RESULTS)

    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        responses = list(pool.map(search, SOURCES))
    candidates = [item for response in responses for item in response.records]
    canonical = Canonicalizer().canonicalize_candidates(candidates)
    if not canonical:
        return [], [response.summary() for response in responses], "no_papers", {}
    scores = [relevance_score(item, topic)[0] for item in canonical]
    model_status = "gpu_unavailable"
    gpu: dict[str, Any] = {}
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            model = SentenceTransformer(
                EMBEDDING_MODEL,
                local_files_only=True,
                trust_remote_code=False,
                device="cuda",
            )
            texts = [
                f"{item['paper'].title}. {(item['paper'].abstract or '')[:MAX_ABSTRACT_CHARS]}"
                for item in canonical
            ]
            vectors = model.encode(
                [topic, *texts],
                batch_size=EMBED_BATCH_SIZE,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            semantic = np.clip(vectors[1:] @ vectors[0], 0, 1)
            scores = [
                round(SEMANTIC_WEIGHT * float(score) + LEXICAL_WEIGHT * lexical, 4)
                for score, lexical in zip(semantic, scores, strict=True)
            ]
            model_status = "gpu_embeddings"
            gpu = {
                "device": torch.cuda.get_device_name(0),
                "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / (1024 * 1024)),
                "embedding_count": len(texts) + 1,
            }
    except (ImportError, OSError, RuntimeError, ValueError):
        model_status = "gpu_unavailable"
    ranked = sorted(zip(scores, canonical, strict=True), key=lambda pair: -pair[0])
    selected = []
    for score, item in select_relevant_papers(ranked, paper_limit):
        item["topic_relevance_score"] = score
        selected.append(item)
    return selected, [response.summary() for response in responses], model_status, gpu
