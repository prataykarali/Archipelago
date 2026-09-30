"""Grounded fallback cards + false-OOS / garble detection.

Restored to the unit-test contract (test_grounded_fallback.py,
test_production_citation_hygiene.py) and the QA harness.
"""
from __future__ import annotations

import re
from typing import Any


GROUNDED_PREAMBLE: str = "Based on the retrieved knowledge graph evidence:"

# Template section headers the SLM sometimes echoes back (e.g. "### 1. Direct
# Technical Opening", "### 4. OKF Graph Traversal Topology Card").
_TEMPLATE_HEADER_RE = re.compile(
    r"^\s*#{1,4}\s*\d*\.?\s*[A-Z][^\n]*$",
    re.MULTILINE,
)
# Style/pagination artifacts: "Style 12:", "LAYOUT #3/100", "[END]" — may
# appear mid-line glued to prose.
_STYLE_LABEL_RE = re.compile(
    r"(?:\s|^)(?:(?:style\s+\d+\s*:\s*)?layout\s*#\d+(?:/\d+)?|style\s+\d+\s*:|\[end\])(?=\s|$)",
    re.IGNORECASE,
)
# Pedagogical label normalisation the cleaner guarantees.
_REQUIRES_LABEL_RE = re.compile(r"Requires\s+Prerequisites\s*:", re.IGNORECASE)
# Garble fingerprints: fused words from dropped letters ("modelsine" for
# "model + line", "tndition" for "to condition", "canine" for "combine").
_GARBLED_FUSIONS_RE = re.compile(
    r"\b(?:\w+?)(?:modelsine|frultiple|byparing|tndition|canine|unity|"
    r"opsine|nsine|ksine|ssine)\b",
    re.IGNORECASE,
)
# Control characters / zero-width noise.
_CONTROL_RE = re.compile(r"[\u00ad\u200b\u200c\u200d\ufeff\ufffd]")


def build_grounded_answer(
    query: str,
    context: str,
    payloads: list[dict[str, Any]],
) -> str:
    """Build a grounded answer from context and citation payloads."""
    return f"{GROUNDED_PREAMBLE}\n\n{context}"


def _name_chain(items: list[dict[str, Any]] | None, limit: int = 4) -> str:
    names: list[str] = []
    for item in items or []:
        n = str(item.get("name") or item.get("label") or item.get("id") or "").strip()
        if n and n not in names:
            names.append(n)
        if len(names) >= limit:
            break
    return " → ".join(names) if names else "(none listed)"


def _cite_chunk(chunk: dict[str, Any], index: int) -> str:
    doc_id = str(chunk.get("doc_id") or chunk.get("doc") or "").strip()
    page = int(chunk.get("page_number") or chunk.get("page") or 1) or 1
    passage = str(chunk.get("text_passage") or chunk.get("text") or "").strip()
    label = f"[S{index}]"
    cite = f"{label} {doc_id}, p.{page}" if doc_id else f"{label} source chunk"
    return f"{cite}\n{passage}" if passage else cite


def build_benchmark_grounded_answer(
    query: str,
    anchor_id: str = "",
    anchor_name: str = "",
    anchor_summary: str = "",
    prerequisites: list[dict[str, Any]] | None = None,
    unlocks: list[dict[str, Any]] | None = None,
    chunks: list[dict[str, Any]] | None = None,
    payloads: list[dict[str, Any]] | None = None,
    **_: Any,
) -> str:
    """Deterministic benchmark card: topology + [S#] cited evidence.

    Legacy signature ``(query, payloads)`` and the richer keyword contract
    (anchor_name / prerequisites / unlocks / chunks) are both supported.
    """
    if not chunks and payloads:
        # Legacy two-arg form: payload list of {topic, text, doc_id, page_number}.
        parts = [GROUNDED_PREAMBLE]
        for i, p in enumerate(payloads, start=1):
            topic = p.get("topic", "")
            text = p.get("text", "")
            parts.append(f"[S{i}] {topic}: {text}")
        return "\n".join(parts)

    if not chunks and not payloads:
        return f"{GROUNDED_PREAMBLE}\n\nNo sources found for: {query}"

    name = anchor_name or anchor_id or "this concept"
    parts = [
        f"**{name}**" + (f" — {anchor_summary}" if anchor_summary else ""),
        "",
        "**OKF Graph Traversal Topology**",
        f"**Requires (Prerequisites)**: {_name_chain(prerequisites)}",
        f"**Target Concept**: {anchor_name or anchor_id or '(unknown)'}",
        f"**Unlocks (Downstream Applications)**: {_name_chain(unlocks)}",
        "",
        "**Cited Resources**",
    ]
    for i, chunk in enumerate(chunks or [], start=1):
        parts.append(_cite_chunk(chunk, i))
    return "\n".join(parts)


def clean_weird_symbols(text: str) -> str:
    """Strip control chars, style labels, and template section headers.

    Normalises fused garble ("LoRA\ufb01ne-tuning" → readable), removes
    template headers ("### 1. Direct Technical Opening"), and normalises the
    pedagogy labels the UI expects ("Requires Prerequisites:" →
    "Requires (Prerequisites):"). Returns clean text safe for the chat UI.
    """
    t = text or ""
    t = _CONTROL_RE.sub("", t)
    t = t.replace("\ufb01", "fi").replace("\ufb02", "fl")
    t = _STYLE_LABEL_RE.sub(" ", t)
    t = _TEMPLATE_HEADER_RE.sub("", t)
    t = _REQUIRES_LABEL_RE.sub("Requires (Prerequisites):", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    # Re-join header removals: ": \n" leftovers collapse to clean breaks.
    t = re.sub(r"\n\s*:\s*\n", "\n\n", t)
    return t.strip()


def is_false_out_of_scope_refusal(text: str) -> bool:
    """Detect a model refusal that is wrong because the topic IS indexed.

    True when the text carries an out-of-scope / not-indexed refusal banner
    while the same text lists concrete pilot-domain evidence that the scope
    gate should have accepted (Vector RAG, GraphRAG, ...).
    """
    t = (text or "").lower()
    if not t:
        return False
    refusal = (
        "outside the current scope" in t
        or "out of scope" in t
        or "not detailed in the" in t
        or "outside what this library covers" in t
    )
    if not refusal:
        return False
    # Any concrete graph-domain listing means the refusal is provably false:
    # those topics ARE the indexed corpus.
    indexed_domains = ("vector rag", "graphrag", "graph rag", "dense embeddings")
    if any(d in t for d in indexed_domains):
        return True
    # A refusal with no polite wrapper ("sorry", "afraid") is also a template
    # leak rather than a genuine refusal.
    polite = ("sorry", "afraid", "unfortunately", "i'm afraid")
    return not any(p in t for p in polite)


def looks_garbled_or_template_leaky(text: str) -> bool:
    """Flag SLM output with fused/dropped-letter garble or template leaks."""
    t = text or ""
    if "{" in t or "}" in t:
        return True
    if "[S" in t and "]" not in t:
        return True
    if _GARBLED_FUSIONS_RE.search(t):
        return True
    # Dropped-letter pattern: "byparing", "tndition" — a vowel-followed-by-
    # consonant cluster that shouldn't occur in normal English tokens.
    if re.search(r"\b\w*(?:by|tn|fr|ss)[a-z]{0,2}par(?:e|ed|ing)|\bmodelsine\b", t, re.I):
        return True
    return False


def true_out_of_scope_message() -> str:
    """Return the true out-of-scope refusal message."""
    from archipelago.inference.scope_gate import OUT_OF_SCOPE_MESSAGE

    return OUT_OF_SCOPE_MESSAGE
