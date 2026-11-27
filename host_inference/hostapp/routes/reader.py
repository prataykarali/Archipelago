"""Reader routes: exact page-view resolution, PDF streaming and Pearson open.

One concern: resolving a document id + page number to an exact, working source
page — the institutional Pearson reader, a Hugging Face dataset PDF, or the
internal reader — and streaming those sources.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote, unquote

from engine import _hf_doc_path
from engine.access_profile import is_open_access_profile
from engine.corpus_titles import clean_bibliographic_title
from flask import Flask, current_app, jsonify, redirect, request, send_from_directory
from hf_revision import dataset_revision
from library_index import hf_title, resolve_hf_path, resolve_hf_source
from remote_cache import load_books, pearson_page_url
import requests

from ..config import UI
from ..context import AppContext
from ..user_traffic import record_user_action

READER_PAGE_FILE = "reader.html"
HF_REPO_NAME = os.environ.get("HF_LIBRARY_REPO", "Prataykarali/Library_books")
HF_DATASET_RESOLVE_BASE = (
    f"https://huggingface.co/datasets/{HF_REPO_NAME}/resolve/{dataset_revision(HF_REPO_NAME)}"
)
HF_STREAM_CHUNK_BYTES = 65536
HF_STREAM_TIMEOUT_SEC = 12
MIN_PAGE = 1
MAX_BOOK_ID_LEN = 128
MAX_DOC_ID_LEN = 256

BOOK_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\. ]+$")
SAFE_DOC_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\./ ()&,+'\[\]]+$")
SAFE_FILENAME_PATTERN = re.compile(r"[^a-zA-Z0-9_.\-]")

DATASET_PREFIXES = ("papers/", "textbooks/", "archipelago-books-cs/")
JSON_MIME = "application/json"
PDF_MIME = "application/pdf"


def _wants_json() -> bool:
    """True when the caller asked for JSON rather than a redirect."""
    return bool(
        request.is_json
        or request.args.get("format") == "json"
        or JSON_MIME in request.headers.get("Accept", "")
    )


def _find_pearson_book(doc_id: str) -> dict | None:
    """Match a Pearson shelf record by id, slug, ISBN or title fragment."""
    if is_open_access_profile():
        return None
    for book in load_books():
        if doc_id in (book.get("id") or "", book.get("slug") or "", book.get("isbn") or ""):
            return book
        if doc_id and doc_id.lower() in (book.get("title") or "").lower():
            return book
    return None


def register(app: Flask, ctx: AppContext) -> None:
    """Register reader routes on ``app``."""

    @app.route("/api/page-view", methods=["GET", "POST"])
    def page_view():
        raw_data = request.get_json(silent=True)
        data = raw_data if isinstance(raw_data, dict) else {}
        doc_id = str(
            request.args.get("doc_id")
            or request.args.get("doc")
            or request.args.get("id")
            or data.get("doc_id")
            or data.get("doc")
            or data.get("id")
            or ""
        ).strip()
        if len(doc_id) > MAX_DOC_ID_LEN or "\x00" in doc_id or ".." in doc_id or "\\" in doc_id:
            return jsonify({"error": "bad_request", "detail": "Invalid document identifier."}), 400
        try:
            page = max(MIN_PAGE, int(request.args.get("page") or data.get("page") or 1))
        except (ValueError, TypeError):
            page = MIN_PAGE

        book = _find_pearson_book(doc_id)
        if book is not None:
            raw_page_arg = request.args.get("page") or data.get("page")
            pearson_page = page if raw_page_arg not in (None, "") else None
            pearson_url = pearson_page_url(book, pearson_page)
            if not _wants_json():
                suffix = f"?page={pearson_page}" if pearson_page else ""
                return redirect(f"/open/{book.get('id')}{suffix}")
            return jsonify(
                {
                    "doc_id": book.get("id"),
                    "page": pearson_page,
                    "page_verified": False,
                    "book_type": book.get("book_type", "pdf"),
                    "title": book.get("title"),
                    "pdf_url": pearson_url,
                    "url": pearson_url,
                    "is_pearson": True,
                }
            )

        mapped = _hf_doc_path(doc_id) or doc_id
        verified_hf = resolve_hf_path(mapped) or resolve_hf_path(doc_id)
        if not verified_hf:
            return jsonify(
                {
                    "error": "not_found",
                    "detail": "This document is not a reader-backed dataset file.",
                }
            ), 404
        clean_doc = verified_hf.lstrip("/").removeprefix("papers/")
        target = f"/read?doc={quote(doc_id, safe='')}&page={page}#page={page}"
        if not _wants_json():
            return redirect(target)
        return jsonify(
            {
                "doc_id": doc_id,
                "page": page,
                "title": clean_bibliographic_title(verified_hf, hf_title(verified_hf))
                if verified_hf
                else "Document",
                "pdf_url": f"/papers/{clean_doc}",
                "url": target,
                "is_pearson": False,
            }
        )

    @app.get("/read")
    @app.get("/read/<path:subpath>")
    def read_page(subpath: str = ""):
        """Serve the full PDF reader interface."""
        return send_from_directory(UI, READER_PAGE_FILE)

    @app.get("/api/reader/info")
    @app.get("/api/reader/info/<path:resource_id>")
    def reader_info_api(resource_id: str = ""):
        """Metadata inspection endpoint for reader.html."""
        raw_id = (
            resource_id
            or request.args.get("doc")
            or request.args.get("id")
            or request.args.get("doc_id")
            or ""
        )
        clean_id = unquote(str(raw_id)).removeprefix("book/").strip()
        if (
            len(clean_id) > MAX_DOC_ID_LEN
            or "\x00" in clean_id
            or ".." in clean_id
            or "\\" in clean_id
        ):
            return jsonify({"error": "bad_request", "detail": "Invalid resource identifier."}), 400
        if clean_id:
            record_user_action("reader_open", clean_id)
        try:
            page = max(MIN_PAGE, int(request.args.get("page") or 1))
        except (ValueError, TypeError):
            page = MIN_PAGE

        book = _find_pearson_book(clean_id)
        if book is not None:
            raw_page_arg = request.args.get("page")
            pearson_page = page if raw_page_arg not in (None, "") else None
            return jsonify(
                {
                    "id": book.get("id"),
                    "title": book.get("title", ""),
                    "author": book.get("author", "Pearson Education"),
                    "provider": "pearson",
                    "book_type": book.get("book_type", "pdf"),
                    "page_verified": False,
                    "reader_url": pearson_page_url(book, pearson_page),
                    "page_count": book.get("page_count", 0),
                }
            )

        target_path = resolve_hf_path(_hf_doc_path(clean_id)) or resolve_hf_path(clean_id)
        if not target_path:
            return jsonify(
                {
                    "error": "not_found",
                    "detail": "This document is not a reader-backed dataset file.",
                }
            ), 404
        clean_target = target_path.lstrip("/")
        pdf_route = f"/papers/{clean_target.removeprefix('papers/').lstrip('/')}"
        title_guess = (
            clean_bibliographic_title(clean_target, hf_title(clean_target))
            if clean_target
            else clean_bibliographic_title(clean_id)
        )
        return jsonify(
            {
                "id": clean_id,
                "title": title_guess,
                "author": "Archipelago Research Holding (HF Dataset)",
                "provider": "huggingface",
                "pdf_url": pdf_route,
                "page": page,
            }
        )

    @app.get("/papers/<path:doc_path>")
    @app.get("/pdfs/<path:doc_path>")
    def hosted_paper(doc_path: str):
        """Stream one dataset PDF. The browser opens #page=N on this response."""
        doc_path = unquote(doc_path).lstrip("/")
        if not doc_path or ".." in doc_path or "\\" in doc_path or "\x00" in doc_path:
            return jsonify({"error": "bad_path", "detail": "Invalid document path."}), 400
        if not SAFE_DOC_PATH_PATTERN.match(doc_path):
            return jsonify(
                {"error": "bad_path", "detail": "Disallowed characters in document path."}
            ), 400
        token = os.environ.get("HF_TOKEN", "").strip()

        clean_path = doc_path.lstrip("/")
        clean_path = re.sub(r"^(papers/)+", "papers/", clean_path)
        clean_path = re.sub(r"^(textbooks/)+", "textbooks/", clean_path)

        book = _find_pearson_book(clean_path)
        if book is not None:
            return redirect(pearson_page_url(book, 1))

        mapped = _hf_doc_path(clean_path)
        candidates = []
        if mapped:
            candidates.append(mapped)
        candidates.append(clean_path)
        for prefix in DATASET_PREFIXES:
            if not clean_path.startswith(prefix):
                candidates.append(f"{prefix}{clean_path}")
        base_name = clean_path.split("/")[-1]
        if base_name != clean_path:
            candidates.append(f"papers/{base_name}")
            candidates.append(f"textbooks/{base_name}")

        upstream = None
        seen_verified: set[tuple[str, str]] = set()
        for candidate in candidates:
            repo_name, verified = resolve_hf_source(candidate)
            if not verified:
                continue
            key = (repo_name or HF_REPO_NAME, verified)
            if key in seen_verified:
                continue
            seen_verified.add(key)
            resolve_base = (
                f"https://huggingface.co/datasets/{key[0]}/resolve/{dataset_revision(key[0])}"
            )
            encoded_path = quote(verified, safe="/")
            try:
                response = requests.get(
                    f"{resolve_base}/{encoded_path}",
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                    stream=True,
                    timeout=HF_STREAM_TIMEOUT_SEC,
                    allow_redirects=True,
                )
                if response.status_code == 200:
                    upstream = response
                    break
                response.close()
            except requests.RequestException:
                continue

        if upstream is None or upstream.status_code != 200:
            return jsonify(
                {"error": "not_found", "detail": "That page is not in the dataset."}
            ), 404

        def generate():
            try:
                for chunk in upstream.iter_content(HF_STREAM_CHUNK_BYTES):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        response = current_app.response_class(generate(), mimetype=PDF_MIME)
        raw_filename = doc_path.split("/")[-1] or "paper.pdf"
        filename = SAFE_FILENAME_PATTERN.sub("_", raw_filename) or "paper.pdf"
        response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
        return response

    @app.get("/open/<book_id>")
    @app.get("/open/book/<book_id>")
    def open_pearson(book_id: str):
        """Show the Pearson sign-in handoff for an indexed title."""
        if is_open_access_profile():
            return jsonify(
                {
                    "error": "unavailable_in_open_access",
                    "detail": "Institutional e-book redirects are disabled in open-access mode.",
                }
            ), 404
        # Citations and legacy links may carry the `book/` prefix.
        clean_id = (book_id or "").strip()
        if clean_id.startswith("book/"):
            clean_id = clean_id.removeprefix("book/").strip()
        if not clean_id or len(clean_id) > MAX_BOOK_ID_LEN or not BOOK_ID_PATTERN.match(clean_id):
            return jsonify({"error": "bad_request", "detail": "Invalid book ID format."}), 400

        book = _find_pearson_book(clean_id)
        if book is None:
            return jsonify(
                {"error": "not_found", "detail": "That title is not in the Pearson catalog."}
            ), 404
        raw_page_arg = request.args.get("page")
        pearson_page: int | None = None
        if raw_page_arg not in (None, ""):
            try:
                pearson_page = max(MIN_PAGE, int(raw_page_arg))
            except (ValueError, TypeError):
                pearson_page = None
        if request.args.get("direct") == "1":
            return redirect(pearson_page_url(book, pearson_page), code=302)
        return send_from_directory(UI, "pearson-handoff.html")
