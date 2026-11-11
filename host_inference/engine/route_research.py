"""Dated research-topic reply over indexed bibliographic metadata."""

from __future__ import annotations

import re
from typing import Any

from . import compose
from .intent import IntentCategory


def research_topic_reply(
    engine: Any, query: str, anchors: list[str], best_id: str, best_score: float, hits: list[str]
) -> tuple[str, str, str | None, dict[str, Any]] | None:
    """Return indexed studies with their verified example years, when requested."""
    graph = engine.graph
    RESEARCH_TOPIC_RE = re.compile(
        r"\b(recent\s+(?:studies|research|papers|advances)|latest\s+(?:findings|literature|works)|state of the art|sota)\b",
        re.I,
    )
    if RESEARCH_TOPIC_RE.search(query):
        target = anchors[0] if anchors else best_id
        ids = [target]
        if target == "rag" and "graph_rag" in compose.VERIFIED_BIBLIOGRAPHIC_RECORDS:
            ids.append("graph_rag")
        records = [
            (cid, compose.VERIFIED_BIBLIOGRAPHIC_RECORDS[cid])
            for cid in ids
            if cid in compose.VERIFIED_BIBLIOGRAPHIC_RECORDS
        ]
        citations = []
        synthesis_text = compose.synthesis(engine, target) if target in graph.nodes else ""
        if records:
            lines = []
            dated_years = []
            for cid, rec in records:
                citation = (
                    graph.cite_record(cid, rec["title"], len(citations) + 1)
                    if cid in graph.nodes
                    else None
                )
                if not citation or citation.get("doc_id") != rec["doc_id"]:
                    continue
                citations.append(citation)
                dated_years.append(rec["year"])
                lines.append(
                    f"- {rec['authors']} ({rec['year']}), *{rec['title']}*, {rec['venue']}. {citation['label']}"
                )
            synthesis_text += "\n\n**Dated papers in the available index:**\n" + "\n".join(lines)
            if dated_years:
                years = sorted(set(dated_years))
                synthesis_text += f"\n\nCorpus date coverage for these examples: {', '.join(years)}. The index does not establish which studies are latest; live scholarly retrieval is needed to verify more recent work."
            else:
                synthesis_text += "\n\nCorpus date coverage could not be verified against indexed papers for this topic."
        else:
            synthesis_text += "\n\nCorpus date coverage is unavailable for this topic in the index. I cannot identify the latest studies from this record."

        return (
            "RESEARCH_TOPIC",
            synthesis_text,
            target,
            {
                "score": max(best_score, 0.93 if hits else best_score),
                "reason": "research_topic_verified_dates",
                "citations": citations,
                "intent_category": IntentCategory.RESEARCH_TOPIC.value,
            },
        )

    return None
