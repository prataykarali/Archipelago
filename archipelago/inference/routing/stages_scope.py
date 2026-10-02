"""Scope stages: identity/onboarding, fast reject, library scope, social/sanity."""
from __future__ import annotations

from archipelago.inference.intent_gate import (
    INTENT_META,
    INTENT_OUT_OF_DOMAIN,
    INTENT_SOCIAL,
    REASON_OUT_OF_SCOPE,
)

from . import _deps as _rt
from .constants import _TECHNICAL_MARKERS
from .guards import _merge_slots


def pre_scope_route(
    q_raw: str,
    q: str,
    ranked: list,
    best_cos: float,
    best_lex: float,
    base: dict,
    library: dict | None,
    offtopic: bool,
    has_domain: bool,
    chitchat: bool,
    learning: bool,
    identity: bool,
    onboarding: bool,
    intent: str,
) -> tuple[dict | None, bool]:
    """Identity/onboarding returns, early fast reject, library scope gate.

    Returns ``(early_response_or_None, graph_evidence)`` — the graph-evidence
    flag is computed here (exactly where the original pipeline computed it) and
    reused by the later social/sanity and graph stages.
    """
    # 0) Identity / onboarding
    if identity and intent != INTENT_META:
        return {**base, "route": "identity", "reason": "identity", "scope": "yes"}, False

    if onboarding:
        return {
            **base, "route": "onboarding", "reason": "onboarding_syllabus",
            "scope": "yes", "related": ranked,
        }, False

    # Early fast reject for completely out-of-scope queries
    graph_evidence = _rt._has_strong_graph_evidence(ranked)
    in_scope, scope_reason = _rt.is_aiml_in_scope(
        q_raw,
        chitchat=chitchat,
        offtopic_keyword=offtopic,
        has_domain_terms=has_domain,
        strong_anchor=False,
        best_cos=best_cos,
        best_lex=best_lex,
        force_llm=False,
        learning_intent=learning,
        graph_evidence=graph_evidence,
    )
    if not in_scope and scope_reason == "no_domain_signal_low_similarity":
        return {
            "anchor_id": None,
            "score": best_cos,
            "related": ranked,
            "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "early_fast_reject"},
            "scope": "no",
            "route": "out_of_scope",
            "reason": REASON_OUT_OF_SCOPE,
        }, graph_evidence

    # 0.5) Library intents
    if library:
        in_scope, scope_reason = _rt.is_aiml_in_scope(
            q,
            chitchat=False,
            offtopic_keyword=offtopic,
            has_domain_terms=has_domain,
            strong_anchor=False,
            best_cos=best_cos,
            best_lex=best_lex,
            force_llm=not has_domain,
            learning_intent=learning,
            graph_evidence=graph_evidence,
        )
        if not in_scope:
            return {
                **base,
                "route": "out_of_scope",
                "reason": f"out_of_scope_library:{scope_reason}",
                "scope": "no",
            }, graph_evidence
        lib_intent = library["intent"]
        slots = _merge_slots(base["slots"], {"limit": library.get("limit", 5)})
        return {
            **base,
            "route": lib_intent,
            "reason": lib_intent,
            "slots": slots,
            "scope": "yes",
        }, graph_evidence

    return None, graph_evidence


def social_sanity_route(
    q_raw: str,
    q: str,
    search_q: str,
    history: list | None,
    ranked: list,
    base: dict,
    offtopic: bool,
    has_domain: bool,
    chitchat: bool,
    learning: bool,
    intent: str,
) -> dict | None:
    """Small talk, pure social, and the absurdity/authority sanity gate."""
    # 1) Small talk — mixed pleasantry + technical tail
    is_small_talk, remaining = _rt._strip_small_talk(q)
    if is_small_talk:
        has_technical_tail = bool(remaining) and bool(_TECHNICAL_MARKERS.search(remaining))
        has_learning_or_domain = (
            _rt._is_learning_intent(remaining) or _rt._has_domain_terms(remaining)
        )
        if has_technical_tail and not has_learning_or_domain:
            return {
                **base,
                "route": "small_talk",
                "reason": "conversational_greeting",
                "score": 1.0,
                "slots": _merge_slots(base["slots"], {
                    "technical_portion": remaining if remaining != q else "",
                }),
            }

    # 2) Pure social → free chat
    if chitchat or intent == INTENT_SOCIAL:
        # If social but search_q has domain content, fall through to graph
        if not (_TECHNICAL_MARKERS.search(search_q or "") or has_domain or learning):
            return {**base, "route": "general_chat", "reason": "chitchat"}

    # 2.5) Absurdity / external-authority sanity gate — only when the query
    # mixes graph-known concepts with foreign content tokens (Batman, sourdough,
    # carbon footprint, a researcher's opinions…). Clean theory questions have
    # no foreign tokens and never pay this LLM call. An off-topic marker plus
    # foreign tokens is decisive on its own (assist list, no LLM needed).
    foreign = _rt._foreign_tokens(search_q or q)
    if foreign and (
        has_domain or _rt._has_strong_graph_evidence(ranked)
        or _rt._has_surface_concept_hit(ranked, search_q or q)
    ):
        guard_input = search_q if (history and search_q and search_q != q_raw) else q_raw
        if offtopic or _rt._run_sanity_guard(guard_input):
            return {
                **base,
                "route": "out_of_scope",
                "reason": REASON_OUT_OF_SCOPE,
                "scope": "no",
                "slots": _merge_slots(base["slots"], {
                    "intent": INTENT_OUT_OF_DOMAIN,
                    "intent_method": "offtopic_mix" if offtopic else "sanity_guard",
                    "foreign_tokens": foreign[:6],
                    "closest_concepts": [
                        r.get("label") or r.get("name") or r.get("id")
                        for r in ranked[:3]
                    ],
                }),
            }
    return None
