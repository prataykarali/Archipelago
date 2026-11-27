"""Classify and resolve citation sources across all 5 Archipelago source types.

One concern: map a graph citation ``doc_id`` to its honest source category and
verified reader/redirect target so zero broken 404 clickable links are emitted
and no Pearson/TOC/missing source masquerades as verified full-text grounding.

The five source types handled explicitly:
  A. ``oa_research_paper``         — HF-backed open-access research paper
  B. ``oa_full_text_textbook``     — HF-backed full-text open-access textbook
  C. ``toc_index_only_textbook``   — back-of-book index / TOC / front-matter stub
  D. ``pearson_catalogue_only``    — official Pearson institutional e-book (no full text)
  E. ``missing_or_unsupported_source`` — legacy/unmapped/unavailable document
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from library_index import resolve_hf_source
from remote_cache import load_books

from .access_profile import is_open_access_profile

# Canonical 5-type source categories.
SOURCE_CAT_OA_PAPER = "oa_research_paper"
SOURCE_CAT_OA_TEXTBOOK = "oa_full_text_textbook"
SOURCE_CAT_TOC_INDEX = "toc_index_only_textbook"
SOURCE_CAT_PEARSON = "pearson_catalogue_only"
SOURCE_CAT_MISSING = "missing_or_unsupported_source"

# Legacy/non-full-text back-matter / front-matter / TOC filename markers.
_TOC_INDEX_PATTERNS = (
    re.compile(r"(?:^|[/_\-])index(?:[_\-\d]|$)", re.I),
    re.compile(r"about[\-_ ]the[\-_ ]authors", re.I),
    re.compile(r"table[\-_ ]of[\-_ ]contents", re.I),
    re.compile(r"front[\-_ ]matter", re.I),
    re.compile(r"no[\-_ ]title[\-_ ]available", re.I),
    re.compile(r"(?:^|[/_\-])(?:preface|glossary|appendix)(?:[_\-\.]|$)", re.I),
)

# Exact verified slug -> Pearson title prefix overrides for legacy graph doc_ids.
_PEARSON_EXACT_ALIASES: dict[str, str] = {
    "doc_computer_networks_6_e": "computer networks, 6/e",
    "textbooks/computer_networks_tanenbaum.pdf": "computer networks, 6/e",
    "doc_compilers_principles_techniques_and_tools": "compilers principles, techniques, and tools, 2e",
    "textbooks/compilers_principles_techniques_tools_aho.pdf": "compilers principles, techniques, and tools, 2e",
    "doc_introduction_to_the_design_and": "introduction to the design and analysis of algorithms",
    "doc_digital_signal_processing_4e": "digital signal processing, 4e",
    "doc_fundamentals_of_database_system_7e": "fundamentals of database system, 7e",
    "doc_data_and_computer_communications": "data and computer communications",
    "doc_cryptography_and_network_security_principles": "cryptography and network security: principles and practice, 8/e",
    "doc_computer_system_architecture_revised_3_e": "computer system architecture, revised 3/e",
    "doc_8051_microcontroller_and_embedded_systems": "8051 microcontroller and embedded systems",
    "doc_operating_systems_internals_and_design": "operating systems: internals and design principles, global edition",
    "doc_electronic_devices_and_circuit_theory": "electronic devices and circuit theory, 11e",
}

_OA_TEXTBOOK_MARKERS = (
    "ostep",
    "deisenroth",
    "textbooks/",
    "archipelago-books-cs/",
)

MIN_SLUG_MATCH_LEN = 12


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def is_toc_or_index_doc(doc_id: str) -> bool:
    """True when ``doc_id`` names a back-of-book index, TOC, or front-matter file."""
    raw = (doc_id or "").strip()
    if not raw:
        return False
    return any(pat.search(raw) for pat in _TOC_INDEX_PATTERNS)


def match_pearson_book(raw_doc_id: str, title: str = "") -> dict[str, Any] | None:
    """Return the exact Pearson catalogue record matching ``raw_doc_id``, else ``None``."""
    raw = (raw_doc_id or "").strip()
    if not raw:
        return None
    books = load_books()
    if not books:
        return None

    low = raw.lower().lstrip("/")
    alias_title = _PEARSON_EXACT_ALIASES.get(low)
    if alias_title:
        for book in books:
            if (book.get("title") or "").strip().lower() == alias_title:
                return book

    # Direct UUID / ISBN / exact slug match.
    for book in books:
        if raw in (book.get("id") or "", book.get("isbn") or "", book.get("slug") or ""):
            return book

    # Normalized prefix match only for explicit `doc_` textbook slugs.
    if low.startswith("doc_"):
        norm_doc = _norm_key(low.removeprefix("doc_"))
        if len(norm_doc) >= MIN_SLUG_MATCH_LEN:
            for book in books:
                norm_title = _norm_key(str(book.get("title") or ""))
                if norm_title and (norm_title == norm_doc or norm_title.startswith(norm_doc)):
                    return book

    if title:
        norm_t = _norm_key(title)
        if len(norm_t) >= MIN_SLUG_MATCH_LEN:
            for book in books:
                if _norm_key(str(book.get("title") or "")) == norm_t:
                    return book
    return None


def is_hf_resolvable_doc(doc_id: str) -> bool:
    """True when ``doc_id`` resolves to a real PDF in Hugging Face datasets."""
    if not doc_id or is_toc_or_index_doc(doc_id):
        return False
    _, hf_path = resolve_hf_source(doc_id)
    return bool(hf_path)


def resolve_source_target(
    *,
    raw_doc_id: str,
    canonical_doc_id: str,
    page_number: int | None,
    title: str = "",
    all_withdrawn: bool = False,
) -> dict[str, Any]:
    """Resolve ``doc_id`` into one of the 5 source categories and a safe URL (or empty)."""
    if all_withdrawn:
        return {
            "source_category": SOURCE_CAT_MISSING,
            "source_type": "withdrawn",
            "url": "",
            "page_number": None,
            "page_verified": False,
            "reader_resolvable": False,
            "is_pearson": False,
            "book_id": "",
            "book_type": "",
            "hf_repo": "",
            "hf_path": "",
            "resolved_title": title,
            "access_status": "Withdrawn",
        }

    # Type C: TOC / back-of-book index / front-matter stub.
    if is_toc_or_index_doc(raw_doc_id) or is_toc_or_index_doc(canonical_doc_id):
        return {
            "source_category": SOURCE_CAT_TOC_INDEX,
            "source_type": "toc_index_only",
            "url": "",
            "page_number": None,
            "page_verified": False,
            "reader_resolvable": False,
            "is_pearson": False,
            "book_id": "",
            "book_type": "",
            "hf_repo": "",
            "hf_path": "",
            "resolved_title": title,
            "access_status": "TOC/index metadata only (full text not indexed)",
        }

    # Types A & B: Open-access PDF backed by Hugging Face Library_books / graphier.
    hf_repo, hf_path = resolve_hf_source(canonical_doc_id)
    if not hf_path and raw_doc_id and raw_doc_id != canonical_doc_id:
        hf_repo, hf_path = resolve_hf_source(raw_doc_id)

    if hf_path:
        valid_page = (
            int(page_number)
            if isinstance(page_number, int) and not isinstance(page_number, bool) and page_number > 0
            else None
        )
        combined = f"{canonical_doc_id} {hf_path}".lower()
        is_textbook = any(marker in combined for marker in _OA_TEXTBOOK_MARKERS)
        category = SOURCE_CAT_OA_TEXTBOOK if is_textbook else SOURCE_CAT_OA_PAPER
        target_doc = canonical_doc_id or hf_path
        url = f"/read?doc={quote(target_doc, safe='')}"
        if valid_page:
            url += f"&page={valid_page}"
        return {
            "source_category": category,
            "source_type": "ingested_pdf",
            "url": url,
            "page_number": valid_page,
            "page_verified": bool(valid_page),
            "reader_resolvable": True,
            "is_pearson": False,
            "book_id": "",
            "book_type": "pdf",
            "hf_repo": hf_repo,
            "hf_path": hf_path,
            "resolved_title": title,
            "access_status": "Available (Open Access HF Reader)",
        }

    # Type D: Official Pearson institutional catalogue-only textbook.
    # Excluded completely under the SIGIR open-access profile.
    pearson_book = (
        None
        if is_open_access_profile()
        else (match_pearson_book(raw_doc_id, title) or match_pearson_book(canonical_doc_id, title))
    )
    if pearson_book is not None:
        book_id = str(pearson_book.get("id") or "").strip()
        book_type = str(pearson_book.get("book_type") or "pdf").strip().lower()
        book_title = str(pearson_book.get("title") or title or canonical_doc_id).strip()
        return {
            "source_category": SOURCE_CAT_PEARSON,
            "source_type": "catalog_metadata",
            "url": f"/open/{book_id}" if book_id else "",
            "page_number": None,  # Never invent Pearson page numbers.
            "page_verified": False,
            "reader_resolvable": bool(book_id),
            "is_pearson": True,
            "book_id": book_id,
            "book_type": book_type,
            "hf_repo": "",
            "hf_path": "",
            "resolved_title": book_title,
            "access_status": "Pearson catalogue-only (institutional login required)",
        }

    # Type E: Missing or unsupported source — zero clickable 404 URLs.
    # Retain recorded page metadata for legacy upload_* chunks (never clickable).
    is_upload_stub = raw_doc_id.strip().lower().startswith("upload_")
    preserved_page = (
        int(page_number)
        if is_upload_stub
        and isinstance(page_number, int)
        and not isinstance(page_number, bool)
        and page_number > 0
        else None
    )
    return {
        "source_category": SOURCE_CAT_MISSING,
        "source_type": "metadata_only",
        "url": "",
        "page_number": preserved_page,
        "page_verified": False,
        "reader_resolvable": False,
        "is_pearson": False,
        "book_id": "",
        "book_type": "",
        "hf_repo": "",
        "hf_path": "",
        "resolved_title": title,
        "access_status": "Unavailable",
    }


__all__ = [
    "SOURCE_CAT_MISSING",
    "SOURCE_CAT_OA_PAPER",
    "SOURCE_CAT_OA_TEXTBOOK",
    "SOURCE_CAT_PEARSON",
    "SOURCE_CAT_TOC_INDEX",
    "is_hf_resolvable_doc",
    "is_toc_or_index_doc",
    "match_pearson_book",
    "resolve_source_target",
]
