"""
src/core/prompt_assembly.py — Context Isolation Middleware for Archipelago Local SLM Runtime.

Enforces strict context bounds:
- MAX_CHUNKS = 3 verified raw evidence text passages
- MAX_GRAPH_NODES = 6 concept nodes total (Target + 1-2 hop neighbors)
- Mandatory [S1], [S2] bracketed badge grounding rules
- LaTeX formatting instructions and zero-hallucination constraints
"""

from __future__ import annotations

import logging
from typing import Any
import urllib.parse

logger = logging.getLogger(__name__)

MAX_CHUNKS: int = 3
MAX_GRAPH_NODES: int = 6


class PromptPayloadAssembler:
    """Assembles strictly bounded, isolated context envelopes for local SLMs."""

    def __init__(self, system_instruction: str | None = None) -> None:
        self.system_instruction = system_instruction or (
            "You are Archipelago, an institutional AI/ML library intelligence assistant. "
            "Synthesize pedagogical explanations strictly grounded in the Topological Map "
            "and Verified Evidence Passages. Never hallucinate outside the provided evidence."
        )

    def format_topological_map(
        self,
        anchor_name: str,
        difficulty: str,
        prerequisites: list[dict[str, Any]],
        unlocks: list[dict[str, Any]],
        path: list[str] | None = None,
    ) -> str:
        """Format the deterministic pedagogical topology within the 6-node budget."""
        if path and len(path) >= 2:
            return (
                f"TOPOLOGY BRIDGE (Connecting Entities):\n  {' -> '.join(path[:MAX_GRAPH_NODES])}"
            )

        # Enforce MAX_GRAPH_NODES budget: 1 anchor + up to 3 prereqs + up to 2 unlocks = max 6
        req_names = [p.get("name") or p.get("id") for p in prerequisites[:3] if p]
        unl_names = [u.get("name") or u.get("id") for u in unlocks[:2] if u]

        req_str = " -> ".join(req_names) if req_names else "None (Foundational Entry Point)"
        unl_str = " -> ".join(unl_names) if unl_names else "None (Terminal Frontier)"

        return (
            f"TARGET CONCEPT: {anchor_name} ({difficulty.upper()})\n"
            "TOPOLOGY:\n"
            f"  Prerequisites (Requires): {req_str}\n"
            f"  Applications (Unlocks): {unl_str}"
        )

    def format_evidence_passages(
        self, chunks: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Format raw text chunks into [S1], [S2] badges with exact #page=N coordinates."""
        lines: list[str] = []
        lineage: list[dict[str, Any]] = []

        # Enforce MAX_CHUNKS = 3
        bounded_chunks = chunks[:MAX_CHUNKS]

        for idx, ch in enumerate(bounded_chunks, 1):
            badge = f"S{idx}"
            doc_id = ch.get("doc_id", "Unknown Document")
            doc_title = ch.get("doc_title") or doc_id
            page = ch.get("page_number", 1)
            section = ch.get("section_title", "")
            passage = ch.get("text_passage", "").strip()

            sec_part = f" § {section}" if section else ""
            lines.append(f'[{badge}] {doc_title} (Page {page}{sec_part}):\n"{passage}"')

            quoted_doc = urllib.parse.quote(str(doc_id).lstrip("/"), safe="/")
            lineage.append(
                {
                    "badge": badge,
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "page_number": page,
                    "section_title": section,
                    "deep_link": f"/api/pdf/view?doc={quoted_doc}#page={page}",
                }
            )

        passages_text = "None retrieved from active shelves." if not lines else "\n\n".join(lines)

        return passages_text, lineage

    def assemble_payload(
        self,
        query: str,
        anchor_name: str,
        difficulty: str = "intermediate",
        prerequisites: list[dict[str, Any]] | None = None,
        unlocks: list[dict[str, Any]] | None = None,
        chunks: list[dict[str, Any]] | None = None,
        path: list[str] | None = None,
    ) -> dict[str, Any]:
        """Assemble the complete context payload for local synthesis."""
        prereqs = prerequisites or []
        unl = unlocks or []
        chk = chunks or []

        topo_text = self.format_topological_map(anchor_name, difficulty, prereqs, unl, path=path)
        passages_text, lineage = self.format_evidence_passages(chk)

        context_boundary = (
            "### Context Boundary (Strict Grounding)\n"
            f"{topo_text}\n\n"
            "VERIFIED EVIDENCE PASSAGES:\n"
            f"{passages_text}\n\n"
            "INSTRUCTIONS:\n"
            "1. Base your answer STRICTLY on the evidence above.\n"
            "2. Every factual assertion MUST end with an inline source badge ([S1] or [S2]).\n"
            "3. Formulate equations using LaTeX ($...$ or $$...$$).\n"
            "4. Do not output raw file paths or '/api/page-view' URLs.\n"
            "5. If the evidence is insufficient, state the limitation clearly."
        )

        system_prompt = f"{self.system_instruction}\n\n{context_boundary}"
        user_prompt = f"User Question: {query}\n\nExplain using topological dependencies and cite [S1], [S2] badges."

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "citation_lineage": lineage,
            "topological_summary": topo_text,
            "anchor_concept": anchor_name,
        }
