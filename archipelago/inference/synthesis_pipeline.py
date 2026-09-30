"""synthesis_pipeline.py — 5-stage local-retrieve and synthesis pipeline."""
from __future__ import annotations

import logging
import re
import threading
from typing import Any

from archipelago.inference import state as st
from archipelago.inference import ranking

logger = logging.getLogger(__name__)

_ollama_lock = threading.Lock()


def _acquire_ollama() -> None:
    _ollama_lock.acquire()


def _release_ollama() -> None:
    if _ollama_lock.locked():
        _ollama_lock.release()


def _ollama_client() -> Any:
    import ollama
    return ollama


def _stage1_guardrails(query: str) -> dict[str, Any]:
    """Stage 1: Enforce input length bounds and strip polite conversational noise."""
    if len(query) > 500:
        return {
            "reject": True,
            "reason": "Query exceeds maximum length of 500 characters.",
        }

    # Normalize polite filler
    q = query.strip()
    noise_patterns = [
        r"^(hey|hello|hi|please|can you|could you|tell me about|explain|what is)[,!.]?\s+",
        r"^(can you explain|could you tell me)\s+",
    ]
    normalized = q
    for pat in noise_patterns:
        normalized = re.sub(pat, "", normalized, flags=re.IGNORECASE).strip()

    return {
        "reject": False,
        "normalized_query": normalized if normalized else q,
    }


def _stage2_vector_search(query: str) -> dict[str, Any] | None:
    """Stage 2: Dense vector retrieval with kill-switch cutoff."""
    ranked = ranking.rank_concepts(query, top_k=5)
    if not ranked:
        return None

    top_hit = max(ranked, key=lambda hit: hit.get("blended", hit.get("cos", 0.0)))
    score = top_hit.get("blended", top_hit.get("cos", 0.0))

    # Kill-switch threshold
    if score < 0.45 and top_hit.get("cos", 0.0) < 0.35 and top_hit.get("alias_boost", 0.0) < 0.3:
        return None

    anchor_id = top_hit.get("id")
    concept_data = getattr(st, "CONCEPTS_DATA", {}).get(anchor_id, {})
    concept_name = concept_data.get("label") or concept_data.get("name") or top_hit.get("label") or anchor_id

    return {
        "anchor_id": anchor_id,
        "concept_name": concept_name,
        "cosine_sim": top_hit.get("cos", 0.0),
        "blended_score": score,
    }


def _stage3_graph_traversal(anchor_id: str, k: int = 2) -> dict[str, Any]:
    """Stage 3: Graph traversal for upstream prerequisites and downstream unlocks."""
    try:
        from archipelago.inference.neighborhood import get_concept_neighborhood
        return get_concept_neighborhood(anchor_id, k=k)
    except Exception:
        return {
            "target": anchor_id,
            "prerequisites": [],
            "unlocks": [],
            "related": [],
        }


def _stage4_build_payload(
    target_concept: str, prerequisites: list[Any], unlocks: list[Any], query: str, chunks: list[Any] | None = None
) -> dict[str, Any]:
    """Stage 4: Build topological context payload for the synthesizer using PromptPayloadAssembler."""
    from src.core.prompt_assembly import PromptPayloadAssembler
    assembler = PromptPayloadAssembler()
    return assembler.assemble_payload(
        query=query,
        anchor_name=target_concept,
        prerequisites=prerequisites,
        unlocks=unlocks,
        chunks=chunks or [],
    )


def _stage5_ollama_synthesis(payload: dict[str, Any]) -> str:
    """Stage 5: Synthesis with local Ollama qwen3.5:0.8b model."""
    from src.core.synthesis_service import SynthesisService
    synth = SynthesisService()
    res = synth.synthesize_response(payload, stream=False)
    if isinstance(res, dict):
        return str(res.get("text") or "")
    return str(res)


def run_archipelago_inference(query: str, history: list[Any] | None = None) -> dict[str, Any]:
    """Execute the full 5-stage inference pipeline."""
    # Stage 1
    s1 = _stage1_guardrails(query)
    if s1.get("reject"):
        return {
            "routing": {"route": "rejected"},
            "text": s1.get("reason", "Input rejected by safety guardrails."),
            "sources": [],
            "citations": [],
        }

    norm_q = s1.get("normalized_query", query)

    # Stage 2
    s2 = _stage2_vector_search(norm_q)
    if s2 is None:
        return {
            "routing": {"route": "kill_switch"},
            "text": (
                "This topic is outside the current scope of the library's active catalog. "
                "Archipelago is scoped to Computer Science, AI/ML, database systems, and institutional library collections, including RAG."
            ),
            "sources": [],
            "citations": [],
        }

    anchor_id = s2["anchor_id"]
    concept_name = s2["concept_name"]

    # Stage 3
    graph_ctx = _stage3_graph_traversal(anchor_id)

    # Retrieve attached verified text chunks
    from src.core.retrieval import TwoPassHybridRetriever
    retriever = TwoPassHybridRetriever(concepts_data=getattr(st, "CONCEPTS_DATA", {}))
    chunks = graph_ctx.get("chunks") or retriever.get_evidence_chunks(anchor_id, max_chunks=3)

    # Stage 4
    payload = _stage4_build_payload(
        target_concept=concept_name,
        prerequisites=graph_ctx.get("prerequisites", []),
        unlocks=graph_ctx.get("unlocks", []),
        query=norm_q,
        chunks=chunks,
    )

    # Stage 5
    text = _stage5_ollama_synthesis(payload)

    from archipelago.inference.citations import citation_payload

    citations = [citation_payload(chunk, concept_name) for chunk in chunks]
    for index, citation in enumerate(citations, 1):
        citation["evidence_id"] = f"S{index}"

    return {
        "routing": {"route": "graph_strong", "anchor": anchor_id, "reason": "5_stage_pipeline"},
        "generation": {"provider": "ollama", "source": "ollama"},
        "text": text,
        "sources": [c.get("doc_id") for c in citations if c.get("doc_id")],
        "citations": citations,
        "target_concept": concept_name,
        "anchor_concept": {"id": anchor_id, "name": concept_name},
        "prerequisites": graph_ctx.get("prerequisites", []),
        "unlocks": graph_ctx.get("unlocks", []),
    }
