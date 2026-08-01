"""SoFerence 4-tier synthesis cleaner — strip fluff/leaks; force OKF footer."""

from __future__ import annotations

import re
from typing import Any


_LEAK_PATTERNS = [
    re.compile(r"(?im)^style\s*\d+.*$"),
    re.compile(r"(?im)^layout\s*#.*$"),
    re.compile(r"(?im)^the\s+end\s*$"),
    re.compile(r"(?im)^\[end\].*$"),
    re.compile(r"(?im)^c_id\s*=.*$"),
    re.compile(r"(?im)doc_id\s*[:=].*$"),
    re.compile(r"(?im)chunk_\d+"),
    re.compile(r"(?im)^\s*indexed domains?:.*$"),
    re.compile(r"(?im)^\s*out of (?:scope|the catalog).*$"),
    re.compile(r"(?im)i(?:'m| am) (?:just |only )?(?:an? )?(?:ai|language model).*$"),
    re.compile(r"[─═━]{4,}"),
    re.compile(r"[↗→]\s*$", re.M),
    # Prompt / style control leaks the 0.8B model sometimes echoes
    re.compile(r"(?i)no\s*greetings?"),
    re.compile(r"(?i)no\s*source\s*list"),
    re.compile(r"(?i)no\s*doc[_\s-]?id"),
    re.compile(r"(?i)no\s*chunk\s*ids?"),
    re.compile(r"(?i)no\s*style\s*/?\s*layout\s*tokens?"),
    re.compile(r"(?i)\bLAYOUT\s*tokens?\b"),
    re.compile(r"(?i)\bstyle\s*/\s*LAYOUT\b"),
]

# Glued OKF headers when stream deltas were strip()'d or model skips spaces
_GLUED_OKF_RE = re.compile(
    r"(?i)OKF\s*Graph\s*Traversal\s*Topology|"
    r"OKFGraphTraversalTopology"
)

_GREETING_RE = re.compile(
    r"(?is)^\s*(?:sure[!.,]?\s*|of course[!.,]?\s*|absolutely[!.,]?\s*|"
    r"great question[!.,]?\s*|hello[!.,]?\s*|hi[!.,]?\s*)+"
)

_OKF_HEADER_RE = re.compile(r"(?i)OKF\s+Graph\s+Traversal\s+Topology")
_REQUIRES_RE = re.compile(r"(?i)Requires\s*\(Prerequisites\)\s*:")
_TARGET_RE = re.compile(r"(?i)Target\s+Concept\s*:")
_UNLOCKS_RE = re.compile(r"(?i)Unlocks\s*\(Downstream[^)]*\)\s*:")


# A long alpha run with no space is only possible once spaces were dropped
# (a degraded/corrupted stream). ~40 chars ≈ 5+ average English words.
_GLUE_RUN_MIN = 40


def is_glued(text: str) -> bool:
    """True when the model dropped all spaces (unbroken alpha runs).

    Fully-glued lowercase prose is not recoverable — any algorithmic split is a
    guess. Callers use this to detect a poisoned stream and fall back to the
    grounded card instead of shipping garbage.
    """
    if not text:
        return False
    runs = re.findall(r"[A-Za-z]{4,}", text)
    if not runs:
        return False
    longest = max(len(r) for r in runs)
    return longest >= _GLUE_RUN_MIN


