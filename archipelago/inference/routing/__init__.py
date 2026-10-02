"""Query routing: graph | library | out_of_scope | general_chat | small_talk.

Defenses scale via embedding/LLM intent prototypes (intent_gate) + embedder
kill-switch — not keyword banlists of forbidden entities.

This package preserves the historical ``routing`` module namespace: every name
that was importable from ``archipelago.inference.routing`` is re-exported here.
"""
from __future__ import annotations

from archipelago.inference import state as st  # noqa: F401
from archipelago.inference.aliases import _clean_query_words, generate_aliases  # noqa: F401
from archipelago.inference.intent_gate import (  # noqa: F401
    INTENT_ENTITY_TRIVIA,
    INTENT_IMPLEMENTATION,
    INTENT_META,
    INTENT_OUT_OF_DOMAIN,
    INTENT_SOCIAL,
    INTENT_THEORY,
    REASON_IMPLEMENTATION,
    REASON_META,
    REASON_NOT_IN_CORPUS,
    REASON_OUT_OF_SCOPE,
    classify_intent,
    intent_to_block_reason,
)
from archipelago.inference.ranking import (  # noqa: F401
    _has_domain_terms,
    _has_strong_graph_evidence,
    _has_surface_concept_hit,
    _is_chitchat,
    _is_identity,
    _is_learning_intent,
    _is_learning_or_domain_query,
    _is_offtopic,
    _is_onboarding,
    _select_soft_anchor,
    find_anchor_concept,
    normalize_user_query,
    rank_concepts,
)
from archipelago.inference.scope_gate import is_aiml_in_scope  # noqa: F401

from .block_override import _graph_block_override  # noqa: F401
from .constants import (  # noqa: F401
    _COVERAGE_STOPWORDS,
    _PERSONA_STYLE_NOISE,
    _PURE_SMALL_TALK_PATTERNS,
    _QUESTION_FRAMING_RE,
    _SANITY_FILLER,
    _SMALL_TALK_PREFIXES,
    _SUGGESTED_QUERY_ANCHORS,
    _TECHNICAL_MARKERS,
)
from .guards import (  # noqa: F401
    _extract_quiz_answers,
    _get_active_concept_from_history,
    _merge_slots,
    _run_dual_pass_guard,
    _strip_persona_style,
    _strip_small_talk,
)
from .library_intent import _detect_library_intent  # noqa: F401
from .multi_topic import parse_multi_topic_query  # noqa: F401
from .resolver import _resolve_query_routing, resolve_query_routing  # noqa: F401
from .sanity import _foreign_tokens, _graph_vocab, _run_sanity_guard  # noqa: F401
from .stages_early import early_route, social_short_circuit  # noqa: F401
from .stages_graph import graph_route  # noqa: F401
from .stages_intent import (  # noqa: F401
    dual_pass_artifact_route,
    dual_pass_ood_route,
    intent_block_route,
)
from .stages_quiz import quiz_route  # noqa: F401
from .stages_scope import pre_scope_route, social_sanity_route  # noqa: F401

__all__ = [
    "resolve_query_routing",
    "_resolve_query_routing",
    "parse_multi_topic_query",
    "_detect_library_intent",
    "early_route",
    "social_short_circuit",
    "quiz_route",
    "dual_pass_artifact_route",
    "intent_block_route",
    "dual_pass_ood_route",
    "pre_scope_route",
    "social_sanity_route",
    "graph_route",
    "_graph_block_override",
    "_foreign_tokens",
    "_graph_vocab",
    "_run_sanity_guard",
    "_strip_small_talk",
    "_strip_persona_style",
    "_merge_slots",
    "_run_dual_pass_guard",
    "_get_active_concept_from_history",
    "_extract_quiz_answers",
]
