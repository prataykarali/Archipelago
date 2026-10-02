"""Open Library Link Resolver."""
from __future__ import annotations

import logging
import re
from typing import Any
import requests

logger = logging.getLogger("archipelago.resolver.openlibrary")

# A search result is only accepted when it genuinely resembles the query, so a
# nonsense title can never resolve to an unrelated book (docs/01 §5: never
# fabricate a book, author, or URL).
MIN_TITLE_MATCH = 0.6
_MIN_TOKEN_LEN = 3
_SEARCH_LIMIT = 10


def _normalize_title(value: str | None) -> str:
    """Lowercase alphanumeric form for title comparison."""
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _title_tokens(value: str | None) -> set[str]:
    """Content tokens (length >= 3) used to compare a query against a result."""
    return {t for t in _normalize_title(value).split() if len(t) >= _MIN_TOKEN_LEN}


def _title_matches(query: str | None, candidate: str | None) -> bool:
    """True when the candidate title plausibly *is* the queried title.

    Compared on a coverage basis so a longer catalog title that contains every
    queried word still matches, while an unrelated book does not.
    """
    query_tokens = _title_tokens(query)
    if not query_tokens:
        # No usable query tokens: only an ISBN lookup is trustworthy.
        return False
    candidate_tokens = _title_tokens(candidate)
    if not candidate_tokens:
        return False
    coverage = len(query_tokens & candidate_tokens) / len(query_tokens)
    return coverage >= MIN_TITLE_MATCH


def _is_plausible_isbn(isbn: str | None) -> bool:
    """Reject placeholder/structurally invalid ISBNs.

    A fabricated identifier such as ``000-0-000000-00-0`` must never be treated
    as an exact lookup, otherwise a bogus identifier can surface an unrelated
    catalogue record.
    """
    if not isbn:
        return False
    digits = re.sub(r"[^0-9Xx]", "", str(isbn)).upper()
    if len(digits) not in (10, 13):
        return False
    if len(set(digits)) <= 1:
        return False  # all zeros / all same digit
    return True


def resolve_openlibrary(
    isbn: str | None = None,
    title: str | None = None,
    author: str | None = None,
    timeout: int = 6,
) -> dict[str, Any] | None:
    """Resolve a book by ISBN or title/author via Open Library API."""
    if _is_plausible_isbn(isbn):
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
                        "verified": True,
                    }
        except Exception as exc:
            logger.debug("Open Library ISBN resolution failed: %s", exc)

    if title:
        search_url = "https://openlibrary.org/search.json"
        params = {"title": title, "limit": _SEARCH_LIMIT}
        if author:
            params["author"] = author
        try:
            resp = requests.get(search_url, params=params, timeout=timeout)
            if resp.status_code == 200:
                docs = resp.json().get("docs", [])
                # Walk the ranked results and take the first genuine title match.
                for doc in docs:
                    doc_title = doc.get("title")
                    key = doc.get("key")
                    if not key or not doc_title:
                        continue
                    if not _title_matches(title, doc_title):
                        continue
                    canonical_url = f"https://openlibrary.org{key}"
                    return {
                        "working": True,
                        "url": canonical_url,
                        "canonical_url": canonical_url,
                        "title": doc_title,
                        "source": "openlibrary",
                        "verified": True,
                    }
                logger.debug(
                    "Open Library search returned %d result(s), none matching %r",
                    len(docs), title,
                )
        except Exception as exc:
            logger.debug("Open Library search resolution failed: %s", exc)

    return None
