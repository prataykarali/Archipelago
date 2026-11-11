"""Resolve short follow-ups from the active chat's user-authored questions."""

from __future__ import annotations

import re

FOLLOW_UP = re.compile(
    r"^(?:now\b|and\b|what about\b|how about\b|which\b|which paper\b|"
    r"what are (?:its|their)\b|(?:its|their|this|that|these|those)\b|"
    r"how (?:does|do|is|are|can)\s+(?:it|they|this|that|these|those)\b|"
    r"(?:can|could) you (?:expand|compare|show|explain)\b|"
    r"show (?:its|the|this|that)\b)",
    re.I,
)
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
MAX_PRIOR_QUESTIONS = 2
MAX_PRIOR_CHARS = 120


def contextual_query(query: str, history: object) -> str:
    """Add bounded previous user questions only for an obvious follow-up."""
    if not FOLLOW_UP.search(query) or not isinstance(history, list):
        return query
    prior: list[str] = []
    for item in reversed(history):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        text = CONTROL_CHARS.sub(" ", str(item.get("content") or "")).strip()
        if text and text.casefold() != query.casefold():
            prior.append(text[:MAX_PRIOR_CHARS])
        if len(prior) >= MAX_PRIOR_QUESTIONS:
            break
    if not prior:
        return query

    # For queries referencing 'it' / 'this' / 'that' directly, substitute referent from recent question
    resolved_q = query
    pronoun_match = re.search(r"^(how (?:does|do|is|are|can))\s+(it|this|that|they)\b", query, re.I)
    if pronoun_match:
        subject = re.sub(
            r"^(?:can\s+you\s+(?:explain|show|tell)|explain|what\s+is|tell\s+me\s+about|how\s+does|how\s+do|define|i\s+want\s+to\s+learn)\s+",
            "",
            prior[0],
            flags=re.I,
        )
        subject = re.sub(r"\s+from\s+(?:that|this|the)\s+source.*$", "", subject, flags=re.I).strip(" ?.,!")
        if subject:
            resolved_q = f"{pronoun_match.group(1)} {subject} " + query[pronoun_match.end() :].lstrip()

    return f"{resolved_q} (Earlier user topics: {'; '.join(reversed(prior))})"
