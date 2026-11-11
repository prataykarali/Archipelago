"""Staff research discovery and institutional page intake routes."""

from __future__ import annotations

import logging
import re

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue
import requests

from ..context import AppContext
from ..research_access import audit_action
from ..research_intake import TARGET_PAPERS, discover_papers, fetch_college_page
from ..research_intake_store import (
    SEARCH_STOPWORDS,
    count_records,
    get_record,
    list_records,
    list_topic_inventory,
    recent_papers,
    save_records,
    search_records,
)
from ..research_okf import build_paper_okf
from ..research_topic_overview import build_topic_overview

MAX_TOPIC_CHARS = 160
MAX_URL_CHARS = 1000
MAX_REPLY_QUERY_CHARS = 300
REPLY_SOURCE_LIMIT = 5
REPLY_EXCERPT_CHARS = 420
REPLY_ANSWER_EXCERPT_CHARS = 220
REPLY_ANSWER_SOURCE_LIMIT = 3
QUERY_WORD = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
MANAGER_ROLES = frozenset({"librarian", "administrator"})
LOGGER = logging.getLogger(__name__)


def _relevant_excerpt(content: str, terms: set[str]) -> str:
    """Select a short supporting sentence from a saved abstract."""
    sentences = SENTENCE_BOUNDARY.split(content.strip())
    sentence = max(sentences, key=lambda part: sum(term in part.casefold() for term in terms))
    return sentence[:REPLY_EXCERPT_CHARS]


