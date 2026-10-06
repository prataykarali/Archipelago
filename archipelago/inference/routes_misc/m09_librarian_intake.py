"""Librarian intake helpers: mention-a-book, page-image prefill, spreadsheet merge.

These routes turn a librarian's free-text mention, a scanned index/content page,
or a catalogue export into a populated, reviewable ingestion record. They never
mutate the graph themselves: they return a plan or a prefill that the librarian
confirms through the existing staged ingestion job.
"""

from __future__ import annotations

import logging
from pathlib import Path
import tempfile

from flask import jsonify, request

from archipelago.auth import require_librarian
from archipelago.inference import state as st
from archipelago.ingestion.mention import MentionResult, mention_book, prefill_from_match
from archipelago.ingestion.page_image import (
    IMAGE_FORMATS,
    OCRUnavailable,
    build_prefill,
    extract_page_from_image,
    extract_page_from_text,
    is_supported_image,
    ocr_available,
)
from archipelago.ingestion.spreadsheet import apply_merge, plan_merge

logger = logging.getLogger("archipelago.inference.routes_misc.librarian_intake")

OK = 200
BAD_REQUEST = 400
UNPROCESSABLE = 422
SERVER_ERROR = 500
MAX_SHEET_BYTES = 32 * 1024 * 1024
RECORD_TYPES = ("resource", "subject")
DEFAULT_RECORD_TYPE = "resource"
MAX_MENTION_CHARS = 300
MAX_PAGE_TEXT_CHARS = 20000
IMAGE_UPLOAD_FIELD = "file"
SHEET_COPY_CHUNK_BYTES = 64 * 1024


def _error(message: str, status: int, **extra):
    return jsonify({"error": message, **extra}), status


@st.app.route("/api/ingest/mention", methods=["POST"])
@require_librarian
def ingest_mention():
    """Resolve a librarian's book mention into ranked, source-linked candidates."""
    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or data.get("mention") or "").strip()
    if not query:
        return _error("Mention is empty; type a book title, ISBN, or filename.", BAD_REQUEST)
    if len(query) > MAX_MENTION_CHARS:
        return _error(f"Mention is longer than {MAX_MENTION_CHARS} characters.", BAD_REQUEST)

    limit = data.get("limit")
    try:
        limit = int(limit) if limit else 0
    except (TypeError, ValueError):
        limit = 0

    result: MentionResult = mention_book(query, limit=limit or 8)
    payload = result.to_dict()
    if payload["matches"]:
        # Include a ready-to-submit prefill for the top candidate.
        payload["prefill"] = prefill_from_match(result.matches[0])
    return jsonify(payload), OK


@st.app.route("/api/ingest/page-image", methods=["POST"])
@require_librarian
def ingest_page_image():
    """OCR an uploaded index/content page image and pre-fill the record."""
    uploaded = request.files.get(IMAGE_UPLOAD_FIELD) or request.files.get("image")
    if uploaded is None or not uploaded.filename:
        return _error(
            f"No image uploaded. Send the scan as the '{IMAGE_UPLOAD_FIELD}' form field.",
            BAD_REQUEST,
            accepted_formats=list(IMAGE_FORMATS),
            ocr_available=ocr_available(),
        )
    if not is_supported_image(uploaded.filename):
        return _error(
            f"Unsupported image type. Accepted: {', '.join(IMAGE_FORMATS)}.",
            BAD_REQUEST,
            accepted_formats=list(IMAGE_FORMATS),
        )

    try:
        data = uploaded.read()
    except OSError as exc:
        logger.warning("Page image read failed: %s", exc)
        return _error("Could not read the uploaded image.", SERVER_ERROR)

    try:
        extraction = extract_page_from_image(data)
    except OCRUnavailable as exc:
        return _error(
            str(exc),
            UNPROCESSABLE,
            ocr_available=False,
            paste_text_endpoint="/api/ingest/page-text",
        )
    except Exception as exc:
        logger.exception("Page image extraction failed")
        return _error(f"Could not read that page image: {exc}", UNPROCESSABLE)

    return jsonify(build_prefill(extraction, filename=uploaded.filename)), OK


@st.app.route("/api/ingest/page-text", methods=["POST"])
@require_librarian
def ingest_page_text():
    """Pre-fill a record from pasted page text (no OCR required)."""
    data = request.get_json(silent=True) or {}
    text = str(data.get("text") or "").strip()
    if not text:
        return _error("No page text supplied.", BAD_REQUEST)
    if len(text) > MAX_PAGE_TEXT_CHARS:
        text = text[:MAX_PAGE_TEXT_CHARS]
    extraction = extract_page_from_text(text)
    return jsonify(build_prefill(extraction, filename=str(data.get("filename") or ""))), OK


