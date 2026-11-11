"""Stage an attributed Wikibooks Algorithms page for academic graph review."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from archipelago.ingestion.fetch_policy import guarded_fetch

SOURCE_HOST = "en.wikibooks.org"
SOURCE_PATH_PREFIX = "/wiki/Algorithms/"
DEFAULT_SOURCE_URL = "https://en.wikibooks.org/wiki/Algorithms/Introduction"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
DEFAULT_OUTPUT = Path("/tmp/archipelago-wikibooks-algorithms-introduction.md")
MIN_PARAGRAPH_CHARS = 40


def extract_academic_page(body: bytes, url: str) -> str:
    """Keep prose headings and paragraphs with source and license attribution."""
    soup = BeautifulSoup(body, "html.parser")
    article = soup.select_one("#mw-content-text .mw-parser-output")
    if article is None:
        raise ValueError("Wikibooks article body was not found")
    for element in article.select("style, script, table, nav, .mw-editsection, .noprint"):
        element.decompose()
    lines = [
        "# Algorithms — Wikibooks",
        "",
        f"Source: {url}",
        f"License: CC BY-SA 4.0 ({LICENSE_URL})",
        "Authors: Wikibooks contributors; see page history at the source URL.",
        "Adaptation: navigation and non-prose elements removed for academic indexing.",
        "",
    ]
    for element in article.find_all(["h2", "h3", "p"], recursive=True):
        content = element.get_text(" ", strip=True)
        if content.startswith(("Top ,", "Chapters:")):
            continue
        if element.name == "p" and len(content) < MIN_PARAGRAPH_CHARS:
            continue
        if element.name in {"h2", "h3"}:
            lines.extend([f"{'##' if element.name == 'h2' else '###'} {content}", ""])
        elif content:
            lines.extend([content, ""])
    if len(lines) <= 8:
        raise ValueError("Wikibooks article contained no usable prose")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    """Fetch one explicitly scoped page and write a local review artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != SOURCE_HOST
        or not parsed.path.startswith(SOURCE_PATH_PREFIX)
    ):
        parser.error("Only HTTPS Wikibooks Algorithms chapter pages are supported")
    decision, body = guarded_fetch(
        args.url,
        allowed_hosts={SOURCE_HOST},
        actor="academic_source_review",
    )
    if not decision.allowed:
        raise SystemExit(f"Source fetch refused: {decision.reason}: {decision.detail}")
    content = extract_academic_page(body, args.url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Staged {args.output} ({len(content)} characters); review before graph ingestion")


if __name__ == "__main__":
    main()
