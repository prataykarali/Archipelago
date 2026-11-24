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

from ..config import LIBRARIAN_ROLES, MAX_CONTENT_LENGTH_BYTES
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

CATALOG_AUTHOR = "Open Access (HF Library_books)"
CATALOG_YEAR = 2024
CATALOG_FALLBACK_AUTHORS = "Pearson Education"
CATALOG_FALLBACK_YEAR = 2024

CANONICAL_DOMAINS: tuple[tuple[str, str], ...] = (
    ("os", "Operating Systems"),
    ("dbms", "Database Systems"),
    ("dsa", "Data Structures & Algorithms"),
    ("net", "Computer Networks"),
    ("cmp", "Compilers & Languages"),
    ("aut", "Automata & Computation"),
    ("math", "Mathematics for Computing"),
    ("prob", "Probability & Statistics"),
    ("sec", "Information Security"),
    ("ai", "AI & Machine Learning"),
    ("se", "Software Engineering"),
    ("coa", "Computer Architecture"),
)
_DOMAIN_LABELS: dict[str, str] = dict(CANONICAL_DOMAINS)


def _dataset_domain(path: str) -> str:
    lower = path.lower()
    if PAPER_MARKER in f"/{path}" or (
        lower.endswith(".pdf") and "ostep" not in lower and "deisenroth" not in lower and "textbooks/" not in lower
    ):
        return "Paper"
    return "Textbook"


def _catalog_document_domain(title_or_path: str, domain_hint: str = "") -> str:
    """Map any library document onto one of the 12 canonical CS/AI domains."""
    title_low = (title_or_path or "").lower()
    combined = f"{title_low} {(domain_hint or '').lower()}"
    if any(k in title_low for k in ("ostep", "operating system", "paging", "virtual memory")):
        return "os"
    if any(k in title_low for k in ("database", "dbms", "sql", "web technology", "web development", "html5")):
        return "dbms"
    if any(k in title_low for k in ("algorithm", "data structure", "programming in c")):
        return "dsa"
    if any(k in title_low for k in ("cryptography", "network security", "constitutionalai")):
        return "sec"
    if any(k in title_low for k in ("computer networks", "computer communications", "wireless", "iot fundamentals")):
        return "net"
    if any(k in title_low for k in ("compiler", "outlines", "willard2023")):
        return "cmp"
    if any(k in combined for k in ("automata", "formal language", "turing")):
        return "aut"
    if any(k in title_low for k in ("probability", "statistics", "kingma2013", "ho2020")):
        return "prob"
    if any(k in title_low for k in ("deisenroth", "math", "signal processing", "image processing", "quantitative")):
        return "math"
    if any(k in title_low for k in ("software engineering", "computer fundamentals", "objective english", "general knowledge")):
        return "se"
    if any(
        k in title_low
        for k in (
            "computer system architecture",
            "computer organization",
            "digital logic",
            "digital design",
            "microcontroller",
            "electronic devices",
            "electrical engineering",
            "op-amps",
        )
    ):
        return "coa"
    return "ai"


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
        resp = jsonify(evidence)
        resp.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
        resp.headers["Vary"] = "Authorization, Cookie"
        return resp

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
            placeholder_titles = {
                "Chapter 1: Foundations & Architecture",
                "Chapter 2: Core Concepts & Practice",
                "Chapter 3: Advanced Topics",
            }
            for item in manifest["ebook_shelf"]:
                if isinstance(item, dict) and isinstance(item.get("toc"), list):
                    titles = {str(t.get("title") or "") for t in item["toc"] if isinstance(t, dict)}
                    if titles and titles.issubset(placeholder_titles):
                        item["toc"] = [{"title": "TOC not indexed (catalogue-only metadata)", "page": None}]
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
        raw_bytes = upload.read(MAX_CONTENT_LENGTH_BYTES + 1)
        if len(raw_bytes) > MAX_CONTENT_LENGTH_BYTES:
            return jsonify(
                {"error": "file_too_large", "detail": "CSV file exceeds maximum size limit."}
            ), 413
        try:
            rows = ctx.inventory.parse(raw_bytes)
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
            dom_key = _catalog_document_domain(title, str(book.get("domain") or ""))
            book_type = str(book.get("book_type") or "pdf").strip().lower()
            docs.append(
                {
                    "id": book_id,
                    "book_id": book_id,
                    "isbn": book.get("isbn") or "",
                    "title": title,
                    "authors": book.get("author") or CATALOG_FALLBACK_AUTHORS,
                    "year": book.get("year", CATALOG_FALLBACK_YEAR),
                    "cat": "textbook",
                    "dom": dom_key,
                    "dom_label": _DOMAIN_LABELS.get(dom_key, "AI & Machine Learning"),
                    "collection": "library_pearson",
                    "is_pearson": True,
                    "book_type": book_type,
                    "page_verified": False,
                    "source_category": "pearson_catalogue_only",
                    "open_url": f"/open/{book_id}",
                    "pdf": "",
                    "topics": [book.get("domain")] if book.get("domain") else [PEARSON_DOMAIN],
                }
            )
        seen_hf_basenames: set[str] = set()
        # Prefer canonical structured paths (`books/papers/...`, `books/textbooks/...`, `archipelago-books-cs/...`)
        # over bare root mirror copies so each open-access source appears cleanly once.
        hf_paths_sorted = sorted(
            load_hf_paths(),
            key=lambda p: (0 if "/" in p else 1, p.lower()),
        )
        for path in hf_paths_sorted:
            if "librarian_uploads/" in path.lower():
                continue
            base = path.rsplit("/", 1)[-1].lower()
            if path in existing or base in seen_hf_basenames:
                continue
            existing.add(path)
            seen_hf_basenames.add(base)
            is_textbook = (
                "ostep" in path.lower()
                or "deisenroth" in path.lower()
                or "textbooks/" in path.lower()
            )
            dom_key = _catalog_document_domain(path)
            docs.append(
                {
                    "id": path,
                    "title": hf_title(path),
                    "authors": CATALOG_AUTHOR,
                    "year": CATALOG_YEAR,
                    "cat": "textbook" if is_textbook else "paper",
                    "dom": dom_key,
                    "dom_label": _DOMAIN_LABELS.get(dom_key, "AI & Machine Learning"),
                    "collection": "open_source",
                    "is_pearson": False,
                    "book_type": "pdf",
                    "page_verified": False,
                    "source_category": (
                        "oa_full_text_textbook" if is_textbook else "oa_research_paper"
                    ),
                    "open_url": paper_url(path, None),
                    "pdf": path,
                    "topics": ["Open Textbook" if is_textbook else "Open Research Paper"],
                }
            )
        domain_counts = {key: 0 for key, _ in CANONICAL_DOMAINS}
        for d in docs:
            dk = d.get("dom") or "ai"
            if dk in domain_counts:
                domain_counts[dk] += 1
        domains_summary = [
            {"key": key, "label": label, "count": domain_counts[key]}
            for key, label in CANONICAL_DOMAINS
        ]
        return jsonify({"documents": docs, "total": len(docs), "domains": domains_summary})
