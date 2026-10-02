"""Prototype embedding, lexical scoring, and structural signal regexes."""

from __future__ import annotations

from collections import OrderedDict
import re
from typing import Any

import torch
import torch.nn.functional as F

from archipelago.inference import state as st
from archipelago.inference.intent_gate.part01_labels import PROTOTYPES

# In-process caches
_PROTO_EMB: dict[str, torch.Tensor] | None = None  # label -> (n, d) normalized
_QUERY_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_TOP_K_PROTOTYPES = 2
_LEXICAL_JACCARD = 1.0
_DISTINCTIVE_OVERLAP_WEIGHT = 0.08

# Offline lexical fallback: content words carry the signal.
STOP_WORDS = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "in",
    "for",
    "and",
    "or",
    "is",
    "are",
    "what",
    "how",
    "do",
    "i",
    "me",
    "my",
    "this",
    "that",
    "who",
    "which",
    "you",
    "your",
    "we",
    "our",
    "us",
    "it",
    "its",
    "he",
    "she",
    "they",
    "them",
    "their",
    "about",
    "with",
    "at",
    "by",
    "from",
    "on",
    "over",
    "please",
    "good",
    "morning",
    "evening",
    "afternoon",
    "night",
    "can",
    "could",
    "would",
    "should",
    "will",
    "shall",
    "may",
    "might",
    "must",
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank",
    "greetings",
    "welcome",
    "tell",
    "neural",
    "network",
    "networks",
    "ai",
    "ml",
    "learning",
    "machine",
    "deep",
    "gru",
    "lstm",
    "lora",
    "bert",
    "gpt",
    "rag",
    "cnn",
    "rnn",
    "graphrag",
}

# Pedagogical / paper-theory language — never hard-block as implementation/entity
PEDAGOGY_RE = re.compile(
    r"(?:"
    r"\b(?:theoretical|theory|curriculum|prerequisite|prerequisites|foundational|"
    r"upstream|downstream|stepping\s+stones|learning\s+path|map\s+the\s+path|"
    r"mathematical\s+definition|strict(?:ly)?\s+mathematical|exactly\s+as\s+(?:it\s+is\s+)?"
    r"described|according\s+to\s+the\s+(?:\w+\s+)?(?:paper|text|library|deisenroth)|"
    r"as\s+detailed\s+in\s+the\s+library|conceptually\s+connect|"
    r"what\s+(?:is|are)\s+the\s+(?:theoretical|math)|"
    r"define\s+the|purpose\s+of\s+the\s+\[?cls\]?\s+token|"
    r"rank\s+decomposition|self-?attention|masked\s+language|"
    r"covariance\s+matrix|orthonormal|gaussian\s+distribution|"
    r"marginal\s+probability|maximum\s+likelihood|"
    r"queries?,?\s+keys?,?\s+and\s+values?|"
    r"implement\s+(?:lora|graphrag|transformer|attention)\b"
    r")\b"
    r")",
    re.I,
)

# Hard implementation surface signals (code/deploy) — scalable structure, not entity names
HARD_IMPL_RE = re.compile(
    r"(?:"
    r"\b(?:write|generate|provide|give\s+me|draft|compose|outline|create|build)\b.{0,50}\b(?:script|code|dockerfile|scraper|"
    r"table|sql|database|function|program|query|pseudocode|pseudo-code|email|essay|letter|homework|draft|schema|config|tutorial|commands?)\b|"
    r"\b(?:create|build)\s+(?:a\s+)?(?:sql\s+)?table\b|"
    r"\b(?:bash|shell|python|cypher|git|sql)\s+(?:script|code|commands?|table)\b|"
    r"\bci/?cd\b|"
    r"\bcommands?\s+to\s+(?:start|run|launch|deploy|train)\b|"
    r"\b(?:dockerfile|docker\s+compose|docker\s+container|pip\s+install|apt-get)\b|"
    r"\bhow\s+(?:do\s+i|can\s+i|to)\s+(?:install|deploy|integrate|configure|setup|set\s+up)\b|"
    r"\bhelp\s+me\s+(?:install|deploy|integrate|configure|setup|set\s+up)\b|"
    r"\bstep[-\s]?by[-\s]?step\s+tutorial\b|"
    r"\btraining\s+loop\b|"
    r"\bweb\s+scraper\b"
    r")",
    re.I,
)

