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
MIN_RELEVANCE_SCORE = 4
LOGGER = logging.getLogger(__name__)
MAX_TOPIC_ANSWER_ROWS = 200
GENERIC_ACADEMIC_TERMS = frozenset(
    {
        "algorithm",
        "algorithms",
        "analysis",
        "based",
        "compare",
        "concept",
        "concepts",
        "data",
        "deep",
        "explain",
        "function",
        "functions",
        "gradient",
        "layer",
        "layers",
        "learning",
        "machine",
        "method",
        "methods",
        "model",
        "models",
        "network",
        "networks",
        "neural",
        "optimization",
        "overview",
        "paper",
        "papers",
        "research",
        "studies",
        "study",
        "system",
        "systems",
        "training",
    }
)
EXPLICIT_SAVED_QUERY = re.compile(
    r"\b(saved|ingested|collected)\s+(papers?|sources?|studies|publications?)\b", re.I
)
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
    clean_query = re.sub(r"\s*\(Earlier user topics:.*$", "", query)
    if not INVENTORY_TERMS.search(clean_query) or not INVENTORY_REQUEST.search(clean_query):
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


def _core_phrases(terms: list[str]) -> list[str]:
    return [f"{terms[i]} {terms[i + 1]}" for i in range(len(terms) - 1)]


def _score(row: dict, core_terms: set[str], phrases: list[str]) -> int:
    title = str(row.get("title") or "").casefold()
    topic = str(row.get("topic") or "").casefold()
    content = str(row.get("content") or "")[:1200].casefold()
    combined = f"{title} {topic} {content}"
    phrase_hit = any(phrase in combined for phrase in phrases)
    matched_terms = [term for term in core_terms if term in combined]
    if len(core_terms) >= 2 and len(matched_terms) < 2 and not phrase_hit:
        return 0
    if len(core_terms) == 1 and not any(t in title or t in topic for t in matched_terms):
        return 0
    score = sum(
        (3 if term in title else 0) + (2 if term in topic else 0) + (1 if term in content else 0)
        for term in core_terms
    )
    if phrase_hit:
        score += 3
    return score


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
    raw_terms = [t for t in SEARCH_WORD.findall(query.casefold()) if t not in SEARCH_STOPWORDS]
    core_terms = {t for t in raw_terms if t not in GENERIC_ACADEMIC_TERMS}
    if not core_terms:
        return prepared
    phrases = _core_phrases(raw_terms)
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
            if (score := _score(row, core_terms, phrases)) >= MIN_RELEVANCE_SCORE
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
    explicit_saved = bool(EXPLICIT_SAVED_QUERY.search(query)) or updated.get("route") == "RESEARCH_EVIDENCE"
    if out_of_corpus or explicit_saved:
        updated["research_overlay"] = True
    return updated
