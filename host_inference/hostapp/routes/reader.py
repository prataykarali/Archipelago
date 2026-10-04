"""Resolve manifest-backed documents and honestly hand off external books.

Only rendering a PDF can confirm its requested page. Metadata and constructed
external URLs are not verification of access or page navigation.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from engine import _hf_doc_path
from flask import Flask, jsonify, redirect, request, send_from_directory
from library_index import hf_title, resolve_hf_path
from pearson_handoff import handoff
from remote_cache import load_books, pearson_page_url

from ..config import UI
from ..context import AppContext
from ..hf_delivery import deliver_pdf, error_response

READER_PAGE_FILE = "reader.html"
MIN_PAGE = 1
MAX_BOOK_ID_LEN = 128

BOOK_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\. ]+$")

JSON_MIME = "application/json"


def _wants_json() -> bool:
    """True when the caller asked for JSON rather than a redirect."""
    return bool(
        request.is_json
        or request.args.get("format") == "json"
        or JSON_MIME in request.headers.get("Accept", "")
    )


def _find_pearson_book(doc_id: str) -> dict | None:
    """Resolve exact identifiers or an unambiguous exact title, never a guess."""
    if not doc_id:
        return None
    books = load_books()
    for book in books:
        if doc_id in (book.get("id"), book.get("slug"), book.get("isbn")):
            return book
    matches = [book for book in books if (book.get("title") or "").strip().casefold() == doc_id.casefold()]
    return matches[0] if len(matches) == 1 else None



def register(app: Flask, ctx: AppContext) -> None:
    """Register reader routes on ``app``."""

    @app.route("/api/page-view", methods=["GET", "POST"])
    def page_view():
        data = request.get_json(silent=True) or {}
        doc_id = (
            request.args.get("doc_id")
            or request.args.get("doc")
            or request.args.get("id")
            or data.get("doc_id")
            or data.get("doc")
            or data.get("id")
            or ""
        ).strip()
        try:
            page = int(request.args.get("page") or data.get("page") or 1)
            if page < MIN_PAGE:
                raise ValueError
        except (ValueError, TypeError):
            return error_response("bad_page", "Page must be a positive integer.", 400)

        book = _find_pearson_book(doc_id)
        if book is not None:
            pearson_url = pearson_page_url(book, page)
            if not _wants_json():
                return redirect(f"/open/{book.get('id')}?page={page}")
            return jsonify({
                "doc_id": book.get("id"),
                "page": page,
                "title": book.get("title"),
                "pdf_url": f"/open/{book.get('id')}?page={page}",
                "url": f"/open/{book.get('id')}?page={page}",
                "external_url": pearson_url,
                "is_pearson": True,
                "verified": False,
                "page_verified": False,
                "navigation": "manual_page",
                "note": f"Open the book, then go to page {page} in Pearson.",
            })

        mapped = resolve_hf_path(_hf_doc_path(doc_id)) or resolve_hf_path(doc_id)
        if not mapped:
            return error_response("not_found", "This document is not in the configured library manifest.", 404)
        clean_doc = quote(mapped, safe="/")
        target = f"/read?doc={quote(doc_id, safe='')}&page={page}#page={page}"
        if not _wants_json():
            return redirect(target)
        return jsonify({
            "doc_id": doc_id,
            "page": page,
            "title": hf_title(mapped) if mapped else "Document",
            "pdf_url": f"/papers/{clean_doc}",
            "url": target,
            "is_pearson": False,
            "verified": False,
            "page_verified": False,
            "status": "manifest_only",
        })

    @app.get("/read")
    @app.get("/read/<path:subpath>")
    def read_page(subpath: str = ""):
        """Serve the full PDF reader interface."""
        return send_from_directory(UI, READER_PAGE_FILE)

    @app.get("/api/reader/info/<path:resource_id>")
    def reader_info_api(resource_id: str):
        """Metadata inspection endpoint for reader.html."""
        clean_id = resource_id.removeprefix("book/").strip()
        try:
            page = int(request.args.get("page") or 1)
            if page < MIN_PAGE:
                raise ValueError
        except (ValueError, TypeError):
            return error_response("bad_page", "Page must be a positive integer.", 400)

        book = _find_pearson_book(clean_id)
        if book is not None:
            return jsonify({
                "id": book.get("id"),
                "title": book.get("title", ""),
                "author": book.get("author", "Pearson Education"),
                "provider": "pearson",
                "reader_url": f"/open/{book.get('id')}?page={page}",
                "external_url": pearson_page_url(book, page),
                "navigation": "manual_page",
                "page_verified": False,
                "page_count": book.get("page_count", 0),
            })

        target_path = resolve_hf_path(_hf_doc_path(clean_id)) or resolve_hf_path(clean_id)
        if not target_path:
            return jsonify({"error": "not_found", "detail": "This document is not a reader-backed dataset file."}), 404
        clean_target = target_path.lstrip("/")
        pdf_route = f"/papers/{quote(clean_target, safe='/')}"
        title_guess = (
            hf_title(clean_target)
            if clean_target
            else clean_id.split("/")[-1].replace(".pdf", "").replace("_", " ").title()
        )
        return jsonify({
            "id": clean_id,
            "title": title_guess,
            "author": "Archipelago Research Holding (HF Dataset)",
            "provider": "huggingface",
            "pdf_url": pdf_route,
            "page": page,
            "page_verified": False,
            "status": "manifest_only",
        })

    @app.get("/papers/<path:doc_path>")
    @app.get("/pdfs/<path:doc_path>")
    def hosted_paper(doc_path: str):
        """Serve an approved PDF, never an HTML login page disguised as a PDF."""
        return deliver_pdf(doc_path)

    @app.get("/open/<book_id>")
    @app.get("/open/book/<book_id>")
    def open_pearson(book_id: str):
        """Show an honest book-opening handoff with manual page instructions."""
        # Citations and legacy links may carry the `book/` prefix.
        clean_id = (book_id or "").strip()
        if clean_id.startswith("book/"):
            clean_id = clean_id.removeprefix("book/").strip()
        if not clean_id or len(clean_id) > MAX_BOOK_ID_LEN or not BOOK_ID_PATTERN.match(clean_id):
            return jsonify({"error": "bad_request", "detail": "Invalid book ID format."}), 400

        book = _find_pearson_book(clean_id)
        if book is None:
            return jsonify({"error": "not_found", "detail": "That title is not in the Pearson catalog."}), 404
        try:
            page = int(request.args.get("page") or 1)
            if page < MIN_PAGE:
                raise ValueError
        except (ValueError, TypeError):
            return error_response("bad_page", "Page must be a positive integer.", 400)
        if book.get("page_count") and page > int(book["page_count"]):
            return error_response("bad_page", "Requested page exceeds the catalogued page count.", 400)
        return handoff(book.get("title") or "Pearson book", pearson_page_url(book, page), page)