# Style noise stripped before intent (persona hijack must not flip theory → OOD)
STYLE_NOISE_RE = re.compile(
    r"(?:"
    r"using\s+gen\s*z\s+slang|gen\s*z\s+slang|using\s+slang|in\s+slang|"
    r"(?:a\s+)?bunch\s+of\s+emojis|lots\s+of\s+emojis|use\s+emojis|with\s+emojis|"
    r"explain\s+like\s+i'?m\s+5|\beli5\b"
    r")",
    re.I,
)

# Therapy-adjacent distress plus a study cue → out_of_domain even when the
# pedagogy surface form would otherwise rescue it.
EMOTIONAL_HOMEWORK_OOD_RE = re.compile(
    r"\b(?:"
    r"crying|sob|bawl|bawling|weep|weeping|tears?|break.?down|break.?ing\s+down|"
    r"frustrat(e|ed|ion|\s+and.*cry)\b|"
    r"anxiety|anxious|panic|overwhelm|exhaust(ed|e)?d\s+by\s+study|"
    r"help\s+me\s+.{0,20}(?:homework|assignment|exam|test|quiz|grade|study|math)\b|"
    r"why\s+is\s+(?:this|calculus|math|algebra|statistics|physics|chemistry|biology|organic|gen)\b|"
    r"i\s+(?:can'?t?|can'?t|unable\s+to|cannot)\s+(?:get|understand|do|finish|study)\b|"
    r"i\s+don'?t\s+(?:get|understand|get\s+it|cope|do)\b|"
    r"please\s+comfort|please\s+help|please\s+tell\s+me\s+what\s+to\s+do|"
    r"i'?m\s+so\s+(?:sad|stressed|overwhelmed|scared|frustrat|anxious|hurt)\b"
    r")\b"
)

CREATIVE_RE = re.compile(r"\b(audio|emotional|story|poem|song|fiction|novel|creative|play)\b", re.I)
THEORY_TERMS_RE = re.compile(
    r"\b(matrix|matrices|attention|transformer|gradient|regression|classification|neural|probability|chain\s+rule)\b",
    re.I,
)
CELEBRITY_TRIVIA_RE = re.compile(
    r"\b(?:awards?\s+did|taylor\s+swift|personal\s+biograph|biographies?\s+of|"
    r"how\s+much\s+(?:money|did\s+it\s+cost)|corporate\s+role|"
    r"engineering\s+team|ec2\s+instances?|leaderboard|"
    r"internal\s+infrastructure|infrastructure\s+does\s+[A-Z]|"
    r"specific\s+engineering\s+team|api.{0,30}(?:implement|backend)|"
    r"(?:backend|infrastructure).{0,30}(?:company|organization))\b",
    re.I,
)
ENTERTAINMENT_RE = re.compile(
    r"\b(movie|film|plot|cinema|recipe|president|aspirin|joke|"
    r"summarize\s+the\s+(?:plot|movie)|side\s+effects)\b",
    re.I,
)
MATRIX_RE = re.compile(r"\bmatrix\b", re.I)
MATRIX_MATH_CUES_RE = re.compile(
    r"\b(?:linear\s+algebra|covariance|eigen|determinant|rank|"
    r"decomposition|orthonormal|jacobian|mathematical|definition|"
    r"formula|tensor|vector\s+space|what\s+is\s+a\s+matrix)\b",
    re.I,
)
MATRIX_FILM_CUES_RE = re.compile(
    r"\b(?:movie|film|plot|cinema|keanu|neo|morpheus|summarize)\b",
    re.I,
)
MATRIX_DEF_ASK_RE = re.compile(r"\bwhat\s+is\s+a\s+matrix\b", re.I)
MATRIX_QUESTION_WORDS_RE = re.compile(r"\b(?:definition|math|algebra|explain|what\s+is)\b", re.I)
MATRIX_THEORY_RATIO = 0.7


