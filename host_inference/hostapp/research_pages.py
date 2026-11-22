"""Render each staff research area as its own full page."""

from __future__ import annotations

from html import escape

from flask import Response

from .config import UI

PAGE_DETAILS = {
    "papers": ("Research", "Explore the research graph and ingest papers for a new topic."),
    "progress": ("Ingestion progress", "Follow your local research job and inspect its results."),
    "topics": ("Recent topics", "Open recent saved searches and their papers."),
    "paper": ("Paper OKF", "Source-backed observations for one research paper."),
    "topic": ("Topic dossier", "Source-backed overview of all saved papers for one topic."),
}
PAGE_SCRIPTS = {
    "papers": ("research_download.js", "research_intelligence.js"),
    "progress": ("research_progress.js",),
    "topics": ("research_topics.js",),
    "paper": ("research_run_dossier.js", "research_paper.js"),
    "topic": ("research_download.js", "research_run_dossier.js", "research_topic.js"),
}
SHELL = UI / "research_shell.html"
FRAGMENTS = UI / "research_pages"
ASSET_VERSION = "20261122stages4"


def render_research_page(page: str) -> Response:
    """Assemble one of the two focused research pages with its script."""
    title, subtitle = PAGE_DETAILS[page]
    shell = SHELL.read_text(encoding="utf-8")
    fragment = (FRAGMENTS / f"{page}.html").read_text(encoding="utf-8")
    scripts: list[str] = []
    scripts.extend(
        f'<script src="/{name}?v={ASSET_VERSION}" defer></script>' for name in PAGE_SCRIPTS[page]
    )
    html = (
        shell.replace("__TITLE__", escape(title))
        .replace("__SUBTITLE__", escape(subtitle))
        .replace("__PAGE__", page)
        .replace("__SCRIPTS__", "\n  ".join(scripts))
        .replace("__CONTENT__", fragment)
    )
    response = Response(html, mimetype="text/html")
    if page in {"papers", "topic"}:
        response.cache_control.no_store = True
    return response
