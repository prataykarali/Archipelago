"""Deliver only manifest-approved PDF files with explicit upstream failure states."""

from __future__ import annotations

import os
import re
from urllib.parse import quote

from flask import current_app, jsonify
from library_index import resolve_hf_path
import requests

CHUNK_BYTES = 64 * 1024
TIMEOUT_SECONDS = 30
DEFAULT_REPO = "Prataykarali/Library_books"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def official_pdf_url(doc_path: str, page: int) -> str:
    """Return a Hub file link; browser access may require a Hub account."""
    repo = os.environ.get("HF_DATASET_REPO", DEFAULT_REPO).strip()
    if not REPO_PATTERN.fullmatch(repo):
        return ""
    return f"https://huggingface.co/datasets/{repo}/resolve/main/{quote(doc_path, safe='/')}#page={page}"


def error_response(code: str, detail: str, status: int):
    """Return a browser-readable error, never upstream bodies or credentials."""
    response = jsonify({"error": code, "detail": detail})
    response.status_code = status
    response.headers["Cache-Control"] = "private, no-store"
    return response


def deliver_pdf(doc_path: str):
    """Validate the approved path and PDF signature before sending response headers."""
    if (
        not doc_path
        or any(part in {".", "..", ""} for part in doc_path.split("/"))
        or "\\" in doc_path
        or any(ord(c) < 32 for c in doc_path)
    ):
        return error_response("bad_path", "Invalid document path.", 400)
    path = resolve_hf_path(doc_path)
    if not path:
        return error_response(
            "not_found", "This document is not in the configured library manifest.", 404
        )
    if path != doc_path:
        # Legacy aliases may resolve, but the upstream path always comes from the manifest.
        doc_path = path
    if (
        any(part in {".", "..", ""} for part in doc_path.split("/"))
        or "\\" in doc_path
        or any(ord(c) < 32 for c in doc_path)
    ):
        return error_response("bad_manifest", "The library manifest contains an invalid path.", 503)
    repo = os.environ.get("HF_DATASET_REPO", DEFAULT_REPO).strip()
    if not REPO_PATTERN.fullmatch(repo):
        return error_response(
            "bad_configuration", "Configure HF_DATASET_REPO as owner/dataset.", 503
        )
    token = os.environ.get("HF_TOKEN", "").strip()
    upstream = None
    try:
        upstream = requests.get(
            f"https://huggingface.co/datasets/{repo}/resolve/main/{quote(doc_path, safe='/')}",
            headers={
                **({"Authorization": f"Bearer {token}"} if token else {}),
                "Accept": "application/pdf",
            },
            stream=True,
            timeout=TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        status = upstream.status_code
        if status in {401, 403}:
            return error_response(
                "dataset_access_denied",
                "The server cannot access the library dataset. Check its read credential and dataset ID.",
                503,
            )
        if status == 404:
            return error_response(
                "not_found", "The indexed PDF was not found in the configured dataset.", 404
            )
        if status != 200:
            return error_response(
                "upstream_unavailable",
                "The library dataset service is temporarily unavailable.",
                502,
            )
        iterator = upstream.iter_content(CHUNK_BYTES)
        first = b""
        while len(first) < 5:
            first += next(iterator, b"")
            if not first:
                break
            if len(first) < 5:
                # Requests normally emits full-size chunks except at EOF.
                extra = next(iterator, b"")
                if not extra:
                    break
                first += extra
        if not first.startswith(b"%PDF-"):
            return error_response(
                "invalid_pdf",
                "The dataset returned a non-PDF response; no document was displayed.",
                502,
            )
        stream = upstream
        upstream = None

        def generate():
            try:
                yield first
                yield from (chunk for chunk in iterator if chunk)
            finally:
                stream.close()

        response = current_app.response_class(generate(), mimetype="application/pdf")
        response.call_on_close(stream.close)
        response.headers["Content-Disposition"] = "inline"
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Library-Source"] = "manifest-approved"
        return response
    except requests.RequestException:
        return error_response(
            "upstream_unavailable", "The library dataset could not be reached. Please retry.", 502
        )
    finally:
        if upstream is not None:
            upstream.close()
