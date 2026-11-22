"""Evidence-only concept filtering for saved research papers."""

from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any

CONCEPT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "quantization": ("quantized", "quantize", "int4", "int8", "4-bit", "8-bit", "low-bit"),
    "low-memory inference": (
        "low memory",
        "memory-efficient",
        "memory footprint",
        "memory constraint",
        "kv cache",
        "ram",
    ),
    "low memory inference": (
        "low-memory",
        "memory-efficient",
        "memory footprint",
        "memory constraint",
        "kv cache",
        "ram",
    ),
    "pruning": ("pruned", "sparsity", "sparse"),
    "distillation": ("knowledge distillation", "distilled"),
}
DISCUSS_RE = re.compile(
    r"\b(?:which|what)\s+(?:papers?\s+)?(?:discuss|mention|cover|use|evaluate|focus on)\s+(.+?)\??$",
    re.I,
)


def _filter_by_concept(
    concept: str, papers: list[dict[str, Any]], link: Callable[[dict[str, Any]], str]
) -> str:
    clean = re.sub(r"[?.!]+$", "", concept.strip().lower())
    syns = CONCEPT_SYNONYMS.get(clean, ())
    matches: list[str] = []
    for i, p in enumerate(papers, 1):
        fields: list[tuple[str, str]] = [
            ("title", str(p.get("title") or "")),
            ("abstract", str(p.get("abstract") or "")),
            ("topics", ", ".join(str(t) for t in (p.get("topics") or []))),
            (
                "claims",
                " ".join(
                    str(c.get("evidence_text") or "")
                    for c in (p.get("claims") or [])
                    if isinstance(c, dict)
                ),
            ),
        ]
        hit_desc = None
        for loc, text in fields:
            if not text:
                continue
            m = re.search(rf"\b{re.escape(clean)}\b", text, re.I)
            if m:
                start, end = max(0, m.start() - 30), min(len(text), m.end() + 45)
                snippet = " ".join(text[start:end].split())
                hit_desc = f"exact match in {loc}: “{snippet}”"
                break
        if not hit_desc and syns:
            for syn in syns:
                for loc, text in fields:
                    if not text:
                        continue
                    m = re.search(rf"\b{re.escape(syn)}\b", text, re.I)
                    if m:
                        start, end = max(0, m.start() - 30), min(len(text), m.end() + 45)
                        snippet = " ".join(text[start:end].split())
                        hit_desc = f"documented synonym ({syn}) in {loc}: “{snippet}”"
                        break
                if hit_desc:
                    break
        if hit_desc:
            matches.append(f"[{i}] {p['title']} — {link(p)} — {hit_desc}")
    if not matches:
        return (
            f"No papers in this collection contain explicit evidence for “{clean}” "
            "in their title, abstract, provider topics, or extracted claims."
        )
    return (
        f"Papers in this collection with evidence for “{clean}” ({len(matches)}/{len(papers)}):\n"
        + "\n".join(matches)
    )
