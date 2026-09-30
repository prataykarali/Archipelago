import re

from archipelago.inference.reply_styles import (
    _MAX_INLINE_CITATIONS_REQUESTED,
    _MIN_INLINE_CITATIONS_REQUESTED,
    REPLY_STYLES,
    select_reply_style,
    style_instruction,
)


def test_reply_style_catalog_has_one_hundred_distinct_safe_styles():
    assert len(REPLY_STYLES) == 100
    assert len(set(REPLY_STYLES)) == 100
    assert all("Sources" not in style and "References" not in style for style in REPLY_STYLES)


def test_reply_style_is_stable_and_preserves_citation_contract():
    assert select_reply_style("What is RAG?") == select_reply_style("What is RAG?")
    prompt = style_instruction("What is RAG?")
    assert "[S#]" in prompt
    assert "Never add a Sources" in prompt or "never add a Sources" in prompt.lower()


def test_style_instruction_asks_for_a_dense_distinct_citation_budget():
    """The prompt states the citation floor, not just a ceiling.

    The previous contract read "at most two inline citations". A 0.5B model
    cites at the floor it is given, so that phrasing was the direct cause of
    replies carrying 2-3 page links regardless of how much evidence the graph
    supplied. The contract now names both ends of the range and demands
    distinct markers. Grounding is unaffected: every emitted marker is still
    resolved against real payloads in citations.cleanse_model_citations, which
    drops any ID that has no evidence or whose paragraph never names the
    concept.
    """
    prompt = style_instruction("What is RAG?")
    assert _MIN_INLINE_CITATIONS_REQUESTED >= 3
    assert _MAX_INLINE_CITATIONS_REQUESTED >= _MIN_INLINE_CITATIONS_REQUESTED
    assert _MAX_INLINE_CITATIONS_REQUESTED <= 8
    assert f"at least {_MIN_INLINE_CITATIONS_REQUESTED}" in prompt
    assert f"at most {_MAX_INLINE_CITATIONS_REQUESTED} inline markers" in prompt
    assert "different [S#]" in prompt
    # No surviving instruction may cap inline citations at one or two.
    assert not re.search(r"at most (?:one|two|1|2)\b", prompt, re.I)


def test_every_style_is_presentation_only_and_never_requests_a_source_dump():
    banned = ("sources", "references", "bibliography", "works cited", "further reading")
    for style in REPLY_STYLES:
        assert not any(term in style.lower() for term in banned)


def test_styles_cover_multiple_structural_patterns():
    blob = " ".join(REPLY_STYLES).lower()
    # Structural variety the product asked for
    assert "---" in blob or "divider" in blob
    assert "bullet" in blob or "dash-led lists" in blob or "•" in blob
    assert "numbered" in blob or "1." in blob or "step" in blob
    assert "----------" in blob or "dashes" in blob
