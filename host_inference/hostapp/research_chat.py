"""Add source-linked research graph evidence to institutional chat answers."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from .research_intake_store import (
    SEARCH_STOPWORDS,
    SEARCH_WORD,
    list_topic_inventory,
    recent_papers,
    search_records,
)
from .research_library_evidence import library_paper_evidence

ELIGIBLE_ROUTES = frozenset(
    {
        "GRAPH_SYNTHESIS",
        "RELATION",
        "CROSS_DOMAIN",
        "MULTI_CONCEPT",
        "RESEARCH_TOPIC",
        "DEMO",
        "DISCONNECTED",
        "CATALOG_DEPTH",
    }
)
OUT_OF_CORPUS_REASON = "cosine_below_0.75"
MAX_EVIDENCE_SOURCES = 3
MAX_DISCOVERY_SOURCES = 8
RECENT_TOPIC_SCAN = 40
MAX_ABSTRACT_EXCERPT = 260
MIN_RELEVANCE_SCORE = 3
LOGGER = logging.getLogger(__name__)
MAX_TOPIC_ANSWER_ROWS = 200
INVENTORY_TERMS = re.compile(
    r"\b(topics?|subjects?|research areas?|ingested papers?|saved papers?)\b", re.I
)
INVENTORY_REQUEST = re.compile(
    r"\b(all|available|covered|indexed|ingested|list|show|what|which)\b", re.I
)
RESEARCH_SOURCE_REQUEST = re.compile(
    r"\b(research|papers?|publications?|studies|arxiv|doi)\b", re.I
)
DISCOVERY_REQUEST = re.compile(
    r"\b(find|list|show|recommend|which)\b.*\b(papers?|studies|publications?)\b", re.I
)


def _inventory_answer(prepared: dict, query: str) -> dict | None:
    """Answer collection inventory questions from the live topic index."""
    if not INVENTORY_TERMS.search(query) or not INVENTORY_REQUEST.search(query):
        return None
    topics = list_topic_inventory()
    recent = recent_papers(RECENT_TOPIC_SCAN)
    papers = []
    linked_topics: set[str] = set()
    for item in recent:
        topic = str(item.get("topic") or "")
        if topic in linked_topics:
            continue
        papers.append(item)
        linked_topics.add(topic)
        if len(papers) == MAX_EVIDENCE_SOURCES:
            break
    lines = [
        f"The live research collection has {len(topics)} ingested topics and "
        f"{sum(int(item['paper_count']) for item in topics)} topic-to-paper records."
    ]
    lines.extend(
        f"• {item['topic']} ({item['paper_count']} papers)"
        for item in topics[:MAX_TOPIC_ANSWER_ROWS]
    )
    if len(topics) > MAX_TOPIC_ANSWER_ROWS:
        lines.append(
            f"The staff research directory lists the remaining {len(topics) - MAX_TOPIC_ANSWER_ROWS} topics."
        )
    if papers:
        lines.append("Recent original paper links by topic:")
        lines.extend(
            f"• {item['topic']} — {item['title']}: {item['source_url']}" for item in papers
        )
    payload = dict(prepared.get("payload") or {})
    payload.update(
        {
            "route": "RESEARCH_EVIDENCE",
            "contract": "RESEARCH_EVIDENCE",
            "routing": {"route": "RESEARCH_EVIDENCE", "reason": "live_topic_inventory"},
            "render_rule": "source_evidence",
            "research_topics": topics,
        }
    )
    return {
        **prepared,
        "route": "RESEARCH_EVIDENCE",
        "text": "\n".join(lines),
        "payload": payload,
        "research_overlay": True,
    }


def _score(row: dict, terms: set[str]) -> int:
    title = str(row.get("title") or "").casefold()
    topic = str(row.get("topic") or "").casefold()
    content = str(row.get("content") or "")[:1200].casefold()
    return sum(
        (3 if term in title else 0) + (2 if term in topic else 0) + (1 if term in content else 0)
        for term in terms
    )


def enrich_with_research(prepared: dict, query: str) -> dict:
    """Attach evidence from the saved research graph when it genuinely matches."""
    try:
        inventory = _inventory_answer(prepared, query)
        if inventory is not None:
            return inventory
    except (requests.RequestException, RuntimeError, ValueError):
        LOGGER.exception("Research topic inventory unavailable during chat")
    routing = (prepared.get("payload") or {}).get("routing") or {}
    out_of_corpus = (
        prepared.get("route") == "GUARDRAIL_INTERCEPT"
        and routing.get("reason") == OUT_OF_CORPUS_REASON
        and bool(RESEARCH_SOURCE_REQUEST.search(query))
    ) or prepared.get("route") == "RESEARCH_UNVERIFIED"
    source_request = prepared.get("route") == "BOOK_PAGE" and RESEARCH_SOURCE_REQUEST.search(query)
    if prepared.get("route") not in ELIGIBLE_ROUTES and not out_of_corpus and not source_request:
        return prepared
    terms = set(SEARCH_WORD.findall(query.casefold())) - SEARCH_STOPWORDS
    if not terms:
        return prepared
    try:
        rows = search_records(query, kind=None)
    except (requests.RequestException, RuntimeError, ValueError):
        LOGGER.exception("Research graph lookup unavailable during chat")
        return prepared
    limit = MAX_DISCOVERY_SOURCES if DISCOVERY_REQUEST.search(query) else MAX_EVIDENCE_SOURCES
    ranked = sorted(
        (
            (score, row)
            for row in rows
            if (score := _score(row, terms)) >= MIN_RELEVANCE_SCORE
            and str(row.get("content") or "").strip()
        ),
        key=lambda item: item[0],
        reverse=True,
    )[:limit]
    if not ranked:
        return prepared
    payload = dict(prepared.get("payload") or {})
    nodes = []
    edges = []
    sources = []
    lines = ["Saved source evidence (verify the linked paper or college page):"]
    for _score_value, row in ranked:
        url = str(row.get("source_url") or "")
        if urlparse(url).scheme != "https":
            continue
        index = len(sources) + 1
        title = str(row.get("title") or "Untitled source").replace("[", "").replace("]", "")
        title = title.replace("(", "").replace(")", "")
        artifact = library_paper_evidence(row)
        facts = artifact.get("verified_facts") if artifact else None
        if isinstance(facts, list) and facts:
            content = "; ".join(
                f"{fact.get('field')}: {fact.get('value')}"
                for fact in facts
                if isinstance(fact, dict) and fact.get("field") and fact.get("value")
            )[:MAX_ABSTRACT_EXCERPT]
        else:
            content = " ".join(str(row.get("content") or "").split())[:MAX_ABSTRACT_EXCERPT]
        topic = str(row.get("topic") or "Institutional pages")
        paper_id = f"research:{row.get('record_key')}"
        topic_id = f"research-topic:{topic.casefold()}"
        library_link = (
            f" [Library evidence](/api/library/paper-evidence/{row.get('record_key')})"
            if artifact
            else ""
        )
        lines.append(f"[{index}] {title}: {content} Source: {url}{library_link}")
        sources.append(
            {
                "evidence_id": f"P{index}",
                "title": title,
                "url": url,
                "source_type": "research_paper"
                if row.get("kind") == "paper"
                else "scholarly_source",
                "evidence_level": "saved excerpt or metadata; full text not verified here",
                "text_span": content,
                "page_number": None,
            }
        )
        nodes.append({"id": paper_id, "label": title, "kind": row.get("kind"), "source_url": url})
        nodes.append({"id": topic_id, "label": topic, "kind": "topic"})
        edges.append({"from_id": topic_id, "to_id": paper_id, "edge_type": "IN_TOPIC"})
    if not edges:
        return prepared
    payload["research_graph"] = {"nodes": nodes, "edges": edges}
    payload["research_sources"] = sources
    if out_of_corpus:
        payload["citations"] = []
    payload["citations"] = [*payload.get("citations", []), *sources]
    updated = dict(prepared)
    if out_of_corpus:
        updated["route"] = "RESEARCH_EVIDENCE"
        payload["route"] = "RESEARCH_EVIDENCE"
        payload["contract"] = "RESEARCH_EVIDENCE"
        payload["routing"] = {"route": "RESEARCH_EVIDENCE", "reason": "saved_source_match"}
        payload["render_rule"] = "source_evidence"
        updated["text"] = (
            "This topic is supported by the saved research sources below. "
            "The cited excerpts are evidence leads; open the original sources for full context.\n\n"
            + "\n".join(lines)
        )
    else:
        updated["text"] = str(prepared.get("text") or "") + "\n\n" + "\n".join(lines)
    updated["payload"] = payload
    updated["research_overlay"] = True
    return updated
