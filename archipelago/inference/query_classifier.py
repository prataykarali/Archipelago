"""Query mode classification for dynamic routing in Archipelago.

Categorizes queries into:
- MODE_A: Library Quick Query / Atomic Concept (factual lookups, single definition, 0-1 hop)
- MODE_B: Comparative / Relational Query (cross-domain bridges, comparison between 2+ concepts)
- MODE_C: Deep Pedagogical / Curriculum Exploration (multi-hop mastery, learning path from scratch)
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any

from archipelago.inference.routing import parse_multi_topic_query


class QueryMode(str, Enum):
    MODE_A = "mode_a"
    MODE_B = "mode_b"
    MODE_C = "mode_c"


_MODE_C_PATTERNS = [
    re.compile(r"\b(?:i\s+want\s+to\s+learn|want\s+to\s+learn|teach\s+me\s+about|learn\s+about|guide\s+me\s+through|learning\s+path\s+for)\b", re.I),
    re.compile(r"\b(learn|study|master|teach\s+me)\b.+\b(from\s+scratch|from\s+the\s+beginning|step\s+by\s+step|roadmap|curriculum|pathway)\b", re.I),
    re.compile(r"\b(from\s+scratch|from\s+the\s+ground\s+up|from\s+the\s+beginning)\b", re.I),
    re.compile(r"\b(roadmap|learning\s+path|learning\s+pathway|curriculum|study\s+plan)\b", re.I),
    re.compile(r"\bhow\s+(?:do|can)\s+i\s+(?:learn|understand|master|start\s+learning)\b", re.I),
    re.compile(r"\b(prerequisites\s+(?:for|to)|what\s+do\s+i\s+need\s+to\s+know\s+before)\b", re.I),
    re.compile(r"\b(deep\s+dive|comprehensive\s+guide|beginner\s+to\s+advanced|zero\s+to\s+hero)\b", re.I),
    re.compile(r"\bwhere\s+should\s+i\s+start\s+(?:with|to\s+learn)\b", re.I),
]

_MODE_B_COMPARATIVE_PATTERNS = [
    re.compile(r"\b(compare|contrast|difference\s+between|differences\s+between|differ\s+from|versus|\bvs\.?\b)\b", re.I),
    re.compile(r"\bhow\s+does\s+.+\s+(?:differ|connect|relate|compare)\s+(?:to|with|from)\b", re.I),
    re.compile(r"\b(relationship\s+between|connection\s+between|bridge\s+between)\b", re.I),
    re.compile(r"\bwhich\s+is\s+better\b.+\b(?:or|vs)\b", re.I),
    re.compile(r"\bpros\s+and\s+cons\s+of\b", re.I),
]


def classify_query_mode(query: str, routing_result: dict[str, Any] | None = None) -> QueryMode:
    """Classify an incoming query into Mode A, Mode B, or Mode C.

    Args:
        query: Raw or normalized query text.
        routing_result: Optional dict from resolve_query_routing.

    Returns:
        QueryMode (MODE_A, MODE_B, or MODE_C).
    """
    if not query or not query.strip():
        return QueryMode.MODE_A

    q = query.strip()
    ql = q.lower()

    # If already determined to be out-of-scope, small-talk, identity, or library policy, return Mode A
    if routing_result:
        route = routing_result.get("route", "")
        if route in ("out_of_scope", "small_talk", "identity", "onboarding"):
            return QueryMode.MODE_A
        if route.startswith("library_") and route != "library_catalog_stats":
            return QueryMode.MODE_A

    # 1. Check for Mode C (Pedagogical / Mastery / Curriculum) first
    for pattern in _MODE_C_PATTERNS:
        if pattern.search(ql):
            return QueryMode.MODE_C

    # 2. Check for Mode B (Comparative / Relational / Bridge)
    for pattern in _MODE_B_COMPARATIVE_PATTERNS:
        if pattern.search(ql):
            return QueryMode.MODE_B

    # Multi-topic check: if parse_multi_topic_query found multiple distinct topics
    topics = parse_multi_topic_query(q)
    if len(topics) >= 2:
        return QueryMode.MODE_B

    # 3. Default to Mode A (Atomic definition / factual lookup)
    return QueryMode.MODE_A
