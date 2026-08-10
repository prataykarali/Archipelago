"""Hardcoded demo-query book stack + availability + page links.

Spreadsheet: docs/demo_query_books.csv
doc_id values must match files under pdfs/ so Page/Split modes open real PDFs.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

_QUERY_MATCHERS: list[tuple[str, tuple[str, ...]]] = [
    ("lora_vs_bert", ("lora vs bert", "compare lora", "lora versus bert")),
    ("lora", ("low-rank adaptation", "what is lora", "lora?")),
    ("rag", ("main components of rag", "components of retrieval augmented", "components of rag")),
    ("bert", ("prerequisites for bert", "prerequisite for bert")),
    ("attention", ("attention mechanism", "how does the attention")),
    ("dbms_buffer", ("buffer pools", "silberschatz", "dbms buffer")),
    ("ostep_paging", ("paging vs segmentation", "virtual memory paging", "paging versus segmentation")),
    ("graphrag", ("graphrag", "graph + rag", "graph and rag")),
    ("peft_rank", ("rank top peft", "peft & rag", "peft and rag papers")),
    ("multi_rag_dbms", ("rag + dbms", "multi-topic: rag", "rag + dbms")),
]

# Aliases: booth / inventory ids → real corpus paths under pdfs/
DOC_ID_ALIASES: dict[str, str] = {
    "lewis2020_rag": "papers/Lewis2020_RAG.pdf",
    "hu2021_lora": "papers/Hu2021_LoRA.pdf",
    "devlin2018_bert": "papers/Devlin2018_BERT.pdf",
    "vaswani2017_attention": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "graphrag_ms": "papers/Edge2024_GraphRAG.pdf",
    "peft_survey": "papers/Hu2021_LoRA.pdf",
    "ostep_three_easy_pieces": "ostep_three_easy_pieces/08_Paging.pdf",
    "ostep_paging": "ostep_three_easy_pieces/08_Paging.pdf",
    "operating_system_concepts_silberschatz": "ostep_three_easy_pieces/08_Paging.pdf",
    # No full Silberschatz DBMS PDF in pilot — use OSTEP I/O chapter as related systems text
    # only when no better file exists; prefer summary-only for pure DBMS rows.
    "database_system_concepts_silberschatz": "",
    "database_management_systems_ramakrishnan": "",
}

from archipelago.inference.demo_query_books_data import DEMO_BOOK_ROWS

_CSV_PATH = Path(__file__).resolve().parents[2] / "docs" / "demo_query_books.csv"
_PDF_ROOT = Path(__file__).resolve().parents[2] / "pdfs"


def resolve_doc_id(doc_id: str) -> str:
    """Map alias / bare id to a path under pdfs/ when possible."""
    raw = (doc_id or "").strip().lstrip("/")
    if raw.startswith("pdfs/"):
        raw = raw[5:]
    if not raw:
        return ""
    if raw in DOC_ID_ALIASES:
        mapped = DOC_ID_ALIASES[raw]
        return mapped or ""
    low = raw.lower()
    for alias, target in DOC_ID_ALIASES.items():
        if alias.lower() == low or alias.lower() in low.replace("\\", "/"):
            return target or raw
    # bare filename → papers/
    if "/" not in raw and raw.lower().endswith(".pdf"):
        candidate = f"papers/{raw}"
        if (_PDF_ROOT / candidate).exists():
            return candidate
    return raw


def _coerce_row(raw: dict[str, str]) -> dict[str, Any]:
    ref = str(raw.get("is_reference", "")).strip().lower() in {"1", "true", "yes", "y"}
    doc = str(raw.get("doc_id") or raw.get("book_id") or "").strip()
    doc = resolve_doc_id(doc) if doc else ""
    return {
        "query_key": str(raw.get("query_key", "")).strip(),
        "book_id": str(raw.get("book_id", "")).strip(),
        "doc_id": doc,
        "book_title": str(raw.get("book_title", "")).strip(),
        "authors": str(raw.get("authors", "")).strip(),
        "total_copies": int(raw.get("total_copies") or 0),
        "available_copies": int(raw.get("available_copies") or 0),
        "availability": str(raw.get("availability", "")).strip() or "Unknown",
        "is_reference": ref,
        "shelf_location": str(raw.get("shelf_location", "")).strip(),
        "page_number": int(raw.get("page_number") or 1),
        "topic": str(raw.get("topic", "")).strip(),
        "summary": str(raw.get("summary", "")).strip(),
    }


def _load_rows() -> list[dict[str, Any]]:
    # Prefer in-module DEMO_BOOK_ROWS (authoritative for booth); CSV is export.
    return [dict(r) for r in DEMO_BOOK_ROWS]


_ROWS: list[dict[str, Any]] = _load_rows()


def match_demo_query_key(query: str) -> str | None:
    q = re.sub(r"\s+", " ", (query or "").strip().lower())
    if not q:
        return None
    for key, needles in _QUERY_MATCHERS:
        if any(n in q for n in needles):
            return key
    return None


def books_for_query(query: str) -> list[dict[str, Any]]:
    key = match_demo_query_key(query)
    if not key:
        return []
    return [dict(r) for r in _ROWS if r["query_key"] == key]


def book_titles_phrase(books: list[dict[str, Any]]) -> str:
    titles = [str(b.get("book_title") or "").strip() for b in books if b.get("book_title")]
    titles = [t for t in titles if t]
    if not titles:
        return ""
    if len(titles) == 1:
        return titles[0]
    if len(titles) == 2:
        return f"{titles[0]} and {titles[1]}"
    return ", ".join(titles[:-1]) + f", and {titles[-1]}"


def page_view_href(book: dict[str, Any]) -> str:
    """Open-page URL for the named doc — empty string when the file is absent
    so the caller can fall back to a Pearson/OPAC CTA instead of a 404 link."""
    doc = resolve_doc_id(str(book.get("doc_id") or book.get("book_id") or ""))
    if not doc:
        return ""
    # Guard: only emit a page-view URL when the underlying file actually exists.
    # doc_id may be a Pearson alias or a metadata-only id for a title we don't
    # have on disk — producing a /page-view URL then would send users to a 404.
    if not (_PDF_ROOT / doc).is_file():
        return ""
    page = int(book.get("page_number") or 1) or 1
    topic = str(book.get("topic") or "").strip()
    q = f"/api/page-view?doc_id={quote(doc, safe='')}&page={page}"
    if topic:
        q += f"&highlight={quote(topic[:120], safe='')}"
    return f"{q}#page={page}"


def format_availability_table(books: list[dict[str, Any]]) -> str:
    if not books:
        return ""
    # Fill missing inventory columns from the full corpus table.
    try:
        from archipelago.inference.corpus_inventory import (
            INVENTORY_DISCLAIMER,
            inventory_for_books,
        )
        rows = inventory_for_books(books)
    except Exception:
        rows = books
        INVENTORY_DISCLAIMER = (
            "⚠️ Simulated inventory — check OPAC for live availability"
        )
    if not rows:
        return ""
    try:
        from archipelago.inference.resource_kind import format_resource_kind_label
    except ImportError:  # pragma: no cover
        def format_resource_kind_label(_row: dict) -> str:  # type: ignore[misc]
            return "Catalog metadata"

    lines = [
        "",
        "### Library holdings for this topic",
        "",
        f"_{INVENTORY_DISCLAIMER}_",
        "",
        "| Book | Type | Page | Copies | Available | Reference? | Status | Shelf | Open |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for b in rows:
        ref = "Yes (library use only)" if b.get("is_reference") else "No (circulating)"
        href = page_view_href(b)
        open_cell = f"[p.{int(b.get('page_number') or 1)} ↗]({href})" if href else "Passage only"
        kind_label = format_resource_kind_label(b).replace("|", "/")
        lines.append(
            "| {title} | {kind} | {page} | {total} | {avail} | {ref} | {status} | {shelf} | {open} |".format(
                title=str(b.get("book_title") or "—").replace("|", "/"),
                kind=kind_label,
                page=int(b.get("page_number") or 1),
                total=int(b.get("total_copies") or 0),
                avail=int(b.get("available_copies") or 0),
                ref=ref,
                status=str(b.get("availability") or "—").replace("|", "/"),
                shelf=str(b.get("shelf_location") or "—").replace("|", "/"),
                open=open_cell,
            )
        )
    lines.append("")
    return "\n".join(lines)


def format_inline_page_links(books: list[dict[str, Any]]) -> str:
    chips: list[str] = []
    for b in books:
        href = page_view_href(b)
        title = str(b.get("book_title") or "Source").strip()
        short = title if len(title) <= 42 else title[:40] + "…"
        page = int(b.get("page_number") or 1) or 1
        if href:
            chips.append(f"[📄 {short} · p.{page} ↗]({href})")
        else:
            chips.append(f"📄 {short} (reference summary — no pilot PDF)")
    if not chips:
        return ""
    return "\n\n**Open source pages:** " + " · ".join(chips) + "\n"


_HOLDINGS_MARKER = "Library holdings for this topic"


def enrich_reply_with_books(
    query: str,
    reply: str,
    books: list[dict[str, Any]] | None = None,
) -> str:
    """Append source ranking, inline page links, and holdings table.

    Prefer explicit ``books`` (graph citations / library_books results), then
    demo-query rows, then corpus inventory enrichment of whatever was found.
    """
    body = (reply or "").rstrip()
    if _HOLDINGS_MARKER in body:
        return body

    resolved = list(books) if books else books_for_query(query)
    if not resolved:
        return body

    try:
        from archipelago.inference.corpus_inventory import inventory_for_books
        enriched = inventory_for_books(resolved)
    except Exception:
        enriched = resolved
    if not enriched:
        return body

    phrase = book_titles_phrase(enriched)
    mention = ""
    if phrase:
        mention = (
            f"\n\n**Sources on the shelf:** This answer draws on **{phrase}** "
            f"from the library stack for this topic."
        )
    return (
        body
        + mention
        + format_inline_page_links(enriched)
        + format_availability_table(enriched)
    )


def citation_overlays_for_query(query: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, b in enumerate(books_for_query(query), start=1):
        doc = resolve_doc_id(str(b.get("doc_id") or b.get("book_id") or ""))
        page = int(b.get("page_number") or 1) or 1
        topic = str(b.get("topic") or "")
        title = str(b.get("book_title") or "Library book")
        href = page_view_href(b)
        out.append(
            {
                "evidence_id": f"B{i}",
                "doc_id": doc or str(b.get("book_id") or f"demo_book_{i}"),
                "title": title,
                "document_title": title,
                "source_title": title,
                "authors": b.get("authors") or "",
                "page_number": page,
                "topic": topic,
                "section_title": topic,
                "summary": b.get("summary") or "",
                "passage": b.get("summary") or "",
                "page_url": href,
                "url": href,
                "pdf": f"{doc}#page={page}" if doc else "",
                "is_reference": bool(b.get("is_reference")),
                "availability": b.get("availability") or "",
                "total_copies": int(b.get("total_copies") or 0),
                "available_copies": int(b.get("available_copies") or 0),
                "shelf_location": b.get("shelf_location") or "",
            }
        )
    return out


def merge_demo_citations(
    query: str,
    citations: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    overlays = citation_overlays_for_query(query)
    if not overlays:
        return list(citations or [])
    existing = list(citations or [])
    for c in existing:
        did = str(c.get("doc_id") or c.get("document_id") or c.get("source_id") or "")
        resolved = resolve_doc_id(did)
        if resolved:
            c["doc_id"] = resolved
        for o in overlays:
            o_doc = str(o.get("doc_id") or "")
            if o_doc and (o_doc == did or o_doc == resolved or o_doc in did or did in o_doc):
                c["title"] = o["title"]
                c["document_title"] = o["title"]
                c["source_title"] = o["title"]
                if o.get("page_url"):
                    c["page_url"] = o["page_url"]
                if o.get("summary") and not c.get("summary"):
                    c["summary"] = o["summary"]
                break
    seen = {
        str(c.get("title") or c.get("document_title") or "").strip().lower()
        for c in existing
    }
    merged = list(existing)
    for o in overlays:
        t = str(o.get("title") or "").strip().lower()
        if t and t not in seen:
            merged.insert(0, o)
            seen.add(t)
    return merged


def demo_passage_for_doc(doc_id: str, page: int = 1, highlight: str = "") -> dict[str, Any] | None:
    """Lookup hardcoded summary for page-view when graph has no chunk.

    Only matches by document id / alias — never by highlight alone (that would
    hijack unknown docs like paper.pdf into an unrelated booth summary).
    """
    raw = (doc_id or "").strip()
    if not raw:
        return None
    resolved = resolve_doc_id(raw)
    # Bare unknown filenames (paper.pdf) that do not alias → no demo hit
    if raw == resolved or (not resolved and "/" not in raw):
        # Still allow exact book_id / known alias keys
        low = raw.lower().replace("\\", "/")
        alias_hit = low in {k.lower() for k in DOC_ID_ALIASES} or any(
            low == str(r.get("book_id") or "").lower()
            or low == str(r.get("doc_id") or "").lower().replace("\\", "/")
            or low.endswith("/" + str(Path(str(r.get("doc_id") or "")).name).lower())
            for r in _ROWS
        )
        if not alias_hit and not (resolved and (_PDF_ROOT / resolved).is_file()):
            # If resolve left path unchanged and file missing → not a demo doc
            if not resolved or not (_PDF_ROOT / resolved).is_file():
                if low not in {k.lower() for k in DOC_ID_ALIASES}:
                    if not any(low == str(r.get("book_id") or "").lower() for r in _ROWS):
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

    for row in _ROWS:
        rdoc = resolve_doc_id(str(row.get("doc_id") or row.get("book_id") or ""))
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
