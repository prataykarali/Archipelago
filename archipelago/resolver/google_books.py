"""Google Books Link Resolver."""
from __future__ import annotations

import logging
from typing import Any
import requests

logger = logging.getLogger("archipelago.resolver.google_books")

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


def resolve_google_books(
    isbn: str | None = None,
    title: str | None = None,
    author: str | None = None,
    timeout: int = 6,
) -> dict[str, Any] | None:
    """Resolve a book by ISBN or title/author via Google Books API."""
    query_parts = []
    if isbn:
        clean_isbn = isbn.replace("-", "").replace(" ", "").strip()
        query_parts.append(f"isbn:{clean_isbn}")
    elif title:
        q_title = title.replace(" ", "+")
        query_parts.append(f"intitle:{q_title}")
        if author:
            q_author = author.replace(" ", "+")
            query_parts.append(f"inauthor:{q_author}")

    if not query_parts:
        return None

    query_str = "+".join(query_parts)
    try:
        resp = requests.get(
            GOOGLE_BOOKS_API,
            params={"q": query_str, "maxResults": 1},
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if items:
                info = items[0].get("volumeInfo", {})
                canonical_url = info.get("infoLink") or info.get("previewLink")
                if canonical_url:
                    return {
                        "working": True,
                        "url": canonical_url,
                        "canonical_url": canonical_url,
                        "title": info.get("title"),
                        "authors": info.get("authors", []),
                        "publisher": info.get("publisher"),
                        "source": "google_books",
                    }
    except Exception as exc:
        logger.debug("Google Books API query failed: %s", exc)

    return None
