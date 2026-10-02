"""Concept ranking, anchors, and intent heuristics."""
from __future__ import annotations

import re  # noqa: F401
import torch  # noqa: F401
from thefuzz import fuzz  # noqa: F401
from archipelago.inference import state as st  # noqa: F401
from archipelago.inference.aliases import (
    extract_acronym, generate_aliases, _core_concept_bonus, _clean_query_words,
)  # noqa: F401
from archipelago.inference.embeddings import get_snowflake_embedding, _disable_embeddings  # noqa: F401

from .part01_plural_tech import (  # noqa: F401
    _PLURAL_TECH,
    _GREETING_PREFIX,
    _POLITE_FILLER,
    _IDENTITY_PATTERNS,
    _ONBOARDING_PATTERNS,
    normalize_user_query,
    _is_identity,
    _is_onboarding,
    _is_chitchat,
    _has_domain_terms,
    _is_learning_intent,
    _is_offtopic,
    _is_learning_or_domain_query,
    _expand_query_for_retrieval,
    _score_lexical_fit,
    rank_concepts,
)
from .part02_find_anchor_concept import (  # noqa: F401
    find_anchor_concept,
    _has_surface_concept_hit,
    _has_strong_graph_evidence,
    _select_soft_anchor,
)

__all__ = ["_PLURAL_TECH", "_GREETING_PREFIX", "_POLITE_FILLER", "_IDENTITY_PATTERNS", "_ONBOARDING_PATTERNS", "normalize_user_query", "_is_identity", "_is_onboarding", "_is_chitchat", "_has_domain_terms", "_is_learning_intent", "_is_offtopic", "_is_learning_or_domain_query", "_expand_query_for_retrieval", "_score_lexical_fit", "rank_concepts", "find_anchor_concept", "_has_surface_concept_hit", "_has_strong_graph_evidence", "_select_soft_anchor"]