def register(app: Flask, ctx: AppContext) -> None:
    """Register read, scholarly discovery and college intake endpoints."""

    @app.get("/api/research/intake/metrics")  # type: ignore[misc]
    def intake_metrics() -> ResponseReturnValue:
        """Expose counts only so the public library page can show real progress."""
        try:
            counts = count_records()
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research aggregate count failed")
            return jsonify({"error": "storage_unavailable"}), 503
        return jsonify({"papers": counts["paper"], "college_pages": counts["institutional_page"]})

    @app.get("/api/research/intake/activity")  # type: ignore[misc]
    def intake_activity() -> ResponseReturnValue:
        """Expose current scholarly titles and topics on the library details page."""
        try:
            topics = list_topic_inventory()
            papers = recent_papers(8)
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research activity read failed")
            return jsonify({"error": "storage_unavailable"}), 503
        return jsonify({"topics": topics, "papers": papers})

    @app.get("/api/research/intake/topics")  # type: ignore[misc]
    def intake_topics() -> ResponseReturnValue:
        """Expose the complete active topic directory to authenticated staff."""
        try:
            topics = list_topic_inventory()
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research topic index failed")
            return jsonify({"error": "storage_unavailable"}), 503
        return jsonify({"topics": topics, "count": len(topics)})

    @app.get("/api/research/intake/records")  # type: ignore[misc]
    def intake_records() -> ResponseReturnValue:
        kind = (request.args.get("kind") or "").strip()
        topic = (request.args.get("topic") or "").strip()
        if kind and kind not in {"paper", "institutional_page"}:
            return jsonify({"error": "invalid_kind"}), 400
        if len(topic) > 200:
            return jsonify({"error": "invalid_topic"}), 400
        try:
            rows = list_records(kind or None, topic) if topic else list_records(kind or None)
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research record read failed")
            return jsonify({"error": "storage_unavailable"}), 503
        return jsonify({"records": rows, "count": len(rows)})

    @app.post("/api/research/intake/reply")  # type: ignore[misc]
    def intake_reply() -> ResponseReturnValue:
        payload = request.get_json(silent=True)
        query = str(payload.get("query") or "").strip() if isinstance(payload, dict) else ""
        if len(query) < 3 or len(query) > MAX_REPLY_QUERY_CHARS:
            return jsonify({"error": "invalid_query"}), 400
        try:
            rows = search_records(query, kind=None)
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research reply source read failed")
            return jsonify({"error": "storage_unavailable"}), 503
        terms = set(QUERY_WORD.findall(query.casefold())) - SEARCH_STOPWORDS
        scored = []
        for row in rows:
            title = str(row.get("title") or "")
            topic = str(row.get("topic") or "")
            content = str(row.get("content") or "")
            if not content:
                continue
            title_text = title.casefold()
            topic_text = topic.casefold()
            content_text = content[:1000].casefold()
            score = sum(
                (3 if term in title_text else 0)
                + (2 if term in topic_text else 0)
                + (1 if term in content_text else 0)
                for term in terms
            )
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        sources = [
            {
                "title": row["title"],
                "url": row["source_url"],
                "provider": row["source_name"],
                "excerpt": _relevant_excerpt(str(row["content"]), terms),
            }
            for _, row in scored[:REPLY_SOURCE_LIMIT]
        ]
        if not sources:
            return jsonify(
                {
                    "answer": "No saved source directly supports this query yet. Fetch papers or campus pages first.",
                    "sources": [],
                }
            )
        passages = " ".join(
            f"[{number}] {source['excerpt'][:REPLY_ANSWER_EXCERPT_CHARS]}"
            for number, source in enumerate(sources[:REPLY_ANSWER_SOURCE_LIMIT], start=1)
        )
        answer = f"Relevant passages from saved sources: {passages}"
        return jsonify({"answer": answer, "sources": sources, "answer_kind": "extractive"})

    @app.get("/api/research/intake/paper-okf/<record_key>")  # type: ignore[misc]
    def intake_paper_okf(record_key: str) -> ResponseReturnValue:
        """Return the complete evidence-aware OKF object for a saved paper."""
        if not re.fullmatch(r"[a-f0-9]{64}", record_key):
            return jsonify({"error": "invalid_record_key"}), 400
        try:
            paper = get_record(record_key)
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research OKF read failed")
            return jsonify({"error": "storage_unavailable"}), 503
        if paper is None or paper.get("kind") != "paper":
            return jsonify({"error": "not_found"}), 404
        return jsonify(build_paper_okf(paper))

    @app.get("/api/research/intake/topic-overview")  # type: ignore[misc]
    def intake_topic_overview() -> ResponseReturnValue:
        """Return only active local-pipeline papers and observed topic facts."""
        topic = (request.args.get("topic") or "").strip()
        if len(topic) < 3 or len(topic) > MAX_TOPIC_CHARS:
            return jsonify({"error": "invalid_topic"}), 400
        try:
            rows = list_records("paper", topic)
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research topic overview read failed")
            return jsonify({"error": "storage_unavailable"}), 503
        return jsonify(build_topic_overview(topic, rows))

    @app.post("/api/research/discover")  # type: ignore[misc]
    def research_discover() -> ResponseReturnValue:
        """Preview scholarly source links without persisting or starting GPU work."""
        payload = request.get_json(silent=True)
        topic = str(payload.get("topic") or "").strip() if isinstance(payload, dict) else ""
        if len(topic) < 3 or len(topic) > MAX_TOPIC_CHARS:
            return jsonify({"error": "invalid_topic"}), 400
        principal = vars(request)["archipelago_principal"]
        records, sources = discover_papers(topic, str(principal["id"]))
        return jsonify(
            {
                "topic": topic,
                "papers": [
                    {
                        "title": row["title"],
                        "source_url": row["source_url"],
                        "source_name": row["source_name"],
                        "abstract": str(row.get("content") or "")[:500],
                    }
                    for row in records[:30]
                ],
                "sources": sources,
            }
        )

    @app.post("/api/research/intake/papers")  # type: ignore[misc]
    def intake_papers() -> ResponseReturnValue:
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            return jsonify({"error": "bearer_required"}), 401
        payload = request.get_json(silent=True)
        topic = str(payload.get("topic") or "").strip() if isinstance(payload, dict) else ""
        if len(topic) < 3 or len(topic) > MAX_TOPIC_CHARS:
            return jsonify({"error": "invalid_topic"}), 400
        principal = vars(request)["archipelago_principal"]
        records, sources = discover_papers(topic, str(principal["id"]))
        if not records:
            return jsonify({"error": "sources_unavailable", "sources": sources}), 503
        try:
            saved = save_records(records)
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research paper persistence failed")
            return jsonify({"error": "storage_unavailable", "sources": sources}), 503
        audit_action(
            user_id=str(principal["id"]),
            role=str(principal["role"]),
            action="paper_intake",
            result="ok",
            topic=topic,
        )
        return jsonify(
            {
                "topic": topic,
                "target": TARGET_PAPERS,
                "fetched": len(records),
                "saved": saved,
                "sources": sources,
                "provider_counts": {
                    provider: sum(1 for record in records if record["source_name"] == provider)
                    for provider in {str(record["source_name"]) for record in records}
                },
                "records": records,
                "okf_records": [build_paper_okf(record, topic) for record in records],
            }
        ), 200

    @app.post("/api/research/intake/college")  # type: ignore[misc]
    def intake_college() -> ResponseReturnValue:
        principal = vars(request)["archipelago_principal"]
        if principal.get("role") not in MANAGER_ROLES:
            return jsonify({"error": "forbidden"}), 403
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            return jsonify({"error": "bearer_required"}), 401
        payload = request.get_json(silent=True)
        url = str(payload.get("url") or "").strip() if isinstance(payload, dict) else ""
        if not url or len(url) > MAX_URL_CHARS:
            return jsonify({"error": "invalid_url"}), 400
        try:
            record = fetch_college_page(url, str(principal["id"]))
        except ValueError as exc:
            return jsonify({"error": "invalid_source", "detail": str(exc)}), 400
        except requests.RequestException as exc:
            LOGGER.warning("Institutional source fetch failed: %s", type(exc).__name__)
            return jsonify(
                {"error": "source_unavailable", "detail": "The college page could not be fetched."}
            ), 502
        try:
            save_records([record])
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Institutional page persistence failed")
            return jsonify({"error": "storage_unavailable"}), 503
        audit_action(
            user_id=str(principal["id"]),
            role=str(principal["role"]),
            action="college_intake",
            result="ok",
        )
        return jsonify({"saved": 1, "record": record}), 200
