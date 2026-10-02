"""Intent classification: LLM override, structural rescues, and block mapping."""

from __future__ import annotations

import re
from typing import Any

from archipelago.inference.intent_gate import part02_scoring as scoring
from archipelago.inference.intent_gate.part01_labels import (
    ABS_MIN,
    BLOCK_MIN,
    BLOCKING_INTENTS,
    CELEBRITY_TRIVIA_MIN_SCORE,
    EMOTIONAL_OOD_MARGIN,
    EMOTIONAL_OOD_SCORE,
    HARD_IMPL_MIN_SCORE,
    INTENT_ENTITY_TRIVIA,
    INTENT_IMPLEMENTATION,
    INTENT_LIABILITY,
    INTENT_META,
    INTENT_OUT_OF_DOMAIN,
    INTENT_SOCIAL,
    INTENT_THEORY,
    LLM_LABEL_ALIASES,
    LLM_MAX_TOKENS,
    LLM_OVERRIDE_MIN_MARGIN,
    LLM_OVERRIDE_MIN_SCORE,
    LLM_SYSTEM_PROMPT,
    LLM_TIMEOUT_SECONDS,
    MARGIN_MIN,
    OOD_TIEBREAK_DELTA,
    OOD_TIEBREAK_FLOOR,
    PEDAGOGY_RESCUE_MIN_MARGIN,
    PEDAGOGY_RESCUE_MIN_SCORE,
    PERSONA_THEORY_DELTA,
    QUERY_CACHE_MAX,
    REASON_IMPLEMENTATION,
    REASON_META,
    REASON_NOT_IN_CORPUS,
    REASON_OUT_OF_SCOPE,
    SHORT_GREETING_MAX_WORDS,
)

_PUNCT_STRIP = " ,.!?"
_WHITESPACE_RE = re.compile(r"\s+")
_ANSWER_SPLIT_RE = re.compile(r"[\s,.\n!?;:]+")


