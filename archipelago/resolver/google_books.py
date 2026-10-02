"""Google Books Link Resolver."""
from __future__ import annotations

import logging
from typing import Any
import requests

from archipelago.resolver.openlibrary import _is_plausible_isbn, _title_matches

logger = logging.getLogger("archipelago.resolver.google_books")

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
_SEARCH_LIMIT = 10


def resolve_google_books(
    isbn: str | None = None,
    title: str | None = None,
    author: str | None = None,
    timeout: int = 6,
) -> dict[str, Any] | None:
    """Resolve a book by ISBN or title/author via Google Books API."""
    query_parts = []
    is_isbn_query = False
    if _is_plausible_isbn(isbn):
        clean_isbn = isbn.replace("-", "").replace(" ", "").strip()
        query_parts.append(f"isbn:{clean_isbn}")
        is_isbn_query = True
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
            params={"q": query_str, "maxResults": _SEARCH_LIMIT},
            timeout=timeout,
        )
        if resp.status_code == 200:
            for item in resp.json().get("items", []):
                info = item.get("volumeInfo", {})
                result_title = info.get("title")
                canonical_url = info.get("infoLink") or info.get("previewLink")
                if not canonical_url:
                    continue
                # A title search must actually match the queried title; an ISBN
                # query is an exact identifier lookup and needs no title check.
                if not is_isbn_query and not _title_matches(title, result_title):
                    continue
                return {
                    "working": True,
                    "url": canonical_url,
                    "canonical_url": canonical_url,
                    "title": result_title,
                    "authors": info.get("authors", []),
                    "publisher": info.get("publisher"),
                    "source": "google_books",
                    "verified": True,
                }
    except Exception as exc:
        logger.debug("Google Books API query failed: %s", exc)

    return None
