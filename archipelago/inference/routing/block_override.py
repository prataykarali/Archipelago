"""Graph-grounded veto of intent-gate hard blocks."""
from __future__ import annotations

from archipelago.inference import state as st
from archipelago.inference.aliases import _clean_query_words, generate_aliases
from archipelago.inference.ranking import normalize_user_query

from .constants import _COVERAGE_STOPWORDS, _QUESTION_FRAMING_RE


def _graph_block_override(query: str, ranked: list) -> list | None:
    """Graph-grounded veto of intent-gate hard blocks.

    Returns the matched top labels when the graph itself clearly covers the
    query (alias/acronym/core hit AND the match explains most of the query's
    content words) — meaning a "not in scope" verdict from the tiny classifier
    is wrong and routing should continue. Returns None when the graph has
    nothing genuinely related, so real off-topic blocks still stand.
    """
    if not ranked:
        return None
    norm = normalize_user_query(query)
    core = _QUESTION_FRAMING_RE.sub("", norm).strip(" ?!.") or norm
    tokens = {
        t for t in _clean_query_words(core)
        if t not in _COVERAGE_STOPWORDS
    }
    if not tokens:
        return None
    for r in ranked[:5]:
        alias_boost = float(r.get("alias_boost") or 0.0)
        core_boost = float(r.get("core_boost") or 0.0)
        lexical = float(r.get("lexical") or 0.0)
        if alias_boost < 0.26 and core_boost < 0.35 and lexical < 0.72:
            continue
        concept = st.CONCEPTS_DATA.get(r.get("id") or "", {})
        aliases = concept.get("aliases") or generate_aliases(concept)
        alias_tokens = set()
        for a in aliases:
            alias_tokens |= _clean_query_words((a or "").lower())
        label_tokens = _clean_query_words(
            (r.get("label") or r.get("name") or "").lower()
        )
        alias_tokens |= label_tokens
        matched = {
            t for t in tokens
            if t in alias_tokens or (t.endswith("s") and t[:-1] in alias_tokens)
        }
        if len(matched) / len(tokens) >= 0.5:
            return [
                x.get("label") or x.get("name") or x.get("id")
                for x in ranked[:3]
            ]
    return None
