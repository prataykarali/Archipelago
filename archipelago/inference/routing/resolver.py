"""Query routing pipeline: stage orchestration + response post-processing."""
from __future__ import annotations

import re

from archipelago.inference import state as st
from archipelago.inference.intent_gate import (
    INTENT_ENTITY_TRIVIA,
    INTENT_IMPLEMENTATION,
    INTENT_META,
    INTENT_OUT_OF_DOMAIN,
    INTENT_SOCIAL,
    INTENT_THEORY,
)

from . import _deps as _rt
from .constants import _SMALL_TALK_PREFIXES, _TECHNICAL_MARKERS
from .stages_early import early_route, social_short_circuit
from .stages_graph import graph_route
from .stages_intent import dual_pass_artifact_route, dual_pass_ood_route, intent_block_route
from .stages_quiz import quiz_route
from .stages_scope import pre_scope_route, social_sanity_route


def resolve_query_routing(query: str, history: list | None = None) -> dict:
    """Route a query and normalize the refusal reasons for the UI."""
    res = _resolve_query_routing(query, history=history)
    if isinstance(res, dict):
        reason = res.get("reason") or ""
        rl = reason.lower()
        if res.get("route") == "out_of_scope":
            if "implementation" in rl:
                reason = "implementation_request"
            elif "not_in_corpus" in rl or "entity" in rl:
                reason = "not_in_corpus"
            elif "meta" in rl:
                reason = "meta_refused"
            else:
                reason = "out_of_scope"
            res["reason"] = reason
            res["block_reason"] = reason
        else:
            res["block_reason"] = None

        # ── Semantic Safety Net only for general Out-of-Scope (non-policy) ──
        # Sanity-guard / dual-pass verdicts are deliberate rejections of
        # absurd or trivia asks — never soften those back into suggestions.
        guarded = (res.get("slots") or {}).get("intent_method") in (
            "sanity_guard", "dual_pass_guard", "offtopic_mix", "emotional_homework_ood",
        )
        if (
            res.get("route") == "out_of_scope"
            and res.get("reason") == "out_of_scope"
            and not guarded
        ):
            from archipelago.inference.ranking import rank_concepts
            q_raw = (query or "").strip()
            ranked = rank_concepts(q_raw, top_k=3)
            best_cos = float(ranked[0]["cos"]) if ranked else 0.0
            best_lex = float(ranked[0].get("lexical") or 0.0) if ranked else 0.0

            # Check if query has a domain signal
            has_domain_signal = _rt._is_learning_or_domain_query(q_raw)
            if has_domain_signal:
                closest = [
                    r.get("label") or r.get("name") or r.get("id")
                    for r in ranked[:3]
                ]
                res["route"] = "low_similarity_reject"
                res["reason"] = "kill_switch_low_similarity_in_scope"
                res["scope"] = "soft"
                res["slots"] = {
                    **(res.get("slots") or {}),
                    "closest_concepts": closest,
                    "query": q_raw,
                }
                res["block_reason"] = None

        from archipelago.inference.query_classifier import classify_query_mode
        res["query_mode"] = classify_query_mode(query, routing_result=res).value
    return res


