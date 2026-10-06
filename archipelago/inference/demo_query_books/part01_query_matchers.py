"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

from archipelago.inference.demo_query_books_data import DEMO_BOOK_ROWS

from . import _deps as _rt  # noqa: F401

_QUERY_MATCHERS: list[tuple[str, tuple[str, ...]]] = [
    ("lora_vs_bert", ("lora vs bert", "compare lora", "lora versus bert")),
    ("lora", ("low-rank adaptation", "what is lora", "lora?")),
    ("rag", ("main components of rag", "components of retrieval augmented", "components of rag")),
    ("bert", ("prerequisites for bert", "prerequisite for bert")),
    ("attention", ("attention mechanism", "how does the attention")),
    ("dbms_buffer", ("buffer pools", "silberschatz", "dbms buffer")),
    (
        "ostep_paging",
        ("paging vs segmentation", "virtual memory paging", "paging versus segmentation"),
    ),
    ("graphrag", ("graphrag", "graph + rag", "graph and rag")),
    ("peft_rank", ("rank top peft", "peft & rag", "peft and rag papers")),
    ("multi_rag_dbms", ("rag + dbms", "multi-topic: rag", "rag + dbms")),
]


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
    # Map DBMS textbook aliases to Pearson eLibrary Fundamentals of Database System, 7e
    "database_system_concepts_silberschatz": "4268f15e-ac2c-40dd-bd12-aca2f02dd0ae",
    "database_management_systems_ramakrishnan": "4268f15e-ac2c-40dd-bd12-aca2f02dd0ae",
}


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
    # Keep curated source/page metadata; circulation must come from Koha ODS.
    inventory_fields = {
        "total_copies",
        "available_copies",
        "availability",
        "is_reference",
        "shelf_location",
        "call_number",
        "library_scope",
    }
    return [{k: v for k, v in r.items() if k not in inventory_fields} for r in DEMO_BOOK_ROWS]


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
    page = int(book.get("page_number") or 1) or 1

    # Check for direct Pearson textbook match
    reader_url = str(book.get("reader_url") or book.get("url") or "")
    if "pearson.com" in reader_url:
        from archipelago.resolver.pearson import _book_only_url

        return _book_only_url(reader_url)
    try:
        from archipelago.resolver.pearson import resolve as pearson_resolve

        p_url = pearson_resolve(doc or str(book.get("book_id") or ""), page=page)
        if not p_url and book.get("book_title"):
            p_url = pearson_resolve(str(book["book_title"]), page=page)
        if p_url:
            return p_url
    except Exception:
        pass

    if not doc:
        return ""
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
            "Koha export unavailable — check the OPAC for current catalogue data."
        )
    rows = [row for row in rows if row.get("koha_record_verified")]
    if not rows:
        return ""
    try:
        from archipelago.inference.resource_kind import format_resource_kind_label
    except ImportError:  # pragma: no cover

        def format_resource_kind_label(_row: dict) -> str:  # type: ignore[misc]
            return "Catalog metadata"

    lines = [
        "",
        "### Koha catalogue matches",
        "",
        f"_{INVENTORY_DISCLAIMER}_",
        "",
        "| Catalogue title | Accession | Copies | Available | Open |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for b in rows:
        href = page_view_href(b)
        open_cell = f"[p.{int(b.get('page_number') or 1)} ↗]({href})" if href else "Passage only"
        lines.append(
            "| {title} | {accession} | {total} | {avail} | {open} |".format(
                title=str(b.get("book_title") or "—").replace("|", "/"),
                accession=str(b.get("accession") or "—").replace("|", "/"),
                total=int(b.get("total_copies") or 0),
                avail=int(b.get("available_copies") or 0),
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


_HOLDINGS_MARKER = "Koha catalogue matches"


def enrich_reply_with_books(
    query: str,
    reply: str,
    books: list[dict[str, Any]] | None = None,
) -> str:
    """Append source ranking, inline page links, and holdings table.

    Prefer explicit ``books`` (graph citations / library_books results), then
    demo-query rows. Circulation details are shown only for a Koha title match.
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
        mention = f"\n\n**Sources referenced:** **{phrase}**"
    return body + mention + format_inline_page_links(enriched) + format_availability_table(enriched)


def citation_overlays_for_query(query: str) -> list[dict[str, Any]]:
    from archipelago.inference.corpus_inventory import inventory_for_books

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
            }
        )
        inventory = inventory_for_books([b])[0]
        if inventory.get("koha_record_verified"):
            out[-1].update(
                {
                    key: inventory[key]
                    for key in (
                        "koha_record_verified",
                        "total_copies",
                        "available_copies",
                        "availability",
                        "accession",
                        "publisher",
                    )
                    if key in inventory
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
            if o_doc and (o_doc in (did, resolved) or o_doc in did or did in o_doc):
                c["title"] = o["title"]
                c["document_title"] = o["title"]
                c["source_title"] = o["title"]
                if o.get("page_url"):
                    c["page_url"] = o["page_url"]
                if o.get("summary") and not c.get("summary"):
                    c["summary"] = o["summary"]
                for field in (
                    "koha_record_verified",
                    "total_copies",
                    "available_copies",
                    "availability",
                    "accession",
                    "publisher",
                ):
                    if field in o:
                        c[field] = o[field]
                break
    seen = {str(c.get("title") or c.get("document_title") or "").strip().lower() for c in existing}
    merged = list(existing)
    for o in overlays:
        t = str(o.get("title") or "").strip().lower()
        if t and t not in seen:
            merged.insert(0, o)
            seen.add(t)
    return merged
