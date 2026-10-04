"""Auto-split from synthesis.py — do not edit blocks by hand."""
from __future__ import annotations

import re


def _strip_residual_markers(text: str) -> str:
    """Remove internal evidence tokens and citation-shaped model inventions."""
    text = re.sub(r"\[(?:S#|S\d+)\]", "", text or "")
    text = re.sub(r"\[(?:RWC\+\d+|GPT-\d+)\](?::)?", "", text, flags=re.IGNORECASE)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def _looks_like_citation_spam(text: str) -> bool:
    raw = text or ""
    invented = len(re.findall(r"\[(?:S#|RWC\+\d+|GPT-\d+)\]", raw, re.IGNORECASE))
    sentences = [re.sub(r"\s+", " ", s.strip().lower()) for s in re.split(r"(?<=[.!?])\s+", raw)]
    repeated = max((sentences.count(s) for s in set(sentences) if len(s) > 12), default=0)
    return invented >= 2 or repeated >= 3


def _trim_verbose_study_answer(text: str, max_words: int = 160) -> str:
    """Trim at a sentence boundary when generated prose exceeds its word budget."""
    words = re.findall(r"\S+", text or "")
    if len(words) <= max_words:
        return (text or "").strip()
    clipped = " ".join(words[:max_words]).rstrip()
    boundary = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    if boundary >= len(clipped) * 0.55:
        clipped = clipped[: boundary + 1]
    elif clipped and clipped[-1] not in ".!?…":
        clipped += "…"
    return clipped


def _model_answer_is_usable(model: str, query: str, grounded: str) -> bool:
    """Reject noisy or disproportionate rewrites when grounded text is available."""
    if not (model or "").strip():
        return False
    from archipelago.inference.cleanser import cleanse_llm_output

    cleaned = cleanse_llm_output(model)
    if _looks_like_citation_spam(cleaned):
        return False
    model_words, grounded_words = _count_words(cleaned), _count_words(grounded)
    if grounded_words >= 20 and model_words > max(120, grounded_words * 3):
        return False
    return model_words > 0


def _finalize_stream_answer(
    model: str,
    grounded: str,
    first_paint: str,
    evidence_ids=None,
    citation_payloads=None,
    sterile: bool = False,
    offline: bool = False,
    user_query: str = "",
) -> str:
    """Choose a clean grounded first paint or a usable model rewrite."""
    from archipelago.inference.cleanser import cleanse_llm_output

    cleaned_model = _strip_residual_markers(cleanse_llm_output(model))
    from archipelago.inference.citations import cleanse_model_citations

    baseline = grounded or first_paint or ""
    if citation_payloads:
        baseline = cleanse_model_citations(baseline, citation_payloads)
    if not _model_answer_is_usable(cleaned_model, user_query, baseline):
        return baseline
    # A concise grounded response with citations wins over a much longer rewrite.
    if _count_words(baseline) and _count_words(cleaned_model) > max(120, _count_words(baseline) * 3):
        return baseline
    return cleanse_model_citations(cleaned_model, citation_payloads) if citation_payloads else cleaned_model
