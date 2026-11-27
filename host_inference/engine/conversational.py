"""Deterministic conversational intents and honest unsupported-query replies.

One concern: handle greetings, thanks, farewells, help/usage requests,
capability inquiries, and unsupported queries deterministically with zero
external LLM calls, using live graph/corpus coverage instead of hardcoded
domain counts.
"""

from __future__ import annotations

import re
from typing import Any

from .access_profile import is_open_access_profile
from .suggestions import discover_knowledge_areas

MAX_UNSUPPORTED_ALTERNATIVES = 5
MAX_CAPABILITY_AREAS = 8

_GREETING_RE = re.compile(
    r"^(?:hi+|hello+|hey+|howdy|greetings|namaste|yo|sup|what'?s\s+up|"
    r"good\s+(?:morning|afternoon|evening|day))[\s!?.]*$",
    re.I,
)
_THANKS_RE = re.compile(
    r"^(?:thanks?(?:\s+(?:a\s+lot|so\s+much|very\s+much))?|"
    r"thank\s+you(?:\s+(?:so\s+much|very\s+much))?|thx|ty|cheers|appreciate\s+it)[\s!?.]*$",
    re.I,
)
_FAREWELL_RE = re.compile(
    r"^(?:bye+|goodbye|see\s+(?:ya|you)|take\s+care|later)[\s!?.]*$",
    re.I,
)
_HELP_RE = re.compile(
    r"^(?:help(?:\s+me)?|how\s+(?:do\s+i\s+use\s+this|does\s+this\s+work)|"
    r"who\s+are\s+you|what\s+are\s+you|getting\s+started|guide)[\s!?.]*$",
    re.I,
)


def classify_conversational_intent(query: str) -> str | None:
    """Return ``greeting|thanks|farewell|help`` for deterministic social turns, else ``None``."""
    q = (query or "").strip()
    if not q:
        return None
    if _GREETING_RE.match(q):
        return "greeting"
    if _THANKS_RE.match(q):
        return "thanks"
    if _FAREWELL_RE.match(q):
        return "farewell"
    if _HELP_RE.match(q):
        return "help"
    return None


def _numbered_areas_block(graph: Any, *, limit: int | None = None) -> str:
    all_areas = discover_knowledge_areas(graph)
    areas = all_areas if limit is None else all_areas[:limit]
    if not areas:
        return "1) Indexed academic concepts currently loaded in this workspace."
    lines: list[str] = []
    for area in areas:
        samples = ", ".join(area.get("sample_concepts") or [])
        sample_suffix = f" (e.g., {samples})" if samples else ""
        lines.append(
            f"{area['index']}) **{area['label']}** — "
            f"{area['concept_count']} indexed concepts{sample_suffix}"
        )
    return "\n".join(lines)


def build_conversational_reply(graph: Any, intent: str) -> tuple[str, str, dict[str, Any]]:
    """Build a fast deterministic reply with zero external LLM calls."""
    open_only = is_open_access_profile()
    areas_block = _numbered_areas_block(graph, limit=None)
    concept_count = len(getattr(graph, "nodes", None) or {})

    if intent == "thanks":
        text = (
            "You're welcome! Ask anytime if you want to explore another indexed concept, "
            "trace prerequisites, or inspect source passages."
        )
        return "GREETING", text, {"hide_graph": True, "reason": "thanks", "conversational_intent": "thanks"}

    if intent == "farewell":
        text = "Goodbye! Feel free to return whenever you want to explore the indexed corpus or concept graph."
        return "GREETING", text, {"hide_graph": True, "reason": "farewell", "conversational_intent": "farewell"}

    if intent == "help":
        scope_line = (
            "This deployment runs in **open-access mode**, grounding answers in indexed open "
            "textbooks and open-access research papers with page-level provenance."
            if open_only
            else "I ground answers in indexed textbooks, research papers, the concept graph, "
            "and institutional library holdings with page-level provenance."
        )
        text = (
            "I'm **Archipelago**, an evidence-grounded academic knowledge assistant. "
            f"{scope_line}\n\n"
            "**What I can do honestly:**\n"
            f"- Explain any of the `{concept_count}` indexed concepts with source citations.\n"
            "- Show candidate prerequisite, unlocks, and related concept links in the knowledge graph "
            "(unreviewed edges are labeled rather than claimed as verified).\n"
            "- Compare concepts or generate adaptive diagnostic questions.\n\n"
            "**Available knowledge areas in the active index:**\n"
            f"{areas_block}"
        )
        return "GREETING", text, {"hide_graph": True, "reason": "help", "conversational_intent": "help"}

    # Default: greeting
    mode_note = (
        "grounded in open-access textbooks and research papers"
        if open_only
        else "grounded in indexed textbooks, research papers, and institutional library holdings"
    )
    text = (
        f"Hello! I'm **Archipelago**, your academic knowledge assistant ({mode_note}).\n\n"
        "**Available knowledge areas in the active index:**\n"
        f"{areas_block}\n\n"
        "Ask a concept question, request a comparison, or pick a suggested question below."
    )
    return "GREETING", text, {"hide_graph": True, "reason": "greeting", "conversational_intent": "greeting"}


