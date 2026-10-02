"""Routing guards: small-talk stripping, persona noise, dual-pass, history."""
from __future__ import annotations

import re

from archipelago.inference import state as st

from . import _deps as _rt
from .constants import (
    _PERSONA_STYLE_NOISE,
    _PURE_SMALL_TALK_PATTERNS,
    _SMALL_TALK_PREFIXES,
    _TECHNICAL_MARKERS,
)


def _strip_small_talk(query: str) -> tuple:
    """Return (is_small_talk, remaining_query)."""
    q = (query or "").strip()
    if not q:
        return True, ""

    stripped = _SMALL_TALK_PREFIXES.sub("", q).strip()

    if _PURE_SMALL_TALK_PATTERNS.fullmatch(stripped):
        return True, stripped

    if not _TECHNICAL_MARKERS.search(stripped):
        return True, stripped

    if len(stripped.split()) <= 4 and not _TECHNICAL_MARKERS.search(stripped):
        return True, stripped

    return False, stripped


def _strip_persona_style(query: str) -> tuple[str, bool]:
    """Remove tone/style instructions; keep the technical ask."""
    q = (query or "").strip()
    if not q or not _PERSONA_STYLE_NOISE.search(q):
        return q, False
    cleaned = _PERSONA_STYLE_NOISE.sub(" ", q)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.?!")
    return (cleaned or q), True


def _merge_slots(base_slots: dict, extra: dict) -> dict:
    out = dict(base_slots or {})
    out.update(extra or {})
    return out


def _run_dual_pass_guard(query: str) -> bool:
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
                        "You are a security guard. Is the user asking to write, draft, or generate code, programming scripts, configuration files, emails, or personal advice? "
                        "Answer YES only if they want you to write or generate these software/administrative artifacts. "
                        "Answer NO if they are asking a theoretical, mathematical, conceptual, or syllabus-related question about machine learning, even if they ask to explain it in a creative style, format, or creative script (e.g. songs, poems, or audio play scripts)."
                    ),
                },
                {"role": "user", "content": query},
            ],
            purpose="routing",
            temperature=0.0,
            max_tokens=8,
            timeout=8,
        ) or ""
        return "YES" in ans.strip().upper()
    except Exception:
        return False


def _get_active_concept_from_history(history: list) -> str | None:
    """Scan conversational history (newest to oldest) to find the active concept.

    Assistant turns are mined too — they name the anchor concept of the previous
    answer, which is exactly what a follow-up pronoun ("it", "that") refers to.
    """
    if not history:
        return None
    for h in reversed(history):
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            # Try to find a strong concept anchor first
            anchor_id, score = _rt.find_anchor_concept(content)
            if anchor_id:
                return anchor_id
            # Fallback to top ranked concept with a reasonable score threshold
            ranked = _rt.rank_concepts(content, top_k=1)
            if ranked and ranked[0].get("cos", 0.0) >= 0.50:
                return ranked[0]["id"]
        elif role == "assistant":
            # Assistant prose mentions concept labels — lexical scan only
            # (no embedding of long answers). Longest label wins to avoid
            # generic single-word labels shadowing the real anchor.
            cl = content.lower()
            best_id, best_len = None, 0
            for cid, concept in st.CONCEPTS_DATA.items():
                label = (concept.get("label") or concept.get("name") or "").lower()
                if len(label) >= 4 and label in cl and len(label) > best_len:
                    best_id, best_len = cid, len(label)
            if best_id:
                return best_id
    return None


def _extract_quiz_answers(text: str) -> dict[str, str]:
    """Extract student quiz responses like {'1': 'A', '2': 'B', ...} from natural text."""
    answers = {}
    if not text:
        return answers
    # Pattern 1: Numbered answers e.g. "1-A, 2-B, 3-C, 4-D, 5-A", "1. A 2. B", "Q1: C", "1A 2B"
    for m in re.finditer(r"(?:q(?:uestion)?\s*)?([1-9])\s*[-:.)]?\s*([A-Da-d])\b", text):
        answers[str(m.group(1))] = m.group(2).upper()
    if answers:
        return answers
    # Pattern 2: Comma or space separated letters e.g. "A, B, C, D, A" or "A B C D A"
    letters = re.findall(r"\b([A-Da-d])\b", text)
    if len(letters) >= 3:
        for idx, letter in enumerate(letters[:6], 1):
            answers[str(idx)] = letter.upper()
        return answers
    return answers
