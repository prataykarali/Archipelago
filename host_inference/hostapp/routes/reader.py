"""Reader routes: exact page-view resolution, PDF validation, D14 OA & Pearson open.

One concern: resolving a document id + page number (or printed page) to a
validated source target — an HF dataset PDF, a license-compliant D14 canonical
OA URL, or an institutional Pearson reader — with strict page-bounds validation
and structured 4-state provenance JSON on missing/metadata-only docs.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote, unquote

from engine import _hf_doc_path
from engine.access_profile import (
    d14_canonical_oa_url,
    is_d14_excluded_commercial,
    is_open_access_profile,
    is_restricted_artifact_path,
    lookup_d14_source,
)
from engine.provenance import (
    EVIDENCE_STATE_AUTHORIZED_EXTERNAL,
    EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
    EVIDENCE_STATE_LABELS,
    EVIDENCE_STATE_METADATA_ONLY,
    EVIDENCE_STATE_UNAVAILABLE,
    SOURCE_KIND_INSTITUTIONAL,
    SOURCE_KIND_LABELS,
    SOURCE_KIND_METADATA_ONLY,
    SOURCE_KIND_UNAVAILABLE,
    SOURCE_KIND_VERIFIED_FULL_TEXT,
    format_canonical_title,
    ostep_chapter_info,
    printed_to_pdf_page,
    resolve_page_provenance,
)
from engine.source_resolution import is_toc_or_index_doc
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
HF_STREAM_CHUNK_BYTES = 65536
HF_STREAM_TIMEOUT_SEC = 12
MIN_PAGE = 1
MAX_REASONABLE_PAGE = 2500
MAX_BOOK_ID_LEN = 128
MAX_DOC_ID_LEN = 256
PDF_MAGIC_HEADER = b"%PDF-"

BOOK_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\. ]+$")
SAFE_DOC_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\./ ()&,+'\[\]]+$")
SAFE_FILENAME_PATTERN = re.compile(r"[^a-zA-Z0-9_.\-]")
DATASET_PREFIXES = ("papers/", "textbooks/", "archipelago-books-cs/")
JSON_MIME = "application/json"
PDF_MIME = "application/pdf"
_NON_PDF_MIMES = ("text/html", "application/json", "text/plain", "application/xml")


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


def _unavailable_response(
    doc_id: str,
    detail: str,
    *,
    error: str = "unavailable_document",
    source_kind: str = SOURCE_KIND_UNAVAILABLE,
    evidence_state: str = EVIDENCE_STATE_UNAVAILABLE,
):
    """Return a clean, non-leaky 404 JSON payload for an unavailable or metadata-only doc."""
    return (
        jsonify(
            {
                "error": error,
                "detail": detail,
                "doc_id": doc_id,
                "title": format_canonical_title(doc_id) if doc_id else "Unavailable Document",
                "source_kind": source_kind,
                "source_kind_label": SOURCE_KIND_LABELS[source_kind],
                "evidence_state": evidence_state,
                "evidence_state_label": EVIDENCE_STATE_LABELS[evidence_state],
                "url": "",
                "clickable": False,
                "reader_resolvable": False,
                "pdf_available": False,
            }
        ),
        404,
    )


def _validate_page_number(
    raw_page: object, doc_id: str, raw_printed_page: object = None
) -> tuple[int, bool]:
    """Parse requested page (or map printed_page -> PDF page) and enforce document bounds."""
    if raw_page in (None, "") and raw_printed_page not in (None, ""):
        mapped_pdf = printed_to_pdf_page(doc_id, raw_printed_page)
        return (mapped_pdf, True) if mapped_pdf is not None else (MIN_PAGE, False)
    try:
        parsed = int(raw_page) if raw_page not in (None, "") else MIN_PAGE
    except (ValueError, TypeError):
        return MIN_PAGE, False
    if parsed < MIN_PAGE:
        return MIN_PAGE, False
    prov = resolve_page_provenance(doc_id, parsed)
    max_pages = prov.get("known_page_count") or MAX_REASONABLE_PAGE
    if parsed > max_pages:
        return max_pages, False
    return parsed, True


def _d14_external_oa_payload(
    doc_id: str, entry: dict, raw_page: object, raw_printed: object = None
) -> dict | None:
    """Build a verified external OA payload for a ``d14_oa/*`` corpus source."""
    ext_url = d14_canonical_oa_url(entry["source_id"])
    if not ext_url:
        return None
    page, page_valid = _validate_page_number(raw_page, entry["doc_id"], raw_printed)
    page_prov = resolve_page_provenance(entry["doc_id"], page, raw_printed)
    target = f"{ext_url}#page={page}" if (ext_url.lower().endswith(".pdf") and page_valid) else ext_url
    return {
        "id": doc_id,
        "doc_id": entry["doc_id"],
        "source_id": entry["source_id"],
        "title": entry["title"] or format_canonical_title(entry["doc_id"]),
        "author": entry.get("authors") or "Open Access",
        "provider": "d14_open_access",
        "source_format": entry["source_format"],
        "license_name": entry.get("license_name") or "",
        "license_url": entry.get("license_url") or "",
        "page": page,
        "pdf_page": page_prov["pdf_page"],
        "printed_page": page_prov["printed_page"],
        "page_offset": page_prov["page_offset"],
        "page_display": page_prov["page_display"],
        "pages_differ": page_prov["pages_differ"],
        "page_valid": page_valid,
        "page_count": page_prov.get("known_page_count"),
        "pdf_url": target if entry["source_format"] == "pdf" else "",
        "url": target,
        "canonical_url": ext_url,
        "pdf_available": entry["source_format"] == "pdf",
        "reader_resolvable": True,
        "clickable": True,
        "is_pearson": False,
        "source_kind": SOURCE_KIND_VERIFIED_FULL_TEXT,
        "source_kind_label": SOURCE_KIND_LABELS[SOURCE_KIND_VERIFIED_FULL_TEXT],
        "evidence_state": EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
        "evidence_state_label": EVIDENCE_STATE_LABELS[EVIDENCE_STATE_AVAILABLE_FULL_TEXT],
    }


def _resolve_reader_target(
    doc_id: str, raw_page: object, raw_printed: object = None
) -> tuple[dict | None, str | None, object | None]:
    """Shared resolution for ``/api/page-view`` and ``/api/reader/info``.

    Returns ``(payload_dict, redirect_url, error_response)``.
    """
    if is_d14_excluded_commercial(doc_id):
        return None, None, _unavailable_response(
            doc_id,
            "Metadata-only commercial holding excluded under open-access license gate.",
            error="metadata_only_record",
            source_kind=SOURCE_KIND_METADATA_ONLY,
            evidence_state=EVIDENCE_STATE_METADATA_ONLY,
        )
    if is_open_access_profile() and is_restricted_artifact_path(doc_id):
        return None, None, _unavailable_response(
            doc_id, "This document is restricted or unavailable in open-access mode."
        )

    d14_entry = lookup_d14_source(doc_id)
    if d14_entry is not None and d14_entry["is_approved_oa"] and d14_entry["origin"] == "d14_oa_acquisition":
        ext_payload = _d14_external_oa_payload(doc_id, d14_entry, raw_page, raw_printed)
        if ext_payload is not None:
            return ext_payload, ext_payload["url"], None

    page, _page_valid = _validate_page_number(raw_page, doc_id, raw_printed)
    book = _find_pearson_book(doc_id)
    if book is not None:
        pearson_page = page if raw_page not in (None, "") else None
        pearson_url = pearson_page_url(book, pearson_page)
        suffix = f"?page={pearson_page}" if pearson_page else ""
        payload = {
            "id": book.get("id"),
            "doc_id": book.get("id"),
            "page": pearson_page,
            "page_verified": False,
            "book_type": book.get("book_type", "pdf"),
            "title": book.get("title", ""),
            "author": book.get("author", "Pearson Education"),
            "provider": "pearson",
            "page_count": book.get("page_count", 0),
            "pdf_url": pearson_url,
            "reader_url": pearson_url,
            "url": pearson_url,
            "is_pearson": True,
            "source_kind": SOURCE_KIND_INSTITUTIONAL,
            "source_kind_label": SOURCE_KIND_LABELS[SOURCE_KIND_INSTITUTIONAL],
            "evidence_state": EVIDENCE_STATE_AUTHORIZED_EXTERNAL,
            "evidence_state_label": EVIDENCE_STATE_LABELS[EVIDENCE_STATE_AUTHORIZED_EXTERNAL],
        }
        return payload, f"/open/{book.get('id')}{suffix}", None

    if is_toc_or_index_doc(doc_id):
        return None, None, _unavailable_response(
            doc_id,
            "This record is a TOC/index metadata stub without a full-text PDF.",
            error="metadata_only_record",
            source_kind=SOURCE_KIND_METADATA_ONLY,
            evidence_state=EVIDENCE_STATE_METADATA_ONLY,
        )

    mapped = _hf_doc_path(doc_id) or doc_id
    verified_hf = resolve_hf_path(mapped) or resolve_hf_path(doc_id)
    if not verified_hf and d14_entry is not None and d14_entry["is_approved_oa"] and d14_entry["source_format"] == "pdf":
        verified_hf = d14_entry["doc_id"]
    if not verified_hf or not verified_hf.lower().endswith(".pdf"):
        return None, None, _unavailable_response(
            doc_id, "This document is not a reader-backed dataset file.", error="not_found"
        )
    if is_open_access_profile() and is_restricted_artifact_path(verified_hf):
        return None, None, _unavailable_response(
            doc_id, "This document is restricted or unavailable in open-access mode."
        )

    page, page_valid = _validate_page_number(raw_page, verified_hf, raw_printed)
    page_prov = resolve_page_provenance(verified_hf, page, raw_printed)
    ostep = ostep_chapter_info(verified_hf) or {}
    clean_doc = verified_hf.lstrip("/").removeprefix("papers/").lstrip("/")
    target = f"/read?doc={quote(doc_id, safe='')}&page={page}#page={page}"
    payload = {
        "id": doc_id,
        "doc_id": doc_id,
        "title": format_canonical_title(verified_hf, hf_title(verified_hf)),
        "author": "Archipelago Research Holding (HF Dataset)",
        "provider": "huggingface",
        "page": page,
        "pdf_page": page_prov["pdf_page"],
        "printed_page": page_prov["printed_page"],
        "page_offset": page_prov["page_offset"],
        "page_display": page_prov["page_display"],
        "pages_differ": page_prov["pages_differ"],
        "page_valid": page_valid,
        "page_count": page_prov.get("known_page_count"),
        "pdf_url": f"/papers/{clean_doc}",
        "url": target,
        "doc_revision": dataset_revision(HF_REPO_NAME),
        "pdf_available": True,
        "reader_resolvable": True,
        "clickable": True,
        "is_pearson": False,
        "source_kind": SOURCE_KIND_VERIFIED_FULL_TEXT,
        "source_kind_label": SOURCE_KIND_LABELS[SOURCE_KIND_VERIFIED_FULL_TEXT],
        "evidence_state": EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
        "evidence_state_label": EVIDENCE_STATE_LABELS[EVIDENCE_STATE_AVAILABLE_FULL_TEXT],
        **ostep,
    }
    return payload, target, None


def _peek_valid_pdf_chunk(upstream: requests.Response) -> bytes | None:
    """Validate upstream MIME type and peek the first non-empty PDF chunk."""
    content_type = str(upstream.headers.get("Content-Type") or "").lower()
    if any(bad in content_type for bad in _NON_PDF_MIMES):
        return None
    for chunk in upstream.iter_content(HF_STREAM_CHUNK_BYTES):
        if chunk:
            return chunk if chunk.lstrip().startswith(PDF_MAGIC_HEADER) else None
    return None


def register(app: Flask, ctx: AppContext) -> None:
    """Register reader routes on ``app``."""
    del ctx

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
        raw_page = request.args.get("page") or data.get("page")
        raw_printed = request.args.get("printed_page") or data.get("printed_page")
        payload, target, err = _resolve_reader_target(doc_id, raw_page, raw_printed)
        if err is not None:
            return err
        if not _wants_json() and target:
            return redirect(target)
        return jsonify(payload)

    @app.get("/read")
    @app.get("/read/<path:subpath>")
    def read_page(subpath: str = ""):
        """Serve the full PDF reader interface."""
        del subpath
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
        if len(clean_id) > MAX_DOC_ID_LEN or "\x00" in clean_id or ".." in clean_id or "\\" in clean_id:
            return jsonify({"error": "bad_request", "detail": "Invalid resource identifier."}), 400
        if clean_id:
            record_user_action("reader_open", clean_id)
        payload, _target, err = _resolve_reader_target(
            clean_id, request.args.get("page"), request.args.get("printed_page")
        )
        if err is not None:
            return err
        return jsonify(payload)

    @app.get("/papers/<path:doc_path>")
    @app.get("/pdfs/<path:doc_path>")
    def hosted_paper(doc_path: str):
        """Stream one validated dataset PDF. The browser opens #page=N on this response."""
        doc_path = unquote(doc_path).lstrip("/")
        if not doc_path or ".." in doc_path or "\\" in doc_path or "\x00" in doc_path:
            return jsonify({"error": "bad_path", "detail": "Invalid document path."}), 400
        if not SAFE_DOC_PATH_PATTERN.match(doc_path):
            return jsonify({"error": "bad_path", "detail": "Disallowed characters in document path."}), 400
        if is_d14_excluded_commercial(doc_path):
            return _unavailable_response(
                doc_path,
                "Metadata-only commercial holding excluded under open-access license gate.",
                error="metadata_only_record",
                source_kind=SOURCE_KIND_METADATA_ONLY,
                evidence_state=EVIDENCE_STATE_METADATA_ONLY,
            )
        if is_open_access_profile() and is_restricted_artifact_path(doc_path):
            return _unavailable_response(
                doc_path, "This document is restricted or unavailable in open-access mode."
            )
        if is_toc_or_index_doc(doc_path):
            return _unavailable_response(
                doc_path,
                "This record is a TOC/index metadata stub without a full-text PDF.",
                error="metadata_only_record",
                source_kind=SOURCE_KIND_METADATA_ONLY,
                evidence_state=EVIDENCE_STATE_METADATA_ONLY,
            )

        token = os.environ.get("HF_TOKEN", "").strip()
        clean_path = re.sub(r"^(papers/)+", "papers/", doc_path.lstrip("/"))
        clean_path = re.sub(r"^(textbooks/)+", "textbooks/", clean_path)
        book = _find_pearson_book(clean_path)
        if book is not None:
            return redirect(pearson_page_url(book, 1))

        mapped = _hf_doc_path(clean_path)
        candidates = [mapped] if mapped else []
        candidates.append(clean_path)
        for prefix in DATASET_PREFIXES:
            if not clean_path.startswith(prefix):
                candidates.append(f"{prefix}{clean_path}")
        base_name = clean_path.split("/")[-1]
        if base_name != clean_path:
            candidates.extend([f"papers/{base_name}", f"textbooks/{base_name}"])

        upstream, first_chunk, resolved_revision = None, None, ""
        seen_verified: set[tuple[str, str]] = set()
        for candidate in candidates:
            repo_name, verified = resolve_hf_source(candidate)
            if not verified or not verified.lower().endswith(".pdf"):
                continue
            if is_open_access_profile() and is_restricted_artifact_path(verified):
                continue
            repo_id = repo_name or HF_REPO_NAME
            if (repo_id, verified) in seen_verified:
                continue
            seen_verified.add((repo_id, verified))
            rev = dataset_revision(repo_id)
            resolve_base = f"https://huggingface.co/datasets/{repo_id}/resolve/{rev}"
            try:
                response = requests.get(
                    f"{resolve_base}/{quote(verified, safe='/')}",
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                    stream=True,
                    timeout=HF_STREAM_TIMEOUT_SEC,
                    allow_redirects=True,
                )
                if response.status_code == 200:
                    peeked = _peek_valid_pdf_chunk(response)
                    if peeked is not None:
                        upstream, first_chunk, resolved_revision = response, peeked, rev
                        break
                response.close()
            except requests.RequestException:
                continue

        if upstream is None or first_chunk is None:
            return _unavailable_response(
                doc_path, "That document is not available as a validated PDF in the dataset.", error="not_found"
            )

        def generate():
            try:
                yield first_chunk
                for chunk in upstream.iter_content(HF_STREAM_CHUNK_BYTES):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        response = current_app.response_class(generate(), mimetype=PDF_MIME)
        filename = SAFE_FILENAME_PATTERN.sub("_", doc_path.split("/")[-1] or "paper.pdf") or "paper.pdf"
        response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
        response.headers["X-Archipelago-Artifact-Verified"] = "true"
        response.headers["X-Archipelago-Doc-Revision"] = resolved_revision
        response.headers["X-Archipelago-Source-Kind"] = SOURCE_KIND_VERIFIED_FULL_TEXT
        response.headers["X-Archipelago-Evidence-State"] = EVIDENCE_STATE_AVAILABLE_FULL_TEXT
        return response

    @app.get("/open/<book_id>")
    @app.get("/open/book/<book_id>")
    def open_pearson(book_id: str):
        """Show the Pearson sign-in handoff for an indexed title."""
        if is_open_access_profile():
            return jsonify(
                {
                    "error": "unavailable_in_open_access",
                    "source_kind": SOURCE_KIND_METADATA_ONLY,
                    "evidence_state": EVIDENCE_STATE_UNAVAILABLE,
                    "detail": "Institutional e-book redirects are disabled in open-access mode.",
                }
            ), 404
        clean_id = (book_id or "").strip().removeprefix("book/").strip()
        if not clean_id or len(clean_id) > MAX_BOOK_ID_LEN or not BOOK_ID_PATTERN.match(clean_id):
            return jsonify({"error": "bad_request", "detail": "Invalid book ID format."}), 400
        book = _find_pearson_book(clean_id)
        if book is None:
            return jsonify(
                {
                    "error": "not_found",
                    "source_kind": SOURCE_KIND_UNAVAILABLE,
                    "evidence_state": EVIDENCE_STATE_UNAVAILABLE,
                    "detail": "That title is not in the Pearson catalog.",
                }
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
