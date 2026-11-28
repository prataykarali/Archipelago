"""Deterministic conversational intents, honest abstentions, and domain-verified topic browser.

One concern: handle greetings, thanks, farewells, help/usage requests,
capability inquiries, and unsupported/fallback queries deterministically with
zero external LLM calls. Delegates 12-domain word-boundary classification to
``engine.suggestions.discover_domain_coverage`` so Operating Systems never lists
AI/ML concepts (e.g., Chain-of-Thought or RNNs), and separates full-text,
graph-only, and unavailable domains.
"""

from __future__ import annotations

import re
from typing import Any

from .access_profile import is_open_access_profile
from .suggestions import discover_domain_coverage

MAX_UNSUPPORTED_ALTERNATIVES = 5
MAX_CAPABILITY_AREAS = 12
MAX_ECHO_TOPIC_CHARS = 72
MIN_GENERAL_EXPLANATION_CHARS = 40

_PRIOR_CONTEXT_RE = re.compile(
    r"\s*(?:\((?:earlier\s+user\s+topics?|prior\s+context)\s*:[^)]*\)|"
    r"\[(?:earlier\s+user\s+topics?|prior\s+context)\s*:[^\]]*\])\s*",
    re.I,
)

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


def strip_prior_context(query: str) -> str:
    """Remove appended multi-turn context markers so prior turns never leak into answers."""
    return _PRIOR_CONTEXT_RE.sub(" ", query or "").strip()


def classify_conversational_intent(query: str) -> str | None:
    """Return ``greeting|thanks|farewell|help`` for deterministic social turns, else ``None``."""
    q = strip_prior_context(query)
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
    coverage = discover_domain_coverage(graph)
    supported = coverage["full_text"]
    graph_only = coverage["graph_only"]
    unavailable = coverage["unavailable"]

    primary = supported if supported else graph_only
    if not primary:
        return "1) Indexed academic concepts currently loaded in this workspace."

    visible = primary if limit is None else primary[:limit]
    lines: list[str] = []
    for idx, area in enumerate(visible, start=1):
        samples = ", ".join(area.get("sample_concepts") or [])
        sample_suffix = f" (e.g., {samples})" if samples else ""
        tier_note = "full-text PDFs + graph" if area["doc_count"] > 0 else "graph concepts only"
        lines.append(
            f"{idx}) **{area['label']}** — "
            f"{area['concept_count']} indexed concepts ({tier_note}){sample_suffix}"
        )

    if supported and graph_only:
        labels = ", ".join(a["label"] for a in graph_only)
        lines.append(f"\n**Graph-only domains (no verified full-text PDFs yet):** {labels}")
    if unavailable:
        labels = ", ".join(a["label"] for a in unavailable)
        lines.append(f"\n**Unavailable domains (not yet in the active corpus):** {labels}")
    return "\n".join(lines)


