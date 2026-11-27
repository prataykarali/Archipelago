"""Contextual follow-up recommendations derived strictly from retrieved evidence.

One concern: attach up to 5 compact follow-up question strings to technical
chat metadata, built ONLY from resolved concepts in ``graph.nodes``, valid
typed graph relationships (excluding quarantined edges), and retrieved
citations.  Never fabricates concepts and never implies that unreviewed graph
edges are verified.
"""

from __future__ import annotations

import re
from typing import Any

from .corpus_titles import clean_bibliographic_title
from .evidence_selection import domains_compatible, infer_doc_domains, infer_text_domains
from .suggestions import NON_AI_FALLBACK_SUGGESTION_COUNT, sample_fallback_questions

MAX_FOLLOW_UP_QUESTIONS = 5
MAX_QUESTION_CHARS = 96
MAX_TITLE_SNIPPET_CHARS = 44

_BLOCKED_ROUTES = frozenset({"EMPTY", "PERSONA_LOCK", "CODE_TRAP"})
_CONVERSATIONAL_ROUTES = frozenset({"GREETING", "CAPABILITY_INQUIRY"})
_NON_AI_FALLBACK_ROUTES = frozenset(
    {"GREETING", "CAPABILITY_INQUIRY", "GUARDRAIL_INTERCEPT", "OUT_OF_SCOPE", "DISCONNECTED"}
)
_UNSUPPORTED_REASONS = frozenset(
    {
        "cosine_below_0.75",
        "curriculum_not_indexed",
        "research_not_indexed",
        "both_missing",
        "unsupported_intent",
        "no_verified_concept_match",
        "out_of_scope",
    }
)
_NOISE_FOLLOWUP_CIDS = frozenset({"fast", "memory_efficient", "data"})
_INTERDISCIPLINARY_FOLLOWUP_BRIDGES: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"paging", "paged_attention"}),
        frozenset({"paging", "vllm"}),
        frozenset({"virtual_memory", "paged_attention"}),
        frozenset({"priority_queue_mechanics", "heuristic_search"}),
    }
)


def _node_domains(graph: Any, cid: str) -> set[str]:
    if hasattr(graph, "node_domains"):
        return set(graph.node_domains(cid))
    node = (getattr(graph, "nodes", None) or {}).get(cid) or {}
    label = str(node.get("label") or node.get("name") or cid)
    summary = str(node.get("summary") or "")
    return infer_text_domains(f"{cid.replace('_', ' ')} {label} {summary[:300]}")


def _neighbor_is_domain_consistent(graph: Any, anchor_cid: str, neighbor_cid: str) -> bool:
    """Reject noise unigrams and cross-domain lexical-noise neighbors in follow-ups."""
    if neighbor_cid in _NOISE_FOLLOWUP_CIDS:
        return False
    if frozenset({anchor_cid, neighbor_cid}) in _INTERDISCIPLINARY_FOLLOWUP_BRIDGES:
        return True
    anchor_doms = _node_domains(graph, anchor_cid)
    neighbor_doms = _node_domains(graph, neighbor_cid)
    return domains_compatible(anchor_doms, neighbor_doms)


def _citation_is_domain_consistent(
    graph: Any, anchor_cid: str, anchor_label: str, cite: dict[str, Any]
) -> bool:
    """Ensure citation-based follow-ups only reference domain-consistent retrieved sources."""
    if cite.get("withdrawn"):
        return False
    doc_id = str(cite.get("doc_id") or "").strip()
    raw_title = str(cite.get("doc_title") or cite.get("title") or "").strip()
    if not doc_id and not raw_title:
        return False
    anchor_doms = _node_domains(graph, anchor_cid) | infer_text_domains(
        f"{anchor_cid.replace('_', ' ')} {anchor_label}"
    )
    doc_doms = infer_doc_domains(
        doc_id or raw_title,
        str(cite.get("concept_id") or ""),
        f"{raw_title} {str(cite.get('text_passage') or '')[:300]}",
    )
    return domains_compatible(anchor_doms, doc_doms)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _truncate_title(title: str) -> str:
    clean = title.split("(", 1)[0].split("—", 1)[0].strip()
    if len(clean) <= MAX_TITLE_SNIPPET_CHARS:
        return clean
    return clean[: MAX_TITLE_SNIPPET_CHARS - 1].rstrip() + "…"


def _valid_concept_label(graph: Any, node_dict: Any) -> tuple[str, str] | None:
    """Return ``(cid, label)`` only when ``node_dict`` resolves to an indexed graph node."""
    if not isinstance(node_dict, dict):
        return None
    cid = str(node_dict.get("id") or "").strip()
    nodes = getattr(graph, "nodes", None) or {}
    if not cid or cid not in nodes:
        return None
    label = str(nodes[cid].get("label") or nodes[cid].get("name") or cid).strip()
    return (cid, label) if label else None