def build_capability_reply(graph: Any) -> str:
    """Build an honest capability overview derived from live graph/corpus inventory."""
    concept_count = len(getattr(graph, "nodes", None) or {})
    open_only = is_open_access_profile()
    areas_block = _numbered_areas_block(graph, limit=MAX_CAPABILITY_AREAS)

    bullets = [
        f"- **Knowledge graph:** `{concept_count}` indexed concepts linked by typed candidate edges "
        "(prerequisite, unlocks, and related — edge review status is reported transparently).",
        "- **Open-access corpus:** Indexed open textbooks and open-access research papers with "
        "passage-level provenance and page links where available.",
        "- **Interactive learning:** Concept topology exploration, prerequisite paths, and "
        "adaptive diagnostic quizzes.",
        "- **Evidence honesty:** When a topic lacks indexed evidence, I report the limitation "
        "rather than fabricating citations or ungrounded claims.",
    ]
    if not open_only:
        bullets.insert(
            2,
            "- **Institutional library catalogue:** Live UEM Kolkata OPAC lookup with authorized "
            "Koha export snapshot fallback and institutional e-book catalogue metadata.",
        )
        bullets.insert(
            3,
            "- **Research Intelligence:** Saved scholarly paper collections, citation networks, "
            "and bibliometric runs for authorized staff.",
        )

    return (
        "Here is what **Archipelago** currently covers:\n\n"
        + "\n".join(bullets)
        + "\n\n**Indexed knowledge areas:**\n"
        + areas_block
    )


def build_unsupported_reply(
    graph: Any,
    query: str,
    *,
    reason: str = "cosine_below_0.75",
) -> str:
    """Explain the evidence limitation honestly and list numbered supported alternatives."""
    clean_q = (query or "").strip().rstrip("?.!")
    if reason == "research_not_indexed":
        intro = (
            f"I do not have sufficient indexed corpus evidence to verify research findings or "
            f"literature gaps for **{clean_q or 'this query'}**. "
            "I will not fabricate citations or claim unverified state-of-the-art results."
        )
    elif reason == "curriculum_not_indexed":
        intro = (
            f"**{clean_q or 'That topic'}** is not currently indexed in the active concept graph, "
            "so I cannot build an evidence-grounded diagnostic or prerequisite roadmap for it."
        )
    elif reason == "both_missing":
        intro = (
            f"I could not match the concepts in **{clean_q or 'this query'}** to indexed nodes "
            "in the active graph, so no relationship or bridge can be verified from corpus evidence."
        )
    else:
        intro = (
            "I do not have indexed corpus evidence to answer this question reliably, "
            "and I will not fabricate sources or ungrounded claims."
        )

    areas = discover_knowledge_areas(graph)
    if not areas:
        return intro

    lines = [intro, "", "**Supported topics available in the active index:**"]
    for area in areas:
        samples = ", ".join(area.get("sample_concepts") or [])
        sample_str = f" — e.g., {samples}" if samples else ""
        lines.append(f"{area['index']}) **{area['label']}**{sample_str}")
    return "\n".join(lines)


__all__ = [
    "build_capability_reply",
    "build_conversational_reply",
    "build_unsupported_reply",
    "classify_conversational_intent",
]