def _resolve_sheet_path(uploaded) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    """Stage a bounded catalogue export and return its owned temporary directory."""
    suffix = Path(uploaded.filename or "").suffix.lower()
    job_dir = tempfile.TemporaryDirectory(prefix="archipelago_sheet_")
    target = Path(job_dir.name) / f"catalogue{suffix or '.csv'}"
    try:
        written = 0
        with target.open("wb") as destination:
            while chunk := uploaded.stream.read(SHEET_COPY_CHUNK_BYTES):
                written += len(chunk)
                if written > MAX_SHEET_BYTES:
                    raise ValueError("Spreadsheet exceeds the size limit.")
                destination.write(chunk)
    except BaseException:
        job_dir.cleanup()
        raise
    return target, job_dir


def _sheet_from_request() -> tuple[
    Path | None, str | None, tempfile.TemporaryDirectory[str] | None
]:
    """Read a catalogue export from either a file upload or a server path."""
    uploaded = request.files.get("file") or request.files.get("sheet")
    if uploaded is not None and uploaded.filename:
        if not is_supported_sheet(uploaded.filename):
            return (
                None,
                (f"Unsupported spreadsheet type. Accepted: {', '.join(SHEET_SUFFIXES)}."),
                None,
            )
        try:
            path, owner = _resolve_sheet_path(uploaded)
        except ValueError as exc:
            return None, str(exc), None
        return path, None, owner

    data = request.get_json(silent=True) or {}
    raw_path = str(data.get("path") or data.get("file_path") or "").strip()
    if not raw_path:
        return None, "Send a spreadsheet upload or a 'path' to an approved export.", None
    candidate = Path(raw_path)
    if not candidate.is_file():
        return None, "That spreadsheet path does not exist.", None
    if not is_supported_sheet(candidate.name):
        return None, f"Unsupported spreadsheet type. Accepted: {', '.join(SHEET_SUFFIXES)}.", None
    if candidate.stat().st_size > MAX_SHEET_BYTES:
        return None, "Spreadsheet exceeds the size limit.", None
    return candidate, None, None


SHEET_SUFFIXES = (".ods", ".csv", ".tsv", ".xlsx")


def is_supported_sheet(filename: str | None) -> bool:
    """True for the catalogue export formats we can parse."""
    if not filename:
        return False
    return str(filename).lower().endswith(SHEET_SUFFIXES)


def _record_type() -> str:
    data = request.get_json(silent=True) or {}
    value = str(data.get("record_type") or DEFAULT_RECORD_TYPE).strip().lower()
    return value if value in RECORD_TYPES else DEFAULT_RECORD_TYPE


@st.app.route("/api/ingest/spreadsheet/plan", methods=["POST"])
@require_librarian
def ingest_spreadsheet_plan():
    """Dry-run: show CREATE/UPDATE/UNCHANGED/RETIRE without writing anything."""
    path, error, owner = _sheet_from_request()
    if error:
        return _error(error, BAD_REQUEST, supported=list(SHEET_SUFFIXES))
    try:
        plan = plan_merge(path, record_type=_record_type(), retire_missing=False)
        summary = plan.summary()
        summary["dry_run"] = True
        return jsonify(summary), OK
    finally:
        if owner is not None:
            owner.cleanup()


@st.app.route("/api/ingest/spreadsheet/apply", methods=["POST"])
@require_librarian
def ingest_spreadsheet_apply():
    """Apply a catalogue export. Idempotent: re-running changes nothing."""
    path, error, owner = _sheet_from_request()
    if error:
        return _error(error, BAD_REQUEST, supported=list(SHEET_SUFFIXES))
    try:
        data = request.get_json(silent=True) or {}
        retire_missing = bool(data.get("retire_missing"))
        if retire_missing and str(data.get("confirm_retire", "")).lower() != "yes":
            return _error(
                "Retiring records missing from this export is destructive. "
                "Re-send with confirm_retire='yes' to proceed.",
                BAD_REQUEST,
                requires_confirmation=True,
            )
        summary = apply_merge(
            path,
            record_type=_record_type(),
            dry_run=bool(data.get("dry_run")),
            retire_missing=retire_missing,
        )
        return jsonify(summary), OK
    finally:
        if owner is not None:
            owner.cleanup()


@st.app.route("/api/ingest/intake/capabilities", methods=["GET"])
@require_librarian
def intake_capabilities():
    """Advertise what the librarian intake helpers can do on this machine."""
    return jsonify(
        {
            "mention_lookup": "/api/ingest/mention",
            "page_image": "/api/ingest/page-image",
            "page_text": "/api/ingest/page-text",
            "spreadsheet_plan": "/api/ingest/spreadsheet/plan",
            "spreadsheet_apply": "/api/ingest/spreadsheet/apply",
            "ocr_available": ocr_available(),
            "image_formats": list(IMAGE_FORMATS),
            "sheet_formats": list(SHEET_SUFFIXES),
            "spreadsheet_outcomes": ["CREATE", "UPDATE", "UNCHANGED", "RETIRE"],
            "retire_requires_confirmation": True,
            "note": (
                "Intake never invents metadata: an unmatched mention or an unreadable "
                "page returns an explicit reason instead of a guess."
            ),
        }
    ), OK