def _resolve_query_routing(query: str, history: list | None = None) -> dict:
    """Decide how to answer.

    Routes: out_of_scope | library_* | onboarding | identity | small_talk
    | graph_strong | graph_soft | general_chat | low_similarity_reject

    Order:
      1) De-grease (small-talk prefix + style noise)
      2) Intent gate (embed prototypes / LLM) — blocks implementation,
         entity trivia, OOD, meta without keyword banlists
      3) Identity / onboarding / library
      4) Embedder kill-switch (strict cosine threshold)
      5) Scope + graph pin
    """
    if not st.CONCEPTS_DATA:
        from archipelago.inference.routes_chat import init_concepts_data
        try:
            init_concepts_data()
        except Exception as e:
            print(f"Failed to auto-initialize concepts data: {e}")

    q_raw = (query or "").strip()

    library = _rt._detect_library_intent(q_raw)
    early = early_route(q_raw, library)
    if early:
        return early

    q, style_stripped = _rt._strip_persona_style(q_raw)

    # Searchable portion: drop conversational lead-ins
    search_q = q
    prefixed = _SMALL_TALK_PREFIXES.sub("", q).strip()
    if prefixed:
        search_q = prefixed

    # Re-run style strip on search portion
    search_q, _ = _rt._strip_persona_style(search_q)

    social = social_short_circuit(q_raw, q, search_q)
    if social:
        return social

    ranked = _rt.rank_concepts(search_q, top_k=max(st.TOP_K_RELATED, 10))
    best = ranked[0] if ranked else None
    best_cos = float(best["cos"]) if best else 0.0
    best_lex = float(best.get("lexical") or 0.0) if best else 0.0
    learning = _rt._is_learning_intent(q)

    quiz = quiz_route(q_raw, history, ranked, best, best_cos)
    if quiz:
        return quiz

    # Conversational memory/pronoun expansion — fires whenever the query leans
    # on a prior turn (pronouns / deictic follow-ups) and the graph shows no
    # direct surface hit of its own, not only when cosine is very low.
    if history:
        has_pronoun = bool(re.search(
            r"\b(it|this|that|them|these|its|starting|before|after|next|prereq|prerequisites|requirements|downstream|upstream|concept|topic|more|deeper|further)\b",
            q_raw, re.I
        ))
        own_surface_hit = _rt._has_surface_concept_hit(ranked, search_q)
        needs_context = best_cos < 0.45 or (has_pronoun and not own_surface_hit)
        if needs_context and (has_pronoun or learning):
            active_concept = _rt._get_active_concept_from_history(history)
            if active_concept and active_concept in st.CONCEPTS_DATA:
                concept_name = st.CONCEPTS_DATA[active_concept].get("label") or active_concept
                search_q = f"{search_q} {concept_name}"
                q = f"{q} {concept_name}"
                # Re-calculate routing parameters with the expanded query
                ranked = _rt.rank_concepts(search_q, top_k=max(st.TOP_K_RELATED, 10))
                best = ranked[0] if ranked else None
                best_cos = float(best["cos"]) if best else 0.0
                best_lex = float(best.get("lexical") or 0.0) if best else 0.0
                learning = _rt._is_learning_intent(q)

    domain = _rt._is_learning_or_domain_query(q)
    chitchat = _rt._is_chitchat(q)
    offtopic = _rt._is_offtopic(q)
    has_domain = _rt._has_domain_terms(q)
    identity = _rt._is_identity(q)
    onboarding = _rt._is_onboarding(q)

    # Intent on degreased technical ask first (style-stripped), then raw.
    # Classifying slang-laden raw text alone made backprop→OOD / RAG theory→impl.
    intent_info = _rt.classify_intent(search_q or q)
    if intent_info["intent"] == INTENT_SOCIAL and search_q and search_q != q_raw:
        intent_info = _rt.classify_intent(search_q)
    if intent_info["intent"] == INTENT_SOCIAL and _TECHNICAL_MARKERS.search(search_q or ""):
        intent_info = _rt.classify_intent(search_q)
    # Meta / system-leak still needs the raw wording ("as an AI… token limits")
    if intent_info["intent"] not in (INTENT_META, INTENT_IMPLEMENTATION, INTENT_ENTITY_TRIVIA):
        raw_info = _rt.classify_intent(q_raw)
        if raw_info["intent"] in (INTENT_META, INTENT_IMPLEMENTATION, INTENT_ENTITY_TRIVIA):
            # Only adopt raw block if search path was not clear pedagogy/theory
            if intent_info["intent"] != INTENT_THEORY:
                intent_info = raw_info

    intent = intent_info["intent"]
    intent_score = float(intent_info.get("score") or 0.0)

    base = {
        "anchor_id": None,
        "score": best_cos,
        "related": ranked,
        "slots": {
            "intent": intent,
            "intent_score": intent_score,
            "intent_method": intent_info.get("method"),
        },
        "scope": "skipped",
    }
    if style_stripped:
        base["slots"]["sterile"] = True
        base["slots"]["persona_hijack"] = True

    artifact = dual_pass_artifact_route(q_raw, search_q, history, intent, base, ranked)
    if artifact:
        return artifact

    blocked, intent, base = intent_block_route(
        q_raw, q, search_q, ranked, intent, intent_score, base, library
    )
    if blocked:
        return blocked

    ood = dual_pass_ood_route(q_raw, intent, intent_score, intent_info, best_cos, base)
    if ood:
        return ood

    pre, graph_evidence = pre_scope_route(
        q_raw, q, ranked, best_cos, best_lex, base, library, offtopic, has_domain,
        chitchat, learning, identity, onboarding, intent,
    )
    if pre:
        return pre

    socialized = social_sanity_route(
        q_raw, q, search_q, history, ranked, base, offtopic, has_domain,
        chitchat, learning, intent,
    )
    if socialized:
        return socialized

    return graph_route(
        q, search_q, ranked, best, best_cos, best_lex, base, domain,
        learning, offtopic, has_domain, graph_evidence,
    )
