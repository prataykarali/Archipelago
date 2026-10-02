"""Intent-gate stages: dual-pass artifact guard, hard blocks, OOD kill-switch."""
from __future__ import annotations

import re

from archipelago.inference.intent_gate import (
    INTENT_IMPLEMENTATION,
    INTENT_META,
    INTENT_OUT_OF_DOMAIN,
    INTENT_ENTITY_TRIVIA,
    INTENT_THEORY,
    REASON_IMPLEMENTATION,
    REASON_META,
    REASON_NOT_IN_CORPUS,
    REASON_OUT_OF_SCOPE,
)

from . import _deps as _rt
from .guards import _merge_slots


def dual_pass_artifact_route(
    q_raw: str, search_q: str, history: list | None, intent: str, base: dict, ranked: list
) -> dict | None:
    """Suspect-term dual-pass LLM guard → implementation / OOD refusal."""
    has_suspicious_terms = bool(re.search(
        r"\b(code|script|scripts|write|generate|provide|give|draft|email|schema|tutorial|"
        r"install|setup|pseudocode|pseudo-code|dataset|dataset\b|analyze|my\s+data|my\s+dataset|"
        r"implement|implementation|create)\b",
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
        guard_input = search_q if (history and search_q and search_q != q_raw) else q_raw
        if _rt._run_dual_pass_guard(guard_input):
            # Artifact/procedural request confirmed → implementation refusal
            # (never the generic OOS reason: the safety net must not soften it).
            if intent == INTENT_IMPLEMENTATION or re.search(
                r"\b(code|script|scripts|pseudocode|pseudo-code|function|tutorial|"
                r"install|deploy|email|draft|schema|config|commands?)\b",
                q_raw, re.I
            ):
                return {
                    "anchor_id": None,
                    "score": 1.0,
                    "related": ranked,
                    "slots": {
                        "intent": INTENT_IMPLEMENTATION,
                        "intent_method": "dual_pass_guard",
                        "closest_concepts": [
                            r.get("label") or r.get("name") or r.get("id")
                            for r in ranked[:3]
                        ],
                    },
                    "scope": "no",
                    "route": "out_of_scope",
                    "reason": REASON_IMPLEMENTATION,
                }
            else:
                return {
                    "anchor_id": None,
                    "score": 1.0,
                    "related": ranked,
                    "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "dual_pass_guard"},
                    "scope": "no",
                    "route": "out_of_scope",
                    "reason": REASON_OUT_OF_SCOPE,
                }
    return None


def intent_block_route(
    q_raw: str,
    q: str,
    search_q: str,
    ranked: list,
    intent: str,
    intent_score: float,
    base: dict,
    library: dict | None,
) -> tuple[dict | None, str, dict]:
    """Intent-gate hard blocks, with the graph-coverage veto for OOD verdicts.

    Returns ``(early_response_or_None, intent, base)`` — the graph override may
    rewrite the intent to THEORY and annotate the base slots.
    """
    block = _rt.intent_to_block_reason(intent, intent_score)
    graph_override = None
    if block == REASON_OUT_OF_SCOPE or intent == INTENT_OUT_OF_DOMAIN:
        # OOD verdicts only — entity/authority trivia stays blocked even when
        # the graph covers the mentioned concept ("PyTorch version for LoRA").
        graph_override = _rt._graph_block_override(search_q or q, ranked)
    closest_labels = [
        r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]
    ]
    # Meta blocks before identity so "system constraints" never becomes identity chat
    if block == REASON_META or intent == INTENT_META:
        return {
            **base,
            "route": "out_of_scope",
            "reason": REASON_META,
            "scope": "no",
        }, intent, base
    if not library:
        if block == REASON_IMPLEMENTATION or intent == INTENT_IMPLEMENTATION:
            return {
                **base,
                "route": "out_of_scope",
                "reason": REASON_IMPLEMENTATION,
                "scope": "no",
                "slots": _merge_slots(base["slots"], {
                    "closest_concepts": closest_labels,
                }),
            }, intent, base
        if graph_override is None:
            if block == REASON_NOT_IN_CORPUS or intent == INTENT_ENTITY_TRIVIA:
                return {
                    **base,
                    "route": "out_of_scope",
                    "reason": REASON_NOT_IN_CORPUS,
                    "scope": "no",
                    "slots": _merge_slots(base["slots"], {
                        "closest_concepts": closest_labels,
                    }),
                }, intent, base
            if block == REASON_OUT_OF_SCOPE or intent == INTENT_OUT_OF_DOMAIN:
                return {
                    **base,
                    "route": "out_of_scope",
                    "reason": REASON_OUT_OF_SCOPE,
                    "scope": "no",
                    "slots": _merge_slots(base["slots"], {
                        "closest_concepts": closest_labels,
                    }),
                }, intent, base
        elif intent in (INTENT_OUT_OF_DOMAIN, INTENT_ENTITY_TRIVIA):
            # Continue as theory: the graph knows this topic.
            intent = INTENT_THEORY
            base["slots"]["intent"] = intent
            base["slots"]["intent_method"] = (
                f"{base['slots'].get('intent_method')}+graph_override"
            )
    return None, intent, base


def dual_pass_ood_route(
    q_raw: str, intent: str, intent_score: float, intent_info: dict, best_cos: float, base: dict
) -> dict | None:
    """Dual-pass kill-switch: high concept cosine but intent near-OOD."""
    ood_score = float((intent_info.get("scores") or {}).get(INTENT_OUT_OF_DOMAIN) or 0.0)
    if (
        intent == INTENT_THEORY
        and best_cos >= 0.55
        and ood_score >= intent_score - 0.08
        and ood_score >= 0.25
    ):
        # Re-check with LLM when margin is thin
        recheck = _rt.classify_intent(q_raw, force_llm=True)
        if recheck.get("intent") == INTENT_OUT_OF_DOMAIN:
            return {
                **base,
                "route": "out_of_scope",
                "reason": REASON_OUT_OF_SCOPE,
                "scope": "no",
                "slots": _merge_slots(base["slots"], {
                    "intent": INTENT_OUT_OF_DOMAIN,
                    "intent_method": recheck.get("method"),
                    "dual_pass": True,
                }),
            }
    return None
