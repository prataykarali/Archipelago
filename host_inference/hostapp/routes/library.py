"""Library catalogue and holdings routes.

One concern: exposing the library shelf (Pearson e-books + dataset papers),
accepting an authorised librarian holdings import, and listing every catalogued
document for the UI.
"""

from __future__ import annotations

from flask import Flask, current_app, jsonify, request
from library_index import hf_title, load_hf_paths, paper_url
from library_inventory import inventory_stats, load_inventory
from remote_cache import load_books, load_library_manifest, public_book
import requests

from ..config import LIBRARIAN_ROLES
from ..context import AppContext
from ..koha_bridge import load_koha_snapshot, public_holdings
from ..research_intake_store import get_record
from ..research_library_evidence import RECORD_KEY_PATTERN, library_paper_evidence

INVENTORY_FILENAME_SUFFIX = ".csv"
PAPER_MARKER = "/papers/"
PEARSON_DOMAIN = "Pearson eLibrary"

DATASET_BOOK = {
    "author": "Library books dataset",
    "year": "",
    "isbn": "",
    "isPearson": False,
    "page_count": 1,
    "primaryColor": "#7c3aed",
    "accentColor": "#ddd6fe",
    "pdfUrl": "",
    "desc": "Opens the dataset file at the indexed page.",
}

CATALOG_AUTHOR = "Research Dataset"
CATALOG_YEAR = 2024
CATALOG_FALLBACK_AUTHORS = "Pearson Education"
CATALOG_FALLBACK_YEAR = 2024


def _dataset_domain(path: str) -> str:
    lower = path.lower()
    if PAPER_MARKER in f"/{path}" or (lower.endswith(".pdf") and "/" not in path):
        return "Paper"
    return "Textbook"


def _catalog_document_domain(title_or_path: str) -> str:
    lower = title_or_path.lower()
    if "database" in lower:
        return "dbms"
    if "operating" in lower:
        return "os"
    if "math" in lower:
        return "math"
    return "dl"


def register(app: Flask, ctx: AppContext) -> None:
    """Register library routes on ``app``."""

    @app.get("/api/library/paper-evidence/<record_key>")
    def library_paper_evidence_api(record_key: str):
        """Give signed-in readers the selected private dataset evidence row."""
        if not RECORD_KEY_PATTERN.fullmatch(record_key):
            return jsonify({"error": "invalid_record_key"}), 400
        try:
            row = get_record(record_key)
        except (requests.RequestException, RuntimeError, ValueError):
            current_app.logger.exception("Research paper lookup failed")
            return jsonify({"error": "storage_unavailable"}), 503
        if not row or row.get("kind") != "paper":
            return jsonify({"error": "not_found"}), 404
        evidence = library_paper_evidence(row)
        if evidence is None:
            return jsonify({"error": "evidence_unavailable"}), 404
        return jsonify(evidence)

    @app.get("/api/library/data")
    def library_data():
        manifest = load_library_manifest()
        opac = load_koha_snapshot()
        imported = load_inventory()
        exported = public_holdings(opac) if opac else []
        existing = manifest.get("holdings") if isinstance(manifest.get("holdings"), list) else []
        rows = imported if imported is not None else exported or existing
        holdings_status = (
            "imported"
            if imported is not None
            else "koha_export"
            if exported
            else "manifest"
            if existing
            else "unavailable"
        )
        if manifest.get("ebook_shelf"):
            manifest["holdings"] = rows
            manifest["holdings_stats"] = inventory_stats(rows)
            manifest["holdings_status"] = holdings_status
            if opac:
                manifest["opac_daily"] = opac.get("opac_daily")
                manifest["koha_source_updated_at"] = opac.get("source_updated_at")
                manifest["koha_stale"] = opac.get("stale")
            return jsonify(manifest)

        ebooks = [public_book(book) for book in load_books()]
        for path in load_hf_paths():
            item = dict(DATASET_BOOK)
            item.update(
                {
                    "id": path,
                    "title": hf_title(path),
                    "domain": _dataset_domain(path),
                    "open_url": paper_url(path, 1),
                    "reader_base_url": paper_url(path, 1),
                }
            )
            ebooks.append(item)
        return jsonify(
            {
                "ebook_shelf": ebooks,
                "ebook_stats": f"{len(ebooks)} institutional e-books · passwords are not shown",
                "holdings": rows,
                "holdings_stats": inventory_stats(rows),
                "holdings_status": holdings_status,
                "opac_daily": opac.get("opac_daily") if opac else None,
                "koha_source_updated_at": opac.get("source_updated_at") if opac else None,
                "koha_stale": opac.get("stale") if opac else None,
                "journal_issues": [],
                "subject_counts": [],
            }
        )

    @app.post("/api/library/import")
    def import_library_inventory():
        """Replace the library holdings snapshot from an authorized librarian CSV."""
        principal, _error = ctx.auth.principal()
        if principal is None or principal.get("role") not in LIBRARIAN_ROLES:
            return jsonify(
                {
                    "error": "forbidden",
                    "detail": "A librarian or administrator session is required.",
                }
            ), 403
        upload = request.files.get("file")
        if (
            upload is None
            or not upload.filename
            or not upload.filename.lower().endswith(INVENTORY_FILENAME_SUFFIX)
        ):
            return jsonify(
                {"error": "invalid_file", "detail": "Choose a CSV inventory export."}
            ), 400
        try:
            rows = ctx.inventory.parse(upload.read())
        except ValueError as exc:
            return jsonify({"error": "invalid_csv", "detail": str(exc)}), 400
        try:
            ctx.inventory.save(rows)
        except (requests.RequestException, RuntimeError):
            current_app.logger.exception("Library inventory persistence failed")
            return jsonify(
                {
                    "error": "storage_unavailable",
                    "detail": "The inventory was not saved. Supabase storage is unavailable.",
                }
            ), 503
        return jsonify({"ok": True, "holdings_stats": inventory_stats(rows)}), 200

    @app.get("/api/catalog/all")
    def catalog_all():
        docs = []
        existing = set()
        for book in load_books():
            book_id = book.get("id")
            if not book_id or book_id in existing:
                continue
            existing.add(book_id)
            title = book.get("title") or ""
            docs.append(
                {
                    "id": book_id,
                    "title": title,
                    "authors": book.get("author") or CATALOG_FALLBACK_AUTHORS,
                    "year": book.get("year", CATALOG_FALLBACK_YEAR),
                    "cat": "textbook",
                    "dom": _catalog_document_domain(title),
                    "pdf": book_id,
                    "topics": [book.get("domain")] if book.get("domain") else [PEARSON_DOMAIN],
                }
            )
        for path in load_hf_paths():
            if path in existing:
                continue
            existing.add(path)
            is_paper = PAPER_MARKER in f"/{path}" or path.lower().endswith(".pdf")
            docs.append(
                {
                    "id": path,
                    "title": hf_title(path),
                    "authors": CATALOG_AUTHOR,
                    "year": CATALOG_YEAR,
                    "cat": "paper" if is_paper else "textbook",
                    "dom": _catalog_document_domain(path),
                    "pdf": path,
                    "topics": ["Research Paper"],
                }
            )
        return jsonify({"documents": docs, "total": len(docs)})
