"""Query routing: graph | library | out_of_scope | general_chat | small_talk."""
from __future__ import annotations

import re

from archipelago.inference.ranking import (
    rank_concepts, find_anchor_concept, _select_soft_anchor,
    _is_chitchat, _is_offtopic, _is_learning_or_domain_query,
    _has_domain_terms, _is_learning_intent, _is_identity, _is_onboarding,
    normalize_user_query, _has_surface_concept_hit, _has_strong_graph_evidence,
)
from archipelago.inference.scope_gate import is_aiml_in_scope
from archipelago.inference.library_scope import (
    AMBIGUOUS,
    IN_SCOPE,
    classify_library_scope,
)
from archipelago.inference.intent_gate import (
    classify_intent,
    intent_to_block_reason,
    INTENT_THEORY,
    INTENT_SOCIAL,
    INTENT_IMPLEMENTATION,
    INTENT_OUT_OF_DOMAIN,
    INTENT_ENTITY_TRIVIA,
    INTENT_META,
    REASON_IMPLEMENTATION,
    REASON_OUT_OF_SCOPE,
    REASON_NOT_IN_CORPUS,
    REASON_META,
)
from archipelago.inference import state as st
from archipelago.inference.routing_helpers import (
    _strip_small_talk,
    _strip_persona_style,
    _merge_slots,
    _run_dual_pass_guard,
    _get_active_concept_from_history,
    _foreign_tokens,
    _run_sanity_guard,
    _graph_block_override,
    _TECHNICAL_MARKERS,
    parse_multi_topic_query,
)
from archipelago.inference.routing_library_intent import _detect_library_intent

def resolve_query_routing(query: str, history: list | None = None) -> dict:
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

        guarded = (res.get("slots") or {}).get("intent_method") in (
            "sanity_guard", "dual_pass_guard", "offtopic_mix",
        )
        if (
            res.get("route") == "out_of_scope"
            and res.get("reason") == "out_of_scope"
            and not guarded
        ):
            from archipelago.inference.ranking import rank_concepts
            q_raw = (query or "").strip()
            ranked = rank_concepts(q_raw, top_k=3)
            has_domain_signal = _is_learning_or_domain_query(q_raw)
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
    return res

