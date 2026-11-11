"""Daily, bounded intake of public campus pages and research metadata."""

from __future__ import annotations

from datetime import UTC, datetime
import os
from secrets import compare_digest
from urllib.parse import quote
from xml.etree.ElementTree import ParseError

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue
import requests

from ..context import AppContext
from ..research_access import audit_action
from ..research_campus_sources import discover_campus_pages, discover_serpapi_pages
from ..research_campus_sync import sync_public_campus_pages
from ..research_intake import discover_papers
from ..research_intake_store import save_records

TOPICS = (
    "optical character recognition",
    "distributed database transactions",
    "operating system process scheduling",
    "computer networks congestion control",
    "graph algorithms and complexity",
    "singular value decomposition",
    "branch prediction and computer architecture",
    "software engineering program analysis",
    "cybersecurity intrusion detection",
    "biomedical signal processing",
    "electronic circuit design",
    "mechanical engineering fluid dynamics",
    "supply chain optimization",
)
COLLEGE_PAGES = (
    "https://uem.edu.in/uem-kolkata/syllabus/",
    "https://uem.edu.in/uem-kolkata/phd-department/research/",
    "https://iem.edu.in/syllabus/",
    "https://iem.edu.in/nirf/",
)
TOPICS_PER_RUN = 2


def register(app: Flask, _ctx: AppContext) -> None:
    """Register a secret-protected route invoked by Vercel Cron."""

    @app.get("/api/research/intake/scheduled")  # type: ignore[misc]
    def scheduled_intake() -> ResponseReturnValue:
        secret = os.getenv("CRON_SECRET", "").strip()
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not secret:
            return jsonify({"error": "schedule_unconfigured"}), 503
        if not supplied or not compare_digest(supplied, secret):
            return jsonify({"error": "unauthorized"}), 401
        day = datetime.now(UTC).date().toordinal()
        index = request.args.get("topic_index", type=int)
        if index is not None and not 0 <= index < len(TOPICS):
            return jsonify({"error": "invalid_topic_index"}), 400
        topics = (
            (TOPICS[index],)
            if index is not None
            else tuple(
                TOPICS[(day * TOPICS_PER_RUN + offset) % len(TOPICS)]
                for offset in range(TOPICS_PER_RUN)
            )
        )
        topic_reports: list[dict[str, object]] = []
        report: dict[str, object] = {"topics": topic_reports, "college": "not_attempted"}
        for topic in topics:
            records, providers = discover_papers(topic, None)
            try:
                saved = save_records(records)
            except (requests.RequestException, RuntimeError, ValueError):
                app.logger.exception("Scheduled paper persistence failed")
                saved = 0
            topic_reports.append(
                {
                    "topic": topic,
                    "fetched": len(records),
                    "saved": saved,
                    "providers": providers,
                    "scholar_review_url": f"https://scholar.google.com/scholar?q={quote(topic)}",
                    "ingestion_status": "not_started",
                }
            )
            audit_action(
                user_id=None,
                role="system",
                action="scheduled_paper_intake",
                result="ok" if saved else "unavailable",
                topic=topic,
            )
        if index is None:
            try:
                candidates = discover_campus_pages()
                if not candidates:
                    raise ValueError("Campus sitemaps contain no approved pages")
                report["campus_discovery"] = {"candidates": len(candidates), "source": "sitemaps"}
                complete_sitemap = True
            except (requests.RequestException, RuntimeError, ValueError, ParseError) as exc:
                app.logger.warning("Campus sitemap discovery failed: %s", type(exc).__name__)
                try:
                    candidates = discover_serpapi_pages()
                except (requests.RequestException, ValueError):
                    app.logger.warning("SerpAPI campus discovery unavailable")
                    candidates = []
                source = "SerpAPI" if candidates else "fallback"
                if not candidates:
                    candidates = list(COLLEGE_PAGES)
                report["campus_discovery"] = {"candidates": len(candidates), "source": source}
                complete_sitemap = False
            try:
                report["college"] = sync_public_campus_pages(
                    candidates, complete_sitemap=complete_sitemap
                )
            except (requests.RequestException, RuntimeError, ValueError):
                app.logger.exception("Scheduled college sync failed")
                report["college"] = {"attempted": len(candidates), "saved": 0, "errors": []}
        return jsonify(report)
