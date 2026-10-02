"""Intent gate package — split from the former intent_gate.py monolith."""

from archipelago.inference import state as st  # noqa: F401  (kept for test monkeypatching)
from archipelago.inference.intent_gate import part02_scoring as scoring  # noqa: F401
from archipelago.inference.intent_gate.part01_labels import (
    ABS_MIN as _ABS_MIN,
)
from archipelago.inference.intent_gate.part01_labels import (
    BLOCK_MIN as _BLOCK_MIN,
)
from archipelago.inference.intent_gate.part01_labels import (
    INTENT_ENTITY_TRIVIA,
    INTENT_IMPLEMENTATION,
    INTENT_LIABILITY,
    INTENT_META,
    INTENT_OUT_OF_DOMAIN,
    INTENT_SOCIAL,
    INTENT_THEORY,
    REASON_IMPLEMENTATION,
    REASON_META,
    REASON_NOT_IN_CORPUS,
    REASON_OUT_OF_SCOPE,
)
from archipelago.inference.intent_gate.part01_labels import (
    MARGIN_MIN as _MARGIN_MIN,
)
from archipelago.inference.intent_gate.part01_labels import (
    PROTOTYPES as _PROTOTYPES,
)
from archipelago.inference.intent_gate.part01_labels import (
    QUERY_CACHE_MAX as _QUERY_CACHE_MAX,
)
from archipelago.inference.intent_gate.part02_scoring import (
    _PROTO_EMB,
    _QUERY_CACHE,
    _blend_scores,
    _ensure_proto_embeddings,
    _normalize,
    _pick,
    _score_embed,
    _score_lexical,
    clear_intent_cache,
)
from archipelago.inference.intent_gate.part03_classify import (
    _llm_classify,
    classify_intent,
    intent_to_block_reason,
)

__all__ = [
    "INTENT_ENTITY_TRIVIA",
    "INTENT_IMPLEMENTATION",
    "INTENT_LIABILITY",
    "INTENT_META",
    "INTENT_OUT_OF_DOMAIN",
    "INTENT_SOCIAL",
    "INTENT_THEORY",
    "REASON_IMPLEMENTATION",
    "REASON_META",
    "REASON_NOT_IN_CORPUS",
    "REASON_OUT_OF_SCOPE",
    "classify_intent",
    "clear_intent_cache",
    "intent_to_block_reason",
]
