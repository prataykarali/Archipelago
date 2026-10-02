"""Graph pinning stage: kill-switch, scope gate, strong/soft anchor selection."""
from __future__ import annotations

from archipelago.inference import state as st
from archipelago.inference.intent_gate import REASON_OUT_OF_SCOPE
from . import _deps as _rt
from .guards import _merge_slots


def graph_route(
    q: str,
    search_q: str,
    ranked: list,
    best: dict | None,
    best_cos: float,
    best_lex: float,
    base: dict,
    domain: bool,
    learning: bool,
    offtopic: bool,
    has_domain: bool,
    graph_evidence: bool,
) -> dict:
    """Embedder kill-switch, hybrid scope gate, graph strong/soft pinning."""
    strong_id, strong_score = _rt.find_anchor_concept(search_q)
    strong_anchor = bool(strong_id)

    # 3) Embedder kill-switch — strict cosine gate (default 0.75 with embeddings)
    threshold = float(getattr(st, "KILL_SWITCH_THRESHOLD", 0.75)) if st.use_embeddings else 0.50
    has_strong_surface_hit = best_lex >= 0.70
    if best_cos < threshold and not has_strong_surface_hit:
        force_llm = learning and not has_domain and not strong_anchor and not domain
        in_scope, scope_reason = _rt.is_aiml_in_scope(
            q,
            chitchat=False,
            offtopic_keyword=offtopic,
            has_domain_terms=has_domain,
            strong_anchor=strong_anchor,
            best_cos=best_cos,
            best_lex=best_lex,
            force_llm=force_llm,
            learning_intent=learning,
            graph_evidence=graph_evidence,
        )
        if in_scope:
            closest = [
                r.get("label") or r.get("name") or r.get("id")
                for r in ranked[:3]
            ]
            return {
                **base,
                "route": "low_similarity_reject",
                "reason": "kill_switch_low_similarity_in_scope",
                "score": best_cos,
                "scope": "yes",
                "slots": _merge_slots(base["slots"], {
                    "closest_concepts": closest, "query": q,
                }),
            }
        return {
            **base,
            "route": "out_of_scope",
            "reason": f"kill_switch_low_similarity_out_of_scope:{scope_reason}",
            "scope": "no",
        }

    # 4) Hybrid scope gate
    force_llm = learning and not has_domain and not strong_anchor and not domain
    in_scope, scope_reason = _rt.is_aiml_in_scope(
        q,
        chitchat=False,
        offtopic_keyword=offtopic,
        has_domain_terms=has_domain,
        strong_anchor=strong_anchor,
        best_cos=best_cos,
        best_lex=best_lex,
        force_llm=force_llm,
        learning_intent=learning,
        graph_evidence=graph_evidence,
    )
    if not in_scope:
        if learning and not offtopic:
            closest = [
                r.get("label") or r.get("name") or r.get("id")
                for r in ranked[:3]
            ]
            return {
                **base,
                "route": "low_similarity_reject",
                "reason": "not_indexed_learning_topic",
                "score": best_cos,
                "scope": "soft",
                "slots": _merge_slots(base["slots"], {
                    "closest_concepts": closest, "query": q,
                }),
            }
        return {
            **base,
            "route": "out_of_scope",
            "reason": f"out_of_scope:{scope_reason}",
            "scope": "no",
        }

    # 5) Graph strong / soft
    target_route = None
    target_anchor = None
    target_score = 0.0
    target_reason = ""

    if strong_id:
        target_route = "graph_strong"
        target_anchor = strong_id
        target_score = strong_score
        target_reason = "strong_embed_or_lexical"
    elif domain:
        soft = _rt._select_soft_anchor(ranked, search_q) or best
        target_route = "graph_soft"
        target_anchor = soft["id"] if soft else None
        target_score = float(soft.get("cos") or 0.0) if soft else 0.0
        target_reason = "domain_soft_match"
    elif best and best_cos >= st.DOMAIN_SOFT_THRESHOLD + 0.12 and best_lex >= 0.35:
        soft = _rt._select_soft_anchor(ranked, search_q) or best
        target_route = "graph_soft"
        target_anchor = soft["id"] if soft else None
        target_score = float(soft.get("cos") or 0.0) if soft else best_cos
        target_reason = "soft_high_confidence"

    if target_route:
        max_cos = max(
            (float(r.get("cos") or 0.0) for r in ranked), default=0.0
        )
        best_alias = float((best or {}).get("alias_boost") or 0.0)
        best_blended = float((best or {}).get("blended") or 0.0)
        surface_hit = _rt._has_surface_concept_hit(ranked, q)

        hard_miss = (
            st.use_embeddings
            and target_route == "graph_soft"
            and max_cos < st.REJECT_SIMILARITY_THRESHOLD
            and best_lex < 0.40
            and best_alias < 0.12
            and not surface_hit
        )
        if hard_miss:
            closest = [
                r.get("label") or r.get("name") or r.get("id")
                for r in ranked[:3]
            ]
            return {
                **base,
                "route": "low_similarity_reject",
                "score": max_cos,
                "reason": "low_similarity_reject",
                "scope": "yes",
                "slots": _merge_slots(base["slots"], {
                    "closest_concepts": closest, "query": q,
                }),
            }

        if (
            st.use_embeddings
            and target_route == "graph_soft"
            and max_cos < st.REJECT_SIMILARITY_THRESHOLD
        ):
            return {
                **base,
                "route": "graph_soft",
                "anchor_id": target_anchor,
                "score": max_cos,
                "reason": "partial_coverage_low_cos",
                "scope": "yes",
                "slots": _merge_slots(base["slots"], {
                    "partial": True,
                    "closest_concepts": [
                        r.get("label") or r.get("name") or r.get("id")
                        for r in ranked[:3]
                    ],
                }),
            }

        out_score = target_score
        if target_route == "graph_soft" and best_blended > out_score:
            out_score = min(1.0, best_blended * 0.5 + out_score * 0.5)

        return {
            **base,
            "route": target_route,
            "anchor_id": target_anchor,
            "score": out_score,
            "reason": target_reason,
            "scope": "yes",
        }

    if learning:
        closest = [
            r.get("label") or r.get("name") or r.get("id")
            for r in ranked[:3]
        ]
        return {
            **base,
            "route": "low_similarity_reject",
            "score": best_cos,
            "reason": "not_indexed_low_signal",
            "scope": "yes",
            "slots": _merge_slots(base["slots"], {
                "closest_concepts": closest, "query": q,
            }),
        }

    return {
        **base,
        "route": "general_chat",
        "reason": "low_similarity_open_chat",
        "scope": "yes",
    }