def build_follow_up_questions(
    graph: Any,
    payload: dict[str, Any],
    query: str,
    route: str,
    *,
    reason: str = "",
) -> list[str]:
    """Return up to 5 grounded follow-up questions for a chat response."""
    if route in _BLOCKED_ROUTES or (route == "GUARDRAIL_INTERCEPT" and reason == "security_abuse_guardrail"):
        return []

    if (
        route in _NON_AI_FALLBACK_ROUTES
        or reason in _UNSUPPORTED_REASONS
        or (route == "GENERAL_EXPLANATION" and not payload.get("anchor_concept"))
    ):
        return sample_fallback_questions(graph, count=NON_AI_FALLBACK_SUGGESTION_COUNT)

    norm_query = _norm(query)
    suggestions: list[str] = []
    seen: set[str] = {norm_query}

    def _push(candidate: str) -> None:
        text = candidate.strip()
        if not text or len(text) > MAX_QUESTION_CHARS:
            return
        key = _norm(text)
        if not key or key in seen or len(suggestions) >= MAX_FOLLOW_UP_QUESTIONS:
            return
        seen.add(key)
        suggestions.append(text)

    anchor_pair = _valid_concept_label(graph, payload.get("anchor_concept"))
    if anchor_pair is not None:
        anchor_cid, anchor_label = anchor_pair
        if anchor_cid in _NOISE_FOLLOWUP_CIDS:
            return sample_fallback_questions(graph, count=NON_AI_FALLBACK_SUGGESTION_COUNT)

        # 1. Prerequisite neighbors (domain-consistent, neutral exploratory phrasing).
        for pre in payload.get("prerequisites") or []:
            pair = _valid_concept_label(graph, pre)
            if (
                pair
                and pair[0] != anchor_cid
                and _neighbor_is_domain_consistent(graph, anchor_cid, pair[0])
            ):
                _push(f"How does {pair[1]} connect to {anchor_label}?")
                break

        # 2. Unlocks / next-topic neighbors (domain-consistent exploratory phrasing).
        for unl in payload.get("unlocks") or []:
            pair = _valid_concept_label(graph, unl)
            if (
                pair
                and pair[0] != anchor_cid
                and _neighbor_is_domain_consistent(graph, anchor_cid, pair[0])
            ):
                _push(f"Explore next concept: {pair[1]}")
                break

        # 3. Related neighbors (domain-consistent comparison phrasing).
        for rel in payload.get("related_concepts") or []:
            pair = _valid_concept_label(graph, rel)
            if (
                pair
                and pair[0] != anchor_cid
                and _neighbor_is_domain_consistent(graph, anchor_cid, pair[0])
            ):
                _push(f"Compare {anchor_label} and {pair[1]}")
                break

        # 4. Evidence-grounded source follow-up (only from domain-consistent, non-withdrawn citations).
        for cite in payload.get("citations") or []:
            if not isinstance(cite, dict) or not _citation_is_domain_consistent(
                graph, anchor_cid, anchor_label, cite
            ):
                continue
            doc_id = str(cite.get("doc_id") or "").strip()
            raw_title = str(cite.get("doc_title") or cite.get("title") or "").strip()
            short_title = _truncate_title(clean_bibliographic_title(doc_id, raw_title))
            if short_title:
                _push(f"What does {short_title} say about {anchor_label}?")
                break

        # 5. Anchor-focused comprehension / example follow-up (respecting user intent).
        if "example" not in norm_query:
            _push(f"Walk through a concrete example of {anchor_label}")
        if "quiz" not in norm_query:
            _push(f"Quiz me on {anchor_label}")

        # Fill remaining slots from additional valid, domain-consistent neighbors if available.
        for group_key, prefix in (
            ("prerequisites", "Review foundational concept: "),
            ("unlocks", "Explain "),
            ("related_concepts", "Explain "),
        ):
            for neighbor in payload.get(group_key) or []:
                pair = _valid_concept_label(graph, neighbor)
                if (
                    pair
                    and pair[0] != anchor_cid
                    and _neighbor_is_domain_consistent(graph, anchor_cid, pair[0])
                ):
                    _push(f"{prefix}{pair[1]}")

    return suggestions[:MAX_FOLLOW_UP_QUESTIONS]


__all__ = ["MAX_FOLLOW_UP_QUESTIONS", "build_follow_up_questions"]
