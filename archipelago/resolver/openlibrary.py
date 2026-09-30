"""Open Library Link Resolver."""
from __future__ import annotations

import logging
from typing import Any
import requests

logger = logging.getLogger("archipelago.resolver.openlibrary")


def resolve_openlibrary(
    isbn: str | None = None,
    title: str | None = None,
    author: str | None = None,
    timeout: int = 6,
) -> dict[str, Any] | None:
    """Resolve a book by ISBN or title/author via Open Library API."""
    if isbn:
        clean_isbn = isbn.replace("-", "").replace(" ", "").strip()
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                key = f"ISBN:{clean_isbn}"
                if key in data:
                    item = data[key]
                    canonical_url = item.get("url") or f"https://openlibrary.org/isbn/{clean_isbn}"
                    return {
                        "working": True,
                        "url": canonical_url,
                        "canonical_url": canonical_url,
                        "title": item.get("title"),
                        "source": "openlibrary",
                    }
        except Exception as exc:
            logger.debug("Open Library ISBN resolution failed: %s", exc)

    if title:
        search_url = "https://openlibrary.org/search.json"
        params = {"title": title}
        if author:
            params["author"] = author
        try:
            resp = requests.get(search_url, params=params, timeout=timeout)
            if resp.status_code == 200:
                docs = resp.json().get("docs", [])
                if docs:
                    key = docs[0].get("key")
                    if key:
                        canonical_url = f"https://openlibrary.org{key}"
                        return {
                            "working": True,
                            "url": canonical_url,
                            "canonical_url": canonical_url,
                            "title": docs[0].get("title"),
                            "source": "openlibrary",
                        }
        except Exception as exc:
            logger.debug("Open Library search resolution failed: %s", exc)

    return None
