"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from . import _deps as _rt  # noqa: F401


def demo_passage_for_doc(doc_id: str, page: int = 1, highlight: str = "") -> dict[str, Any] | None:
    """Lookup hardcoded summary for page-view when graph has no chunk.

    Only matches by document id / alias — never by highlight alone (that would
    hijack unknown docs like paper.pdf into an unrelated booth summary).
    """
    raw = (doc_id or "").strip()
    if not raw:
        return None
    resolved = _rt.resolve_doc_id(raw)
    # Bare unknown filenames (paper.pdf) that do not alias → no demo hit
    if raw == resolved or (not resolved and "/" not in raw):
        # Still allow exact book_id / known alias keys
        low = raw.lower().replace("\\", "/")
        alias_hit = low in {k.lower() for k in _rt.DOC_ID_ALIASES} or any(
            low == str(r.get("book_id") or "").lower()
            or low == str(r.get("doc_id") or "").lower().replace("\\", "/")
            or low.endswith("/" + str(Path(str(r.get("doc_id") or "")).name).lower())
            for r in _rt._ROWS
        )
        if not alias_hit and not (resolved and (_rt._PDF_ROOT / resolved).is_file()):
            # If resolve left path unchanged and file missing → not a demo doc
            if not resolved or not (_rt._PDF_ROOT / resolved).is_file():
                if low not in {k.lower() for k in _rt.DOC_ID_ALIASES}:
                    if not any(low == str(r.get("book_id") or "").lower() for r in _rt._ROWS):
                        if "/" not in raw and raw.lower().endswith(".pdf"):
                            # unknown bare pdf stem
                            known = (
                                "lora", "bert", "rag", "lewis", "hu2021", "devlin",
                                "vaswani", "edge", "attention", "qlora", "dettmers",
                            )
                            if not any(k in low for k in known):
                                return None

    targets = {raw, resolved}
    if resolved:
        targets.add(Path(resolved).name)
    targets = {t for t in targets if t}
    targets_l = {t.lower().replace("\\", "/") for t in targets}

    for row in _rt._ROWS:
        rdoc = _rt.resolve_doc_id(str(row.get("doc_id") or row.get("book_id") or ""))
        rid = str(row.get("book_id") or "")
        candidates = {rdoc, rid, Path(rdoc).name if rdoc else ""}
        candidates_l = {c.lower().replace("\\", "/") for c in candidates if c}
        if targets_l & candidates_l:
            return {
                "doc_id": rdoc or rid,
                "page": int(row.get("page_number") or page or 1),
                "highlight": highlight or str(row.get("topic") or ""),
                "passage": str(row.get("summary") or ""),
                "text": str(row.get("summary") or ""),
                "title": str(row.get("book_title") or ""),
                "authors": str(row.get("authors") or ""),
                "section_title": str(row.get("topic") or ""),
            }
    return None