def _short_topic_phrase(query: str) -> str:
    clean = strip_prior_context(query).rstrip("?.!").strip()
    if not clean or len(clean) > MAX_ECHO_TOPIC_CHARS:
        return ""
    return clean


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
        return (
            "GREETING",
            text,
            {"hide_graph": True, "reason": "thanks", "conversational_intent": "thanks"},
        )

    if intent == "farewell":
        text = (
            "Goodbye! Feel free to return whenever you want to explore the indexed corpus "
            "or concept graph."
        )
        return (
            "GREETING",
            text,
            {"hide_graph": True, "reason": "farewell", "conversational_intent": "farewell"},
        )

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
        return (
            "GREETING",
            text,
            {"hide_graph": True, "reason": "help", "conversational_intent": "help"},
        )

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
    return (
        "GREETING",
        text,
        {"hide_graph": True, "reason": "greeting", "conversational_intent": "greeting"},
    )


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
        "- **Evidence honesty:** When a topic lacks indexed evidence, I abstain honestly "
        "rather than fabricating citations, graph paths, or ungrounded claims.",
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
    """Emit a clear abstention (never mislabeled as a general explanation) with domain coverage."""
    topic = _short_topic_phrase(query)
    topic_ref = f"**{topic}**" if topic else "this question"

    if reason == "research_not_indexed":
        intro = (
            f"I cannot answer this from the available corpus: there is insufficient indexed "
            f"corpus evidence to verify research findings or literature gaps for {topic_ref}. "
            "I will not fabricate citations or claim unverified state-of-the-art results."
        )
    elif reason == "curriculum_not_indexed":
        intro = (
            f"I cannot answer this from the available corpus: {topic_ref} is not currently "
            "indexed in the active concept graph, so I cannot build an evidence-grounded "
            "diagnostic or prerequisite roadmap for it."
        )
    elif reason == "both_missing":
        intro = (
            f"I cannot answer this from the available corpus: the concepts in {topic_ref} "
            "do not match indexed nodes in the active graph, so no relationship or bridge "
            "can be verified from indexed corpus evidence."
        )
    else:
        intro = (
            "I cannot answer this question from the available indexed corpus evidence, "
            "and I will not fabricate sources, graph paths, or ungrounded claims."
        )

    coverage = discover_domain_coverage(graph)
    supported = coverage["full_text"]
    graph_only = coverage["graph_only"]
    unavailable = coverage["unavailable"]

    primary = supported if supported else graph_only
    if not primary:
        return intro

    heading = (
        "**Supported full-text domains in the active corpus:**"
        if supported
        else "**Indexed concept areas:**"
    )
    lines = [intro, "", heading]
    for idx, area in enumerate(primary, start=1):
        samples = ", ".join(area.get("sample_concepts") or [])
        sample_str = f" — e.g., {samples}" if samples else ""
        lines.append(f"{idx}) **{area['label']}**{sample_str}")

    if supported and graph_only:
        lines.extend(
            [
                "",
                "**Graph-only domains (concept nodes only, no verified full-text PDFs):** "
                + ", ".join(a["label"] for a in graph_only),
            ]
        )
    if unavailable:
        lines.extend(
            [
                "",
                "**Unavailable domains (not yet covered in the active corpus):** "
                + ", ".join(a["label"] for a in unavailable),
            ]
        )
    return "\n".join(lines)


def build_unindexed_academic_fallback(
    graph: Any,
    query: str,
    *,
    allow_general_explanation: bool = False,
    general_explanation_text: str = "",
) -> tuple[str, str, dict[str, Any]]:
    """Distinguish an explicitly labeled general explanation from an honest corpus abstention.

    Never echoes the user's question and claims to offer a general explanation
    without actually providing one, never leaks prior turn context, and never
    manufactures a graph path, evidence badge, or academic source.
    """
    clean_q = strip_prior_context(query)
    body = (general_explanation_text or "").strip()
    is_substantive_explanation = (
        allow_general_explanation
        and len(body) >= MIN_GENERAL_EXPLANATION_CHARS
        and body.lower().strip(" ?.") != clean_q.lower().strip(" ?.")
    )
    if is_substantive_explanation:
        text = f"**General explanation (not grounded in the indexed corpus):**\n\n{body}"
        return (
            "GENERAL_EXPLANATION",
            text,
            {
                "hide_graph": True,
                "evidence_backed": False,
                "fallback_mode": "general_explanation",
                "reason": "academic_general_not_indexed",
            },
        )

    abstention_text = build_unsupported_reply(graph, clean_q, reason="corpus_coverage_gap")
    return (
        "GUARDRAIL_INTERCEPT",
        abstention_text,
        {
            "hide_graph": True,
            "evidence_backed": False,
            "fallback_mode": "abstention",
            "reason": "corpus_coverage_gap",
        },
    )


__all__ = [
    "build_capability_reply",
    "build_conversational_reply",
    "build_unindexed_academic_fallback",
    "build_unsupported_reply",
    "classify_conversational_intent",
    "discover_domain_coverage",
    "strip_prior_context",
]
