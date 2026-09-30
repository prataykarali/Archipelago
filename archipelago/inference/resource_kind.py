"""Human labels for catalog resource kinds (paper / textbook / reference)."""
from __future__ import annotations

from typing import Any

_KIND_LABELS = {
    "paper": "Research paper",
    "textbook": "Textbook",
    "ebook": "E-book",
    "hardcopy": "Hardcopy",
    "reference": "Reference (library use only)",
    "notes": "Library notes",
    "journal": "Journal",
}


def format_resource_kind_label(row: dict[str, Any]) -> str:
    """Return a short holdings-table label for one inventory row."""
    if row.get("is_reference"):
        return _KIND_LABELS["reference"]
    raw = str(row.get("kind") or row.get("category") or row.get("format") or "").strip().lower()
    if "paper" in raw or "arxiv" in raw or "research" in raw:
        return _KIND_LABELS["paper"]
    if "journal" in raw or "periodical" in raw:
        return _KIND_LABELS["journal"]
    if "note" in raw or "binder" in raw or "survey" in raw:
        return _KIND_LABELS["notes"]
    if "e-book" in raw or "ebook" in raw:
        return _KIND_LABELS["ebook"]
    if "textbook" in raw or "hardcover" in raw or "book" in raw:
        return _KIND_LABELS["textbook"]
    title = str(row.get("book_title") or row.get("title") or "").lower()
    doc = str(row.get("doc_id") or "").lower()
    if "paper" in doc or "/papers/" in doc or "arxiv" in title:
        return _KIND_LABELS["paper"]
    if raw:
        return raw.replace("_", " ").title()
    return "Catalog metadata"
