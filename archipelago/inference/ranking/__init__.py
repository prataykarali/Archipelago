"""Concept ranking, anchors, and intent heuristics."""

from __future__ import annotations

import re  # noqa: F401

from thefuzz import fuzz  # noqa: F401
import torch  # noqa: F401

from archipelago.inference import state as st  # noqa: F401
from archipelago.inference.aliases import (  # noqa: F401
    _clean_query_words,
    _core_concept_bonus,
    extract_acronym,
    generate_aliases,
)
from archipelago.inference.embeddings import (  # noqa: F401
    _disable_embeddings,
    get_snowflake_embedding,
)

from .part01_plural_tech import (
    _GREETING_PREFIX,
    _IDENTITY_PATTERNS,
    _ONBOARDING_PATTERNS,
    _PLURAL_TECH,
    _POLITE_FILLER,
    _expand_query_for_retrieval,
    _has_domain_terms,
    _is_chitchat,
    _is_identity,
    _is_learning_intent,
    _is_learning_or_domain_query,
    _is_offtopic,
    _is_onboarding,
    _score_lexical_fit,
    normalize_user_query,
    rank_concepts,
)
from .part02_find_anchor_concept import (
    _has_strong_graph_evidence,
    _has_surface_concept_hit,
    _select_soft_anchor,
    find_anchor_concept,
)

__all__ = [
    "_GREETING_PREFIX",
    "_IDENTITY_PATTERNS",
    "_ONBOARDING_PATTERNS",
    "_PLURAL_TECH",
    "_POLITE_FILLER",
    "_expand_query_for_retrieval",
    "_has_domain_terms",
    "_has_strong_graph_evidence",
    "_has_surface_concept_hit",
    "_is_chitchat",
    "_is_identity",
    "_is_learning_intent",
    "_is_learning_or_domain_query",
    "_is_offtopic",
    "_is_onboarding",
    "_score_lexical_fit",
    "_select_soft_anchor",
    "find_anchor_concept",
    "normalize_user_query",
    "rank_concepts",
]
