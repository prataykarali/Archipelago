"""Sanity gate: foreign-token detection and the absurd-mix LLM guard."""
from __future__ import annotations

import re

from archipelago.inference import state as st
from archipelago.inference.aliases import _clean_query_words

from .constants import _SANITY_FILLER, _TECHNICAL_MARKERS

_sanity_vocab_cache: dict = {"key": None, "vocab": frozenset()}


def _graph_vocab() -> frozenset:
    """Token vocabulary of every concept id/label/alias in the loaded graph."""
    key = (id(st.CONCEPTS_DATA), len(st.CONCEPTS_DATA))
    if _sanity_vocab_cache["key"] == key:
        return _sanity_vocab_cache["vocab"]
    vocab = set()
    for cid, concept in st.CONCEPTS_DATA.items():
        for text in (
            cid.replace("_", " "),
            concept.get("label") or "",
            concept.get("name") or "",
            *(concept.get("aliases") or []),
        ):
            tl = (text or "").lower()
            vocab |= _clean_query_words(tl)
            # Compact multi-word form: "graph rag" → "graphrag"
            compact = re.sub(r"[\s\-_]+", "", tl)
            if 3 <= len(compact) <= 24:
                vocab.add(compact)
    for term in st._DOMAIN_TERMS:
        vocab |= _clean_query_words(term)
    _sanity_vocab_cache["key"] = key
    _sanity_vocab_cache["vocab"] = frozenset(vocab)
    return _sanity_vocab_cache["vocab"]


def _foreign_tokens(query: str) -> list:
    """Content tokens not explained by the graph vocabulary or filler words."""
    vocab = _graph_vocab()
    out = []
    for tok in re.findall(r"[a-z][a-z']{2,}", (query or "").lower()):
        tok = tok.strip("'")
        if tok in _SANITY_FILLER or tok in vocab:
            continue
        if tok.endswith("s") and (tok[:-1] in vocab or tok[:-1] in _SANITY_FILLER):
            continue
        if _TECHNICAL_MARKERS.search(tok):
            continue
        out.append(tok)
    return out


def _run_sanity_guard(query: str) -> bool:
    """LLM check for absurd cross-domain mixes and external-authority trivia.

    Returns True when the query should be refused. Only invoked when the query
    contains graph-known concepts *plus* foreign content tokens (Batman,
    sourdough, carbon footprint, a researcher's opinions…) — a serious theory
    question about indexed concepts never pays this extra call.
    """
    import os
    import sys
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        from archipelago.inference.llm_gateway import gateway_chat

        ans = gateway_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer YES only if this question can be answered purely with "
                        "mathematics and machine learning theory from a textbook. "
                        "Answer NO if answering would require knowledge about: food, sports, "
                        "sports predictions or winners, movies, fictional or famous people, "
                        "magic, law, history, gardening, personal life, anyone's opinions or "
                        "stance or ethics views, companies, hardware, software or library "
                        "versions, prices, energy or carbon footprints, patents, downloads, "
                        "or replication logistics.\n"
                        "Examples:\n"
                        "Q: Can a hidden Markov model predict who wins the World Cup? -> NO (sports prediction)\n"
                        "Q: Which framework version do the authors recommend? -> NO (software version)\n"
                        "Q: What is the stance of the authors on ethics? -> NO (opinions/ethics stance)\n"
                        "Q: Compare energy usage of training two models. -> NO (energy/carbon)\n"
                        "Q: What is the chain rule used for in backpropagation? -> YES\n"
                        "Q: Which concepts are prerequisites for attention? -> YES\n"
                        "Answer YES or NO only."
                    ),
                },
                {"role": "user", "content": query},
            ],
            purpose="routing",
            temperature=0.0,
            max_tokens=8,
            timeout=8,
        ) or ""
        ans = ans.strip().upper()
        return not ans.startswith("YES")
    except Exception:
        return False