def _llm_classify(query: str) -> str | None:
    """Cheap multi-class zero-shot via LLM Gateway. One token answer."""
    try:
        from archipelago.inference.llm_gateway import gateway_chat

        ans = gateway_chat(
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            purpose="routing",
            temperature=0.0,
            max_tokens=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        ans = (ans or "").strip().lower()
        token = _ANSWER_SPLIT_RE.split(ans, maxsplit=1)[0] if ans else ""
        if token in LLM_LABEL_ALIASES:
            return LLM_LABEL_ALIASES[token]
        for key, lab in LLM_LABEL_ALIASES.items():
            if key in ans:
                return lab
        return None
    except Exception as e:
        print(f"intent LLM classify failed: {e}")
        return None


def _strip_style_noise(q_raw: str) -> str:
    """Remove persona/style noise, keeping the original if nothing is left."""
    q = scoring.STYLE_NOISE_RE.sub(" ", q_raw)
    return _WHITESPACE_RE.sub(" ", q).strip(_PUNCT_STRIP) or q_raw


def _is_creative_theory_mix(q_raw: str) -> bool:
    """A creative ask that still carries theory terms must not hard-block."""
    return bool(scoring.CREATIVE_RE.search(q_raw)) and bool(scoring.THEORY_TERMS_RE.search(q_raw))


def _resolve_matrix_rescue(intent: str, scores: dict[str, float], q: str) -> str | None:
    """Pull math 'matrix' questions back from OOD film prototypes."""
    if intent != INTENT_OUT_OF_DOMAIN or not scoring.MATRIX_RE.search(q):
        return None
    math_cues = scoring.MATRIX_MATH_CUES_RE.search(q)
    film_cues = scoring.MATRIX_FILM_CUES_RE.search(q)
    if math_cues and not film_cues:
        return "math_matrix_rescue"
    if not film_cues and scoring.MATRIX_DEF_ASK_RE.search(q):
        return "math_matrix_rescue"
    if (
        not film_cues
        and float(scores.get(INTENT_THEORY) or 0)
        >= float(scores.get(INTENT_OUT_OF_DOMAIN) or 0) * scoring.MATRIX_THEORY_RATIO
        and scoring.MATRIX_QUESTION_WORDS_RE.search(q)
    ):
        return "math_matrix_rescue"
    return None


def classify_intent(query: str, *, force_llm: bool = False) -> dict[str, Any]:
    """Return {intent, score, margin, method, scores}.

    Blocking intents (implementation, out_of_domain, entity_trivia, meta) should
    short-circuit the graph. theory/social continue into the existing router.
    """
    q_raw = (query or "").strip()
    # Strip persona style before scoring so slang/emoji cannot dominate OOD
    q = _strip_style_noise(q_raw)
    key = scoring._normalize(q_raw)  # cache on original
    if not key:
        return {
            "intent": INTENT_SOCIAL,
            "score": 1.0,
            "margin": 1.0,
            "method": "empty",
            "scores": {},
        }
    if key in scoring._QUERY_CACHE and not force_llm:
        scoring._QUERY_CACHE.move_to_end(key)
        return dict(scoring._QUERY_CACHE[key])

    lex = scoring._score_lexical(q)
    emb = None if force_llm else scoring._score_embed(q)
    scores, method = scoring._blend_scores(lex, emb)

    intent, score, margin = scoring._pick(scores)

    # ── Structural rescues (not entity keyword lists) ─────────────────
    pedagogy = bool(scoring.PEDAGOGY_RE.search(q))
    hard_impl = bool(scoring.HARD_IMPL_RE.search(q_raw))

    if _is_creative_theory_mix(q_raw):
        hard_impl = False

    # Celebrity / awards / bio trivia must stay entity_trivia even if the query
    # says "according to the paper" (pedagogy surface form with non-theory ask).
    celebrity_trivia = bool(scoring.CELEBRITY_TRIVIA_RE.search(q_raw))

    # Pedagogy/paper-theory always wins over weak embed "implementation/entity"
    # — except celebrity/infra trivia dressed as "according to the paper".
    if pedagogy and not hard_impl and not celebrity_trivia:
        if intent in (INTENT_IMPLEMENTATION, INTENT_ENTITY_TRIVIA, INTENT_OUT_OF_DOMAIN):
            intent = INTENT_THEORY
            score = max(score, float(scores.get(INTENT_THEORY) or 0.0), PEDAGOGY_RESCUE_MIN_SCORE)
            margin = max(margin, PEDAGOGY_RESCUE_MIN_MARGIN)
            method = f"{method}+pedagogy_rescue"
    if celebrity_trivia and not hard_impl:
        intent = INTENT_ENTITY_TRIVIA
        score = max(score, CELEBRITY_TRIVIA_MIN_SCORE)
        method = f"{method}+celebrity_trivia"

    # Hard code/deploy surface → implementation even if embed is mushy
    if hard_impl:
        intent = INTENT_IMPLEMENTATION
        score = max(score, HARD_IMPL_MIN_SCORE)
        method = f"{method}+hard_impl"

    # ── Emotional / homework-distress short-circuit ──────────────────────
    if scoring.EMOTIONAL_HOMEWORK_OOD_RE.search(q_raw):
        return {
            "intent": INTENT_OUT_OF_DOMAIN,
            "score": EMOTIONAL_OOD_SCORE,
            "margin": EMOTIONAL_OOD_MARGIN,
            "method": "emotional_homework_ood",
            "scores": {k: float(v) for k, v in scores.items()},
        }

    # Short pure greetings: trust social prototype, never LLM-override to theory
    if (
        intent == INTENT_SOCIAL
        and len(q.split()) <= SHORT_GREETING_MAX_WORDS
        and score > 0
        and all(v <= score for v in scores.values())
    ):
        needs_llm = False
    else:
        # Only call the tiny LLM when prototypes are genuinely ambiguous.
        clear_winner = score >= ABS_MIN and margin >= MARGIN_MIN
        # Never LLM-override a pedagogy rescue or hard_impl
        if pedagogy or hard_impl:
            needs_llm = False
        else:
            needs_llm = force_llm or not clear_winner

    if needs_llm:
        llm = _llm_classify(q)
        if llm is not None:
            proto_intent, proto_score, proto_margin = intent, score, margin
            if (
                not force_llm
                and proto_score >= ABS_MIN
                and proto_margin >= MARGIN_MIN
                and proto_intent != INTENT_SOCIAL
                and llm != proto_intent
            ):
                pass
            else:
                intent = llm
                score = max(score, LLM_OVERRIDE_MIN_SCORE)
                margin = max(margin, LLM_OVERRIDE_MIN_MARGIN)
                method = f"{method}+llm" if method != "empty" else "llm"

    if (
        intent in (INTENT_IMPLEMENTATION, INTENT_ENTITY_TRIVIA)
        and not hard_impl
        and not celebrity_trivia
    ):
        # Tiny-SLM "who funds X"/"build Y" verdicts on pedagogy-flavored asks are
        # unreliable; downgrade to theory so the router can pin a graph concept.
        intent = INTENT_THEORY
        score = max(score, float(scores.get(INTENT_THEORY) or 0.0), PEDAGOGY_RESCUE_MIN_SCORE)
        method = f"{method}+impl_to_theory_downgrade"

    # Film/plot vs math theory: prefer OOD only with clear entertainment framing.
    if intent == INTENT_THEORY:
        ood = float(scores.get(INTENT_OUT_OF_DOMAIN) or 0.0)
        if (
            ood >= max(score - OOD_TIEBREAK_DELTA, OOD_TIEBREAK_FLOOR)
            and scoring.ENTERTAINMENT_RE.search(q)
            and not pedagogy
        ):
            intent = INTENT_OUT_OF_DOMAIN
            method = f"{method}+ood_tiebreak"

    matrix_rescue = _resolve_matrix_rescue(intent, scores, q)
    if matrix_rescue:
        intent = INTENT_THEORY
        method = f"{method}+{matrix_rescue}"

    # Persona/style residue: if theory score is close to OOD after strip, prefer theory
    if intent == INTENT_OUT_OF_DOMAIN and scoring.STYLE_NOISE_RE.search(q_raw):
        if (
            float(scores.get(INTENT_THEORY) or 0)
            >= float(scores.get(INTENT_OUT_OF_DOMAIN) or 0) - PERSONA_THEORY_DELTA
        ):
            intent = INTENT_THEORY
            method = f"{method}+persona_theory_rescue"

    result = {
        "intent": intent,
        "score": float(score),
        "margin": float(margin),
        "method": method,
        "scores": {k: float(v) for k, v in scores.items()},
    }
    scoring._QUERY_CACHE[key] = result
    while len(scoring._QUERY_CACHE) > QUERY_CACHE_MAX:
        scoring._QUERY_CACHE.popitem(last=False)
    return dict(result)


def intent_to_block_reason(intent: str, score: float) -> str | None:
    """Map intent → out_of_scope reason tag, or None if routing should continue."""
    if score < BLOCK_MIN and intent not in BLOCKING_INTENTS:
        return None
    if intent == INTENT_IMPLEMENTATION:
        return REASON_IMPLEMENTATION
    if intent == INTENT_ENTITY_TRIVIA:
        return REASON_NOT_IN_CORPUS
    if intent == INTENT_LIABILITY:
        return REASON_NOT_IN_CORPUS
    if intent == INTENT_OUT_OF_DOMAIN:
        return REASON_OUT_OF_SCOPE
    if intent == INTENT_META:
        return REASON_META
    return None
