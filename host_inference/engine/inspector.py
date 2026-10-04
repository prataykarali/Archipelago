"""Optional retrieval trace assembled from actual execution, not model claims."""
from __future__ import annotations

from .privacy import inference_context


def build_trace(graph, payload: dict, route: str, contract: str, extra: dict) -> dict:
    """Expose safe evidence and bounded context separately from the normal answer."""
    nodes = [
        payload.get("anchor_concept"),
        *payload.get("prerequisites", []), *payload.get("unlocks", []),
        *payload.get("related_concepts", []),
    ]
    return {
        "intent": contract, "route": route,
        "retrieval_type": "exported_graph_lexical_hash_vector",
        "corpus_source": getattr(graph, "corpus_source", "unknown"),
        "anchor": (payload.get("anchor_concept") or {}).get("id"),
        "score": extra.get("score"),
        "score_type": "lexical_hash_cosine_with_phrase_boost",
        "k_hop_depth": 2 if payload.get("anchor_concept") else 0,
        "nodes_retrieved": len({node["id"] for node in nodes if isinstance(node, dict)}),
        "source_pages": [
            {key: citation.get(key) for key in ("doc_id", "page_number", "url")}
            for citation in payload.get("citations", []) if isinstance(citation, dict)
        ],
        "external_context": inference_context(graph, payload),
        "privacy_policy": "allowlisted concept summaries; no inventory or learner history",
    }
