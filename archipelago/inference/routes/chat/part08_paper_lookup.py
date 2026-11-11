"""Evidence-only paper lookup for the local chat stream."""

from __future__ import annotations

import json
import re

from flask import Response

from archipelago.inference import state as st
from archipelago.inference.citations import (
    build_citation_payloads,
    build_concept_citation_map,
    render_citation_from_payload,
)


def _paper_match_score(node: dict, paper: dict) -> int:
    """Score a paper title against the requested concept, excluding passing mentions."""
    title = (
        " "
        + re.sub(
            r"[^a-z0-9]+", " ", str(paper.get("title") or paper.get("doc_id") or "").casefold()
        ).strip()
        + " "
    )
    terms = {
        str(node.get("label") or ""),
        str(node.get("name") or ""),
        str(node.get("id") or "").replace("_", " "),
    }
    terms.update(alias for alias in node.get("aliases") or [] if isinstance(alias, str))
    return max(
        (
            len(term)
            for raw in terms
            if (term := re.sub(r"[^a-z0-9]+", " ", raw.casefold()).strip()) and f" {term} " in title
        ),
        default=0,
    )


def handle_paper_lookup(query: str, routing: dict) -> Response:
    """Return indexed paper metadata without a learning graph or quiz."""
    anchor_id = routing.get("anchor_id")
    node = st.CONCEPTS_DATA.get(anchor_id) if anchor_id else None
    evidence = build_concept_citation_map(node, [], []) if node else {}
    citations = build_citation_payloads(node, [], [], evidence) if node else []
    papers = [
        item
        for item in citations
        if node
        and str(item.get("doc_id") or "").lower().startswith("papers/")
        and _paper_match_score(node, item)
    ]
    papers.sort(key=lambda item: _paper_match_score(node, item), reverse=True)
    papers = papers[:1]
    if papers:
        paper = papers[0]
        title = paper.get("title") or paper.get("doc_id")
        answer = f"Closest indexed paper: **{title}** {render_citation_from_payload(paper)}."
        if re.search(r"\b(who wrote|who authored|authors?)\b", query, re.I):
            answer += (
                " The indexed passage does not verify its authors; check the paper's title page."
            )
        if re.search(r"\b(introduced|first)\b", query, re.I):
            answer += " This source alone does not establish which paper introduced the idea first."
    else:
        answer = "I could not verify a matching paper in the indexed evidence."
    if papers:
        answer += "\n\n**Sources:**\n" + "\n".join(
            f"- {render_citation_from_payload(paper)}" for paper in papers
        )

    def generate():
        yield (
            json.dumps(
                {
                    "anchor_concept": None,
                    "subgraph": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "diagnostic_mcqs": [],
                    "related_concepts": [],
                    "citations": papers,
                    "routing": {"route": "paper_lookup", "reason": "indexed_paper_metadata"},
                    "logs": [
                        {
                            "step": "Paper lookup",
                            "status": "Success" if papers else "No evidence",
                            "details": "Indexed paper evidence only.",
                        }
                    ],
                }
            )
            + "\n[STREAM_START]\n"
        )
        yield answer

    return Response(generate(), mimetype="text/plain")
