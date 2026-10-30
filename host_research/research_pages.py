"""Render the original five-page research UI on the second Vercel project."""

from __future__ import annotations

from html import escape
from pathlib import Path

from flask import Response

UI = Path(__file__).resolve().parent / "ui"
PAGE_DETAILS = {
    "papers": ("Research", "Explore the research graph and ingest papers for a new topic."),
    "progress": ("Ingestion progress", "Follow your local research job and inspect its results."),
    "topics": ("Research atlas", "Explore topics and their verified paper networks."),
    "paper": ("Paper OKF", "Source-backed observations for one research paper."),
    "topic": ("Topic dossier", "Source-backed overview of all saved papers for one topic."),
}
PAGE_SCRIPTS = {
    "papers": ("research_okf_ui.js", "research_home.js"),
    "progress": ("research_progress.js",),
    "topics": ("research_topics.js",),
    "paper": ("research_paper.js",),
    "topic": ("research_topic.js",),
}
ASSET_VERSION = "20261030a"


def render_research_page(page: str) -> Response:
    """Assemble the original research shell, fragment, and page scripts."""
    title, subtitle = PAGE_DETAILS[page]
    shell = (UI / "research_shell.html").read_text(encoding="utf-8")
    fragment = (UI / "research_pages" / f"{page}.html").read_text(encoding="utf-8")
    scripts = (
        [
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.4/cytoscape.min.js" defer></script>'
        ]
        if page == "topics"
        else []
    )
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
    return Response(html, mimetype="text/html")
