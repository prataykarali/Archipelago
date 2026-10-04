"""Pearson eLibrary Link Resolver - Pure Metadata & External URL Generation Engine."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger("archipelago.resolver.pearson")

PEARSON_PORTAL_BASE = "https://elibrary.in.pearson.com"
PEARSON_READER_BASE = "https://ebooks.elibrary.in.pearson.com/wr/index.html"
PEARSON_READER_VERSION = "1.0.317.1"

_PEARSON_CATALOG_CACHE: list[dict[str, Any]] | None = None


def _reader_url(book_id: str, subscription_id: str, book_type: str = "pdf") -> str:
    """Build a Pearson reader URL with one valid query string and book fragment."""
    viewer = "index.html" if book_type.lower() == "reflowable" else "pdfviewer.html"
    return (
        f"https://ebooks.elibrary.in.pearson.com/wr/{viewer}"
        f"?version={PEARSON_READER_VERSION}&subscriptionId={subscription_id}#book/{book_id}"
    )


def _load_pearson_catalog() -> list[dict[str, Any]]:
    global _PEARSON_CATALOG_CACHE
    if _PEARSON_CATALOG_CACHE is not None:
        return _PEARSON_CATALOG_CACHE
    repo_root = Path(__file__).resolve().parents[2]
    cat_file = repo_root / "data" / "catalogs" / "pearson_bookshelf.json"
    if cat_file.is_file():
        try:
            with cat_file.open(encoding="utf-8") as f:
                _PEARSON_CATALOG_CACHE = json.load(f).get("books", [])
                return _PEARSON_CATALOG_CACHE
        except Exception as exc:
            logger.debug("Failed to load pearson_bookshelf.json: %s", exc)
    _PEARSON_CATALOG_CACHE = []
    return _PEARSON_CATALOG_CACHE


def _normalize_key(s: str | None) -> str:
    """Normalize string to lowercase alphanumeric characters, stripping common prefixes."""
    if not s:
        return ""
    clean = s.lower().replace("doc_", "").replace("pearson_", "").replace("book_", "").replace(".pdf", "")
    return re.sub(r"[^a-z0-9]", "", clean)


def _fuzzy_match_book(catalog: list[dict[str, Any]], query_id: str | None, query_title: str | None, query_isbn: str | None) -> dict[str, Any] | None:
    """Find matching Pearson book using exact, normalized, or fuzzy criteria."""
    if not query_id and not query_title and not query_isbn:
        return None

    # 1. Exact ID, ISBN, slug or alias match
    for q in (query_id, query_title, query_isbn):
        if not q:
            continue
        q_str = str(q).strip()
        q_low = q_str.lower()
        for book in catalog:
            b_id = str(book.get("id", "")).strip()
            b_isbn = str(book.get("isbn", "")).strip()
            b_slug = str(book.get("slug", "") or "").strip().lower()
            b_aliases = [str(a).strip().lower() for a in (book.get("aliases") or [])]
            if (b_id and q_str == b_id) or (b_isbn and q_str == b_isbn):
                return book
            if b_slug and q_low == b_slug:
                return book
            if q_low in b_aliases:
                return book

    # 2. Normalized alphanumeric match against title, slug, and id
    for q in (query_id, query_title, query_isbn):
        if not q:
            continue
        nq = _normalize_key(str(q))
        if not nq:
            continue
        for book in catalog:
            nb_title = _normalize_key(book.get("title", ""))
            nb_slug = _normalize_key(book.get("slug", ""))
            nb_id = _normalize_key(book.get("id", ""))
            nb_author = _normalize_key(book.get("author", ""))
            if nq in (nb_title, nb_slug, nb_id):
                return book
            # Check aliases
            for alias in book.get("aliases") or []:
                if nq == _normalize_key(alias):
                    return book

    # 3. Substring matching on normalized strings (length >= 5)
    for q in (query_id, query_title):
        if not q:
            continue
        nq = _normalize_key(str(q))
        if len(nq) < 5:
            continue
        for book in catalog:
            nb_title = _normalize_key(book.get("title", ""))
            nb_slug = _normalize_key(book.get("slug", ""))
            if nq in nb_title or nb_title in nq:
                return book
            if nb_slug and (nq in nb_slug or nb_slug in nq):
                return book

    # 4. Partial character overlay matching (for UUID typos like 13ddfc73-f7ee-4ab8-8cf3-e5c4a8cfdbf)
    if query_id and len(query_id) > 10:
        clean_q = query_id.replace("-", "").lower()
        for book in catalog:
            b_id = book.get("id", "").replace("-", "").lower()
            matching_chars = sum(1 for a, b in zip(clean_q, b_id) if a == b)
            if matching_chars / max(len(clean_q), len(b_id)) > 0.75:
                return book

    return None


def _with_reader_version(url: str) -> str:
    """Ensure a catalog reader URL carries the pinned reader version.

    Catalog entries may store a bare viewer URL. Without the version query the
    reader can fall back to an older viewer, so the pinned version is added here
    rather than relying on the browser to patch it.
    """
    if not url or "version=" in url:
        return url
    if "?" in url:
        return url.replace("?", f"?version={PEARSON_READER_VERSION}&", 1)
    return url.replace(".html", f".html?version={PEARSON_READER_VERSION}", 1)


def resolve_pearson_url(
    book_id: str | None = None,
    subscription_id: str | None = None,
    isbn: str | None = None,
    title: str | None = None,
    existing_url: str | None = None,
    use_playwright: bool = False,
    timeout: int = 6,
) -> dict[str, Any]:
    """Resolve catalog metadata only; legacy ``working`` means URL availability, not access.

    No network probe occurs here. ``verified``, ``access_verified`` and
    ``page_verified`` remain false, even when a URL can be constructed.
    """
    
    # 1. Direct URL check
    if existing_url and urlsplit(existing_url).scheme == "https" and urlsplit(existing_url).hostname in {"elibrary.in.pearson.com", "ebooks.elibrary.in.pearson.com"} and not urlsplit(existing_url).username:
        return {
            "working": True,
            "url": existing_url,
            "canonical_url": existing_url,
            "source": "pearson",
            "verified": False,
            "url_available": True,
            "access_verified": False,
            "page_verified": False,
            "navigation": "manual_page",
            "note": "Book URL available; open the book and select the cited page manually. Access has not been verified.",
            "status": "unverified",
            "last_verified": None,
            "target_blank": True,
        }

    catalog = _load_pearson_catalog()
    matched_book = _fuzzy_match_book(catalog, book_id, title, isbn)

    if matched_book:
        b_id = matched_book.get("id")
        b_isbn = matched_book.get("isbn")
        b_title = matched_book.get("title")
        sub_id = matched_book.get("subscription_id") or subscription_id or "debf3e10-c27c-469a-a2aa-8a30c919db91"
        r_url = matched_book.get("reader_base_url")
        book_type = matched_book.get("book_type", "pdf")

        if r_url:
            target_url = _with_reader_version(r_url)
        else:
            target_url = _reader_url(str(b_id), str(sub_id), str(book_type))

        return {
            "working": True,
            "url": target_url,
            "canonical_url": target_url,
            "reader_url": target_url,
            "source": "pearson",
            "verified": False,
            "url_available": True,
            "access_verified": False,
            "page_verified": False,
            "navigation": "manual_page",
            "note": "Book URL available; open the book and select the cited page manually. Access has not been verified.",
            "book_id": b_id,
            "subscription_id": sub_id,
            "isbn": b_isbn,
            "title": b_title,
            "status": "unverified",
            "last_verified": None,
            "target_blank": True,
        }

    # 2. If book_id and subscription_id are explicitly passed
    if book_id and subscription_id:
        canonical_url = _reader_url(book_id, subscription_id)
        return {
            "working": True,
            "url": canonical_url,
            "canonical_url": canonical_url,
            "reader_url": canonical_url,
            "source": "pearson",
            "verified": False,
            "url_available": True,
            "access_verified": False,
            "page_verified": False,
            "navigation": "manual_page",
            "note": "Book URL available; open the book and select the cited page manually. Access has not been verified.",
            "book_id": book_id,
            "status": "unverified",
            "last_verified": None,
            "target_blank": True,
        }

    # 3. Fallback to Pearson eLibrary main portal (not found)
    canonical_url = f"{PEARSON_PORTAL_BASE}/"
    return {
        "working": False,
        "url": canonical_url,
        "canonical_url": canonical_url,
        "source": "pearson",
        "verified": False,
        "status": "not_found",
        "target_blank": True,
        "error": f"Book not found in Pearson catalog: {title or book_id or isbn or 'unknown'}",
        "error_code": "PEARSON_NOT_FOUND",
        "note": "Institutional login required at Pearson eLibrary portal.",
    }


def build_reader_url(book_or_uuid: dict[str, Any] | str, page: int = 1) -> str:
    """Build a Pearson eLibrary reader URL for a specific book and page.

    Preserves the exact reader viewer (index.html for reflowable, pdfviewer.html for pdf)
    and specific subscriptionId defined in the catalog.

    Args:
        book_or_uuid: A matched book dict, book UUID, slug, doc_id, or title.
        page: The page number to navigate to (default: 1).

    Returns:
        Full Pearson reader URL with #book/{uuid}/page/{page} fragment.
    """
    import re
    matched_book = None
    if isinstance(book_or_uuid, dict):
        matched_book = book_or_uuid
    else:
        catalog = _load_pearson_catalog()
        matched_book = _fuzzy_match_book(catalog, str(book_or_uuid), str(book_or_uuid), None)

    if matched_book and matched_book.get("reader_base_url"):
        base_url = _with_reader_version(matched_book["reader_base_url"])
    elif matched_book:
        b_id = matched_book.get("id")
        sub_id = matched_book.get("subscription_id") or "debf3e10-c27c-469a-a2aa-8a30c919db91"
        book_type = matched_book.get("book_type", "pdf")
        viewer = "index.html" if book_type == "reflowable" else "pdfviewer.html"
        base_url = _reader_url(str(b_id), str(sub_id), str(book_type))
    else:
        import os
        sub_id = os.environ.get("PEARSON_SUBSCRIPTION_ID", "debf3e10-c27c-469a-a2aa-8a30c919db91")
        base_url = _reader_url(str(book_or_uuid), str(sub_id))

    clean_base = re.sub(r"/page/\d+", "", base_url)
    if page and int(page) >= 1:
        return f"{clean_base}/page/{int(page)}"
    return clean_base


def resolve(book_id: str, page: int = 1) -> str | None:
    """Resolve a book identifier (UUID, slug, doc_id, ISBN, or title) to a Pearson reader URL.

    Args:
        book_id: Any identifier for the Pearson book.
        page: The page to navigate to.

    Returns:
        Pearson reader URL string with page fragment, or None if not found.
    """
    if not book_id:
        return None
    catalog = _load_pearson_catalog()
    matched = _fuzzy_match_book(catalog, query_id=book_id, query_title=book_id, query_isbn=book_id)
    if matched:
        return build_reader_url(matched, page=page)
    return None