def _fix_missing_spaces(text: str) -> str:
    """Repair CamelCase / digit boundaries left by token strip. Not a de-gluer."""
    t = text or ""
    # Insert space between lower→Upper boundaries: GraphTraversal → Graph Traversal
    t = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)
    # digit/letter boundaries
    t = re.sub(r"(?<=[a-zA-Z])(?=\d)", " ", t)
    t = re.sub(r"(?<=\d)(?=[A-Z])", " ", t)
    # Common glued OKF phrases
    t = re.sub(r"(?i)OKFGraph", "OKF Graph", t)
    t = re.sub(r"(?i)TargetConcept", "Target Concept", t)
    t = re.sub(r"(?i)DownstreamApplications", "Downstream Applications", t)
    # Qwen3.5:0.8b tokenization artifacts — common acronyms split across tokens
    t = re.sub(r"\bLo\s+RA\b", "LoRA", t)
    t = re.sub(r"\bQLo\s+RA\b", "QLoRA", t)
    t = re.sub(r"\bAI\s+ML\b", "AI/ML", t)
    t = re.sub(r"\bGP\s+U\b", "GPU", t)
    t = re.sub(r"\bCP\s+U\b", "CPU", t)
    t = re.sub(r"\bLL\s+M\b", "LLM", t)
    t = re.sub(r"\bRL\s+HF\b", "RLHF", t)
    t = re.sub(r"\bS\s+FT\b", "SFT", t)
    t = re.sub(r"\bD\s+PO\b", "DPO", t)
    t = re.sub(r"\bR\s+AG\b", "RAG", t)
    t = re.sub(r"\bB\s+ERT\b", "BERT", t)
    t = re.sub(r"\bG\s+PT\b", "GPT", t)
    # Math expression fixes
    t = re.sub(r"\bW\s+W\b", "W", t)
    t = re.sub(r"\bB\s+😎\b", "B", t)
    t = re.sub(r"😎", "", t)
    t = re.sub(r"\bn\s+n\b", "n", t)
    t = re.sub(r"\bk\s+n\b", "k < n", t)
    t = re.sub(r"\bA\s+i\b", "A_i", t)
    t = re.sub(r"\bW\s+i\b", "W_i", t)
    t = re.sub(r"\bpartial\s+E\s*/\s*partial\s+W\b", r"partial E / partial W", t)
    # Fix LaTeX-like: $W$ -> $W$, \$W\$ -> $W$
    t = re.sub(r"\$\s*([A-Za-z])\s*\$", r"$\1$", t)
    t = re.sub(r"\\\$\s*([A-Za-z])\s*\\\$", r"$\1$", t)
    # Fix common split tokens
    t = re.sub(r"\bmatrix\s+decomposition\b", "matrix decomposition", t)
    t = re.sub(r"\blow\s+rank\b", "low-rank", t)
    t = re.sub(r"\bfine\s+tuning\b", "fine-tuning", t)
    t = re.sub(r"\bpre\s+trained\b", "pre-trained", t)
    # Fix LoRA variants
    t = re.sub(r"\bLo\s+RAs\b", "LoRAs", t)
    t = re.sub(r"\bLo\s+RA\b", "LoRA", t)
    # General: single letter + space + single letter + space + single letter → merge (3+ capitals = acronym)
    t = re.sub(r"\b([A-Z])\s+([A-Z])\s+([A-Z])\b", r"\1\2\3", t)
    # Don't merge 2 single capitals (e.g., "W B" are separate math vars, not an acronym)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def _clean_body(text: str) -> str:
    t = (text or "").strip()
    t = _fix_missing_spaces(t)
    t = _GREETING_RE.sub("", t).strip()
    # Drop inline prompt-leak fragments anywhere in a line
    for pat in (
        re.compile(r"(?i)\s*No\s*greetings?,?"),
        re.compile(r"(?i)\s*no\s*source\s*list,?"),
        re.compile(r"(?i)\s*no\s*doc[_\s-]?id/?chunk\s*ids?,?"),
        re.compile(r"(?i)\s*no\s*Style/?LAYOUT\s*tokens\.?"),
    ):
        t = pat.sub("", t)
    # Strip model-generated Sources section (we append our own verified one)
    t = re.sub(r"(?is)\n\*\*Sources\*\*.*?(\n\n|\Z)", "\n", t)
    t = re.sub(r"(?is)\nSources:?.*?(\n\n|\Z)", "\n", t)
    t = re.sub(r"(?is)\nSources\s*\n.*?(?=\n\n|\Z)", "\n", t)
    lines: list[str] = []
    for line in t.splitlines():
        drop = False
        for pat in _LEAK_PATTERNS:
            if pat.search(line):
                drop = True
                break
        # Drop pure glued control lines with no spaces and OKF spam
        compact = re.sub(r"\s+", "", line)
        if (
            len(compact) > 40
            and " " not in line.strip()
            and any(
                k in compact.lower() for k in ("okfgraph", "nogreet", "sourcelist", "layouttoken")
            )
        ):
            drop = True
        if not drop:
            lines.append(line)
    t = "\n".join(lines)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def _name_chain(items: list[dict[str, Any]] | None, limit: int = 4) -> str:
    names: list[str] = []
    for item in items or []:
        n = (item.get("name") or item.get("label") or item.get("id") or "").strip()
        if n and n not in names:
            names.append(n)
        if len(names) >= limit:
            break
    return " → ".join(names) if names else "(none listed)"