def _resolve_query_routing(query: str, history: list | None = None) -> dict:
    q_raw = (query or "").strip()
    scope_decision = classify_library_scope(q_raw, history=history)
    if scope_decision.status != IN_SCOPE:
        route = "library_ambiguous" if scope_decision.status == AMBIGUOUS else "out_of_scope"
        closest: list[str] = []
        if st.CONCEPTS_DATA:
            try:
                ranked_hint = rank_concepts(q_raw, top_k=3)
                closest = [
                    r.get("label") or r.get("name") or r.get("id")
                    for r in ranked_hint
                    if r.get("label") or r.get("name") or r.get("id")
                ][:3]
            except Exception:
                closest = []
        return {
            "anchor_id": None, "score": scope_decision.confidence, "related": [],
            "slots": {
                "intent": scope_decision.intent,
                "matched_terms": list(scope_decision.matched_terms),
                "closest_concepts": closest,
            },
            "scope": "no", "route": route, "reason": scope_decision.reason,
        }

    if not st.CONCEPTS_DATA:
        from archipelago.inference.routes_chat import init_concepts_data
        try:
            init_concepts_data()
        except Exception as e:
            print(f"Failed to auto-initialize concepts data: {e}")

    library = _detect_library_intent(q_raw)

    if "my dataset" in q_raw.lower() or "my data" in q_raw.lower():
        return {
            "anchor_id": None, "score": 1.0, "related": [],
            "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "direct_block"},
            "scope": "no", "route": "out_of_scope", "reason": REASON_OUT_OF_SCOPE,
        }

    q, style_stripped = _strip_persona_style(q_raw)
    search_q = q
    prefixed = re.sub(r"^\s*(?:hi|hello|hey|yo|sup|howdy|good\s+morning)\s*,?\s*", "", q, flags=re.I).strip()
    if prefixed:
        search_q = prefixed
    search_q, _ = _strip_persona_style(search_q)

    if _is_chitchat(q_raw) and not _TECHNICAL_MARKERS.search(search_q or q_raw):
        return {
            "anchor_id": None, "score": 1.0, "related": [],
            "slots": {"intent": INTENT_SOCIAL, "intent_method": "chitchat_short_circuit"},
            "scope": "yes", "route": "general_chat", "reason": "chitchat",
        }

    ranked = rank_concepts(search_q, top_k=max(st.TOP_K_RELATED, 10))
    best = ranked[0] if ranked else None
    best_cos = float(best["cos"]) if best else 0.0
    best_lex = float(best.get("lexical") or 0.0) if best else 0.0
    learning = _is_learning_intent(q)

    if history:
        has_pronoun = bool(re.search(
            r"\b(it|this|that|them|these|its|starting|before|after|next|prereq|prerequisites|requirements|downstream|upstream|concept|topic|more|deeper|further)\b",
            q_raw, re.I
        ))
        own_surface_hit = _has_surface_concept_hit(ranked, search_q)
        needs_context = best_cos < 0.45 or (has_pronoun and not own_surface_hit)
        if needs_context and (has_pronoun or learning):
            active_concept = _get_active_concept_from_history(history)
            if active_concept and active_concept in st.CONCEPTS_DATA:
                concept_name = st.CONCEPTS_DATA[active_concept].get("label") or active_concept
                search_q = f"{search_q} {concept_name}"
                q = f"{q} {concept_name}"
                ranked = rank_concepts(search_q, top_k=max(st.TOP_K_RELATED, 10))
                best = ranked[0] if ranked else None
                best_cos = float(best["cos"]) if best else 0.0
                best_lex = float(best.get("lexical") or 0.0) if best else 0.0
                learning = _is_learning_intent(q)

    domain = _is_learning_or_domain_query(q)
    chitchat = _is_chitchat(q)
    offtopic = _is_offtopic(q)
    has_domain = _has_domain_terms(q)
    identity = _is_identity(q)
    onboarding = _is_onboarding(q)

    intent_info = classify_intent(search_q or q)
    if intent_info["intent"] == INTENT_SOCIAL and search_q and search_q != q_raw:
        intent_info = classify_intent(search_q)
    if intent_info["intent"] == INTENT_SOCIAL and _TECHNICAL_MARKERS.search(search_q or ""):
        intent_info = classify_intent(search_q)
    if intent_info["intent"] not in (INTENT_META, INTENT_IMPLEMENTATION, INTENT_ENTITY_TRIVIA):
        raw_info = classify_intent(q_raw)
        if raw_info["intent"] in (INTENT_META, INTENT_IMPLEMENTATION, INTENT_ENTITY_TRIVIA):
            if intent_info["intent"] != INTENT_THEORY:
                intent_info = raw_info

    intent = intent_info["intent"]
    intent_score = float(intent_info.get("score") or 0.0)

    base = {
        "anchor_id": None, "score": best_cos, "related": ranked,
        "slots": {
            "intent": intent, "intent_score": intent_score, "intent_method": intent_info.get("method"),
        },
        "scope": "skipped",
    }
    if style_stripped:
        base["slots"]["sterile"] = True
        base["slots"]["persona_hijack"] = True

    has_suspicious_terms = bool(re.search(
        r"\b(code|script|scripts|write|generate|provide|give|draft|email|schema|tutorial|install|setup|pseudocode|pseudo-code|dataset|dataset\b|analyze|my\s+data|my\s+dataset|implement|implementation|create)\b",
        q_raw, re.I
    ))
    is_creative = bool(re.search(r"\b(audio|emotional|story|poem|song|fiction|novel|creative|play)\b", q_raw, re.I))
    has_theory_terms = bool(re.search(
        r"\b(matrix|matrices|attention|transformer|gradient|regression|classification|neural|probability|chain\s+rule)\b",
        q_raw, re.I
    ))
    if is_creative and has_theory_terms:
        has_suspicious_terms = False

    if intent in (INTENT_IMPLEMENTATION, INTENT_OUT_OF_DOMAIN, INTENT_ENTITY_TRIVIA, INTENT_META) or has_suspicious_terms:
        if _run_dual_pass_guard(q_raw):
            if intent == INTENT_IMPLEMENTATION or re.search(
                r"\b(code|script|scripts|pseudocode|pseudo-code|function|tutorial|install|deploy|email|draft|schema|config|commands?)\b",
                q_raw, re.I
            ):
                return {
                    "anchor_id": None, "score": 1.0, "related": ranked,
                    "slots": {
                        "intent": INTENT_IMPLEMENTATION, "intent_method": "dual_pass_guard",
                        "closest_concepts": [r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]],
                    },
                    "scope": "no", "route": "out_of_scope", "reason": REASON_IMPLEMENTATION,
                }
            else:
                return {
                    "anchor_id": None, "score": 1.0, "related": ranked,
                    "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "dual_pass_guard"},
                    "scope": "no", "route": "out_of_scope", "reason": REASON_OUT_OF_SCOPE,
                }

    block = intent_to_block_reason(intent, intent_score)
    graph_override = None
    if block == REASON_OUT_OF_SCOPE or intent == INTENT_OUT_OF_DOMAIN:
        graph_override = _graph_block_override(search_q or q, ranked)
    closest_labels = [r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]]

    if block == REASON_META or intent == INTENT_META:
        return {**base, "route": "out_of_scope", "reason": REASON_META, "scope": "no"}

    if not library:
        if block == REASON_IMPLEMENTATION or intent == INTENT_IMPLEMENTATION:
            return {
                **base, "route": "out_of_scope", "reason": REASON_IMPLEMENTATION, "scope": "no",
                "slots": _merge_slots(base["slots"], {"closest_concepts": closest_labels}),
            }
        if graph_override is None:
            if block == REASON_NOT_IN_CORPUS or intent == INTENT_ENTITY_TRIVIA:
                return {
                    **base, "route": "out_of_scope", "reason": REASON_NOT_IN_CORPUS, "scope": "no",
                    "slots": _merge_slots(base["slots"], {"closest_concepts": closest_labels}),
                }
            if block == REASON_OUT_OF_SCOPE or intent == INTENT_OUT_OF_DOMAIN:
                return {
                    **base, "route": "out_of_scope", "reason": REASON_OUT_OF_SCOPE, "scope": "no",
                    "slots": _merge_slots(base["slots"], {"closest_concepts": closest_labels}),
                }
        elif intent in (INTENT_OUT_OF_DOMAIN, INTENT_ENTITY_TRIVIA):
            intent = INTENT_THEORY
            base["slots"]["intent"] = intent
            base["slots"]["intent_method"] = f"{base['slots'].get('intent_method')}+graph_override"

    ood_score = float((intent_info.get("scores") or {}).get(INTENT_OUT_OF_DOMAIN) or 0.0)
    if intent == INTENT_THEORY and best_cos >= 0.55 and ood_score >= intent_score - 0.08 and ood_score >= 0.25:
        recheck = classify_intent(q_raw, force_llm=True)
        if recheck.get("intent") == INTENT_OUT_OF_DOMAIN:
            return {
                **base, "route": "out_of_scope", "reason": REASON_OUT_OF_SCOPE, "scope": "no",
                "slots": _merge_slots(base["slots"], {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": recheck.get("method"), "dual_pass": True}),
            }

    if identity and intent != INTENT_META:
        return {**base, "route": "identity", "reason": "identity", "scope": "yes"}

    if onboarding:
        return {**base, "route": "onboarding", "reason": "onboarding_syllabus", "scope": "yes", "related": ranked}

    if library:
        lib_intent = library["intent"]
        extra_slots = {"limit": library.get("limit", 4), "seed_subject": library.get("seed_subject")}
        if isinstance(library.get("slots"), dict):
            extra_slots.update(library["slots"])
        slots = _merge_slots(base["slots"], extra_slots)
        return {**base, "route": lib_intent, "reason": lib_intent, "slots": slots, "scope": "yes"}

    graph_evidence = _has_strong_graph_evidence(ranked)
    in_scope, scope_reason = is_aiml_in_scope(
        q_raw, chitchat=chitchat, offtopic_keyword=offtopic, has_domain_terms=has_domain,
        strong_anchor=False, best_cos=best_cos, best_lex=best_lex, force_llm=False,
        learning_intent=learning, graph_evidence=graph_evidence,
    )
    if not in_scope and scope_reason == "no_domain_signal_low_similarity":
        return {
            "anchor_id": None, "score": best_cos, "related": ranked,
            "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "early_fast_reject"},
            "scope": "no", "route": "out_of_scope", "reason": REASON_OUT_OF_SCOPE,
        }

    is_small_talk, remaining = _strip_small_talk(q)
    if is_small_talk:
        has_technical_tail = bool(remaining) and bool(_TECHNICAL_MARKERS.search(remaining))
        has_learning_or_domain = _is_learning_intent(remaining) or _has_domain_terms(remaining)
        if has_technical_tail and not has_learning_or_domain:
            return {
                **base, "route": "small_talk", "reason": "conversational_greeting", "score": 1.0,
                "slots": _merge_slots(base["slots"], {"technical_portion": remaining if remaining != q else ""}),
            }

    if chitchat or intent == INTENT_SOCIAL:
        if not (_TECHNICAL_MARKERS.search(search_q or "") or has_domain or learning):
            return {**base, "route": "general_chat", "reason": "chitchat"}

    foreign = _foreign_tokens(search_q or q)
    if foreign and (has_domain or _has_strong_graph_evidence(ranked) or _has_surface_concept_hit(ranked, search_q or q)):
        if offtopic or _run_sanity_guard(q_raw):
            return {
                **base, "route": "out_of_scope", "reason": REASON_OUT_OF_SCOPE, "scope": "no",
                "slots": _merge_slots(base["slots"], {
                    "intent": INTENT_OUT_OF_DOMAIN, "intent_method": "offtopic_mix" if offtopic else "sanity_guard",
                    "foreign_tokens": foreign[:6], "closest_concepts": [r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]],
                }),
            }

    strong_id, strong_score = find_anchor_concept(search_q)
    strong_anchor = bool(strong_id)

    threshold = float(getattr(st, "KILL_SWITCH_THRESHOLD", 0.75)) if st.use_embeddings else 0.50
    has_strong_surface_hit = best_lex >= 0.70
    if best_cos < threshold and not has_strong_surface_hit:
        force_llm = learning and not has_domain and not strong_anchor and not domain
        in_scope, scope_reason = is_aiml_in_scope(
            q, chitchat=False, offtopic_keyword=offtopic, has_domain_terms=has_domain,
            strong_anchor=strong_anchor, best_cos=best_cos, best_lex=best_lex, force_llm=force_llm,
            learning_intent=learning, graph_evidence=graph_evidence,
        )
        if in_scope:
            closest = [r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]]
            return {
                **base, "route": "low_similarity_reject", "reason": "kill_switch_low_similarity_in_scope",
                "score": best_cos, "scope": "yes", "slots": _merge_slots(base["slots"], {"closest_concepts": closest, "query": q}),
            }
        return {**base, "route": "out_of_scope", "reason": f"kill_switch_low_similarity_out_of_scope:{scope_reason}", "scope": "no"}

    force_llm = learning and not has_domain and not strong_anchor and not domain
    in_scope, scope_reason = is_aiml_in_scope(
        q, chitchat=False, offtopic_keyword=offtopic, has_domain_terms=has_domain,
        strong_anchor=strong_anchor, best_cos=best_cos, best_lex=best_lex, force_llm=force_llm,
        learning_intent=learning, graph_evidence=graph_evidence,
    )
    if not in_scope:
        if learning and not offtopic:
            closest = [r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]]
            return {
                **base, "route": "low_similarity_reject", "reason": "not_indexed_learning_topic",
                "score": best_cos, "scope": "soft", "slots": _merge_slots(base["slots"], {"closest_concepts": closest, "query": q}),
            }
        return {**base, "route": "out_of_scope", "reason": f"out_of_scope:{scope_reason}", "scope": "no"}

    target_route, target_anchor, target_score, target_reason = None, None, 0.0, ""
    if strong_id:
        target_route, target_anchor, target_score, target_reason = "graph_strong", strong_id, strong_score, "strong_embed_or_lexical"
    elif domain:
        soft = _select_soft_anchor(ranked, search_q) or best
        target_route, target_anchor, target_score, target_reason = "graph_soft", soft["id"] if soft else None, float(soft.get("cos") or 0.0) if soft else 0.0, "domain_soft_match"
    elif best and best_cos >= st.DOMAIN_SOFT_THRESHOLD + 0.12 and best_lex >= 0.35:
        soft = _select_soft_anchor(ranked, search_q) or best
        target_route, target_anchor, target_score, target_reason = "graph_soft", soft["id"] if soft else None, float(soft.get("cos") or 0.0) if soft else best_cos, "soft_high_confidence"

    if target_route:
        max_cos = max((float(r.get("cos") or 0.0) for r in ranked), default=0.0)
        best_alias = float((best or {}).get("alias_boost") or 0.0)
        best_blended = float((best or {}).get("blended") or 0.0)
        surface_hit = _has_surface_concept_hit(ranked, q)

        hard_miss = (
            st.use_embeddings and target_route == "graph_soft"
            and max_cos < st.REJECT_SIMILARITY_THRESHOLD and best_lex < 0.40
            and best_alias < 0.12 and not surface_hit
        )
        if hard_miss:
            closest = [r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]]
            return {
                **base, "route": "low_similarity_reject", "score": max_cos, "reason": "low_similarity_reject",
                "scope": "yes", "slots": _merge_slots(base["slots"], {"closest_concepts": closest, "query": q}),
            }

        if st.use_embeddings and target_route == "graph_soft" and max_cos < st.REJECT_SIMILARITY_THRESHOLD:
            return {
                **base, "route": "graph_soft", "anchor_id": target_anchor, "score": max_cos, "reason": "partial_coverage_low_cos",
                "scope": "yes", "slots": _merge_slots(base["slots"], {"partial": True, "closest_concepts": [r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]]}),
            }

        out_score = target_score
        if target_route == "graph_soft" and best_blended > out_score:
            out_score = min(1.0, best_blended * 0.5 + out_score * 0.5)

        return {**base, "route": target_route, "anchor_id": target_anchor, "score": out_score, "reason": target_reason, "scope": "yes"}

    if learning:
        closest = [r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]]
        return {
            **base, "route": "low_similarity_reject", "score": best_cos, "reason": "not_indexed_low_signal",
            "scope": "yes", "slots": _merge_slots(base["slots"], {"closest_concepts": closest, "query": q}),
        }

    return {**base, "route": "general_chat", "reason": "low_similarity_open_chat", "scope": "yes"}