def _normalize(q: str) -> str:
    return re.sub(r"\s+", " ", (q or "").strip().lower())


def _content_tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 1}


def _ensure_proto_embeddings() -> dict[str, torch.Tensor] | None:
    """Embed all prototypes once with the live Snowflake model."""
    global _PROTO_EMB
    if _PROTO_EMB is not None:
        return _PROTO_EMB
    if not st.use_embeddings or st.embed_model is None:
        return None
    from archipelago.inference.embeddings import get_snowflake_embedding

    labels = list(PROTOTYPES)
    all_texts = [text for texts in PROTOTYPES.values() for text in texts]
    embedded = get_snowflake_embedding(all_texts)
    if embedded is None or len(embedded) != len(all_texts):
        return None
    out: dict[str, torch.Tensor] = {}
    offset = 0
    for label in labels:
        count = len(PROTOTYPES[label])
        stacked = embedded[offset : offset + count]
        offset += count
        if not isinstance(stacked, torch.Tensor):
            stacked = torch.as_tensor(stacked)
        stacked = F.normalize(stacked.float(), p=2, dim=1)
        out[label] = stacked
    _PROTO_EMB = out
    return _PROTO_EMB


def clear_intent_cache() -> None:
    global _PROTO_EMB
    _PROTO_EMB = None
    _QUERY_CACHE.clear()


def _score_embed(query: str) -> dict[str, float] | None:
    """Mean of top-2 prototype cosines per label. None if embedder unavailable."""
    protos = _ensure_proto_embeddings()
    if protos is None:
        return None
    from archipelago.inference.embeddings import get_snowflake_embedding

    qe = get_snowflake_embedding(query)
    if qe is None:
        return None
    q = F.normalize(qe.float().unsqueeze(0), p=2, dim=1)  # (1, d)
    scores: dict[str, float] = {}
    for label, mat in protos.items():
        sims = torch.mm(q, mat.T).squeeze(0)  # (n,)
        topk = torch.topk(sims, k=min(_TOP_K_PROTOTYPES, sims.numel())).values
        scores[label] = float(topk.mean().item())
    return scores


def _score_lexical(query: str) -> dict[str, float]:
    """Offline fallback: token Jaccard vs prototypes (good enough for unit tests)."""
    q_tokens = _content_tokens(query)
    if not q_tokens:
        return dict.fromkeys(PROTOTYPES, 0.0)

    filtered_q_tokens = q_tokens - STOP_WORDS if q_tokens - STOP_WORDS else q_tokens

    scores: dict[str, float] = {}
    for label, texts in PROTOTYPES.items():
        best = 0.0
        for t in texts:
            t_tokens = _content_tokens(t)
            if not t_tokens:
                continue
            filtered_t_tokens = t_tokens - STOP_WORDS if t_tokens - STOP_WORDS else t_tokens
            inter = len(filtered_q_tokens & filtered_t_tokens)
            union = len(filtered_q_tokens | filtered_t_tokens) or _LEXICAL_JACCARD
            j = inter / union
            # Extra weight for distinctive overlaps
            distinctive = filtered_q_tokens & filtered_t_tokens - STOP_WORDS
            j += _DISTINCTIVE_OVERLAP_WEIGHT * len(distinctive)
            best = max(best, j)
        scores[label] = best
    return scores


def _pick(scores: dict[str, float]) -> tuple[str, float, float]:
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_l, best_s = ordered[0]
    second_s = ordered[1][1] if len(ordered) > 1 else 0.0
    return best_l, best_s, best_s - second_s


_LEXICAL_WEIGHT = 0.45
_EMBED_WEIGHT = 0.55


def _blend_scores(
    lex: dict[str, float], emb: dict[str, float] | None
) -> tuple[dict[str, float], str]:
    """Blend lexical + embed so pedagogy word overlap rescues weak embed margins."""
    if emb is None:
        return lex, "lexical"
    labels = set(lex) | set(emb)
    out = {}
    for lab in labels:
        out[lab] = _LEXICAL_WEIGHT * float(lex.get(lab) or 0.0) + _EMBED_WEIGHT * float(
            emb.get(lab) or 0.0
        )
    return out, "hybrid"