def build_okf_footer(
    anchor_name: str,
    prerequisites: list[dict[str, Any]] | None = None,
    unlocks: list[dict[str, Any]] | None = None,
    concept: dict[str, Any] | None = None,
) -> str:
    """Deterministic OKF card from graph topology."""
    # Extract all available OKF fields from concept
    fields = []
    if concept:
        # Add all non-empty fields from concept
        for key, label in [
            ("citations", "Citations"),
            ("authors", "Authors"),
            ("publisher", "Publisher"),
            ("year", "Year"),
            ("subject", "Subject"),
            ("doi", "DOI"),
            ("isbn", "ISBN"),
        ]:
            val = concept.get(key)
            if val:
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                fields.append(f"**{label}**: {val}")

    parts = ["**OKF Graph Traversal Topology**"]
    parts.append(f"**Requires (Prerequisites)**: {_name_chain(prerequisites)}")
    parts.append(f"**Target Concept**: {anchor_name or '(unknown)'}")
    parts.append(f"**Unlocks (Downstream Applications)**: {_name_chain(unlocks)}")

    if fields:
        parts.append("")  # blank line before extra fields
        parts.extend(fields)

    return "\n".join(parts)


def append_source_list(citations: list[dict[str, Any]] | None) -> str:
    """Verified source list Python appends (model must not invent). Deduplicates by doc_id."""
    if not citations:
        return ""
    lines = ["", "**Sources**"]
    seen_docs = set()
    for c in citations:
        doc_id = c.get("doc_id", "")
        if doc_id in seen_docs:
            continue
        seen_docs.add(doc_id)
        eid = c.get("evidence_id") or "S?"
        # Use prettify_doc_title for better source names
        from archipelago.inference.synthesis import prettify_doc_title

        title = (
            prettify_doc_title(doc_id)
            if doc_id
            else (c.get("title") or c.get("doc_title") or "Source")
        )
        page = c.get("page_number") or 1
        lines.append(f"[{eid}] {title}, p.{page}")
    return "\n".join(lines)
def enforce_four_tier(
    text: str,
    *,
    anchor_name: str = "",
    prerequisites: list[dict[str, Any]] | None = None,
    unlocks: list[dict[str, Any]] | None = None,
    citations: list[dict[str, Any]] | None = None,
    concept: dict[str, Any] | None = None,
    curriculum_paths: list[dict[str, Any]] | None = None,
) -> str:
    """Strip leaks/fluff; ensure OKF footer + optional source list exist."""
    body = _clean_body(text)
    if not body:
        body = (
            f"{anchor_name or 'This concept'} is indexed in the library knowledge graph. "
            "See the topological map and source chunks for grounded detail."
        )

    # If model already has OKF block (spaced or glued), keep body before it.
    m = _OKF_HEADER_RE.search(body) or _GLUED_OKF_RE.search(body)
    if m:
        body = body[: m.start()].rstrip()
    elif _REQUIRES_RE.search(body) and _TARGET_RE.search(body):
        m2 = _REQUIRES_RE.search(body)
        if m2:
            body = body[: m2.start()].rstrip()
    # Body that is only control/glued junk → replace with grounded stub
    body_compact = re.sub(r"\s+", "", body or "")
    if body and (
        len(body.split()) < 4
        and any(k in body_compact.lower() for k in ("nogreet", "okfgraph", "layouttoken"))
    ):
        body = (
            f"{anchor_name or 'This concept'} is indexed in the library knowledge graph. "
            "See the topological map and source pages below."
        )
    footer = build_okf_footer(anchor_name, prerequisites, unlocks, concept)
    sources = append_source_list(citations)
    parts = [body, "", footer]
    if curriculum_paths:
        parts.append("")
        parts.append("**Curriculum Paths:**")
        for path in curriculum_paths[:3]:
            md = path.get("markdown") or ""
            if md:
                parts.append(md)
    if sources:
        parts.append(sources)
    return "\n".join(parts).strip() + "\n"
