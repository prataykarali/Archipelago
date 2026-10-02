"""Compound-query parser: split multi-topic asks into topic phrases."""
from __future__ import annotations

import re


def parse_multi_topic_query(query: str) -> list[str]:
    """Parse a compound query into multiple topic phrases or return single topic.

    Handles '+', 'vs', 'versus', 'differ from', commas, and 'and' conjunctions,
    while treating subordinate explanatory clauses (e.g. 'and how it reduces...')
    as a single unified topic.
    """
    if not query or not query.strip():
        return []

    q = query.strip()
    # Strip common leading question / imperative phrasing
    prefix_match = re.match(
        r"^(?:explain|compare|describe|analyze|discuss|what\s+(?:is|are)|how\s+does|how\s+do)\s+",
        q,
        re.I,
    )
    cleaned = q[prefix_match.end():] if prefix_match else q
    cleaned = cleaned.rstrip("?.! ")

    # Check for dependent explanatory clauses with 'and' (e.g. 'and how', 'and why', 'and what', 'and its')
    # If the conjunction is explanatory, do not split on 'and'
    if re.search(r"\band\s+(?:how|why|what|where|when|which|who|its|their|the\s+way)\b", cleaned, re.I):
        if not re.search(r"\+|\bvs\.?\b|\bversus\b", cleaned, re.I):
            return [cleaned]

    # Delimiters: '+', 'vs', 'versus', 'differ from', or ',' / 'and'
    if "+" in cleaned:
        parts = [p.strip() for p in cleaned.split("+") if p.strip()]
        return parts

    vs_match = re.split(r"\s+(?:vs\.?|versus|differ(?:s)?\s+from)\s+", cleaned, flags=re.I)
    if len(vs_match) > 1:
        return [p.strip() for p in vs_match if p.strip()]

    # Otherwise split on commas and conjunction 'and'
    split_parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", cleaned, flags=re.I)
    parts = [p.strip() for p in split_parts if p.strip()]
    if parts:
        return parts[:4]
    return [cleaned]
