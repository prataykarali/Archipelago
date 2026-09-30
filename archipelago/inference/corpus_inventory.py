"""Join cited resources to the latest local Koha holdings export when possible."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any

INVENTORY_DISCLAIMER = "Koha export snapshot — check the OPAC for live circulation status."

DEFAULT_PAGE = 1
MAX_INVENTORY_ROWS = 6

# Catalog knowledge keys / aliases → path under pdfs/ (empty = metadata only).
CATALOG_DOC_IDS: dict[str, str] = {
    "attention_is_all_you_need": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "vaswani2017_attention": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "deep_learning_goodfellow": "",
    "operating_systems_three_easy_pieces": "ostep_three_easy_pieces/08_Paging.pdf",
    "ostep_three_easy_pieces": "ostep_three_easy_pieces/08_Paging.pdf",
    "database_system_concepts": "",
    "database_system_concepts_silberschatz": "",
    "lora_paper": "papers/Hu2021_LoRA.pdf",
    "hu2021_lora": "papers/Hu2021_LoRA.pdf",
    "bert_paper": "papers/Devlin2018_BERT.pdf",
    "devlin2018_bert": "papers/Devlin2018_BERT.pdf",
    "math_for_ml": "Deisenroth_Math_For_ML.pdf",
    "rag_paper": "papers/Lewis2020_RAG.pdf",
    "lewis2020_rag": "papers/Lewis2020_RAG.pdf",
    "graphrag_ms": "papers/Edge2024_GraphRAG.pdf",
    "peft_survey": "papers/Hu2021_LoRA.pdf",
}

def _populate_pearson_inventory():
    import json
    from pathlib import Path
    try:
        repo_root = Path(__file__).resolve().parents[2]
        cat_file = repo_root / "data" / "catalogs" / "pearson_bookshelf.json"
        if not cat_file.is_file():
            return
        with cat_file.open(encoding="utf-8") as f:
            books = json.load(f).get("books", [])
        for b in books:
            b_id = b.get("id", "")
            slug = b.get("slug") or b_id
            reader_url = b.get("reader_base_url") or ""
            CATALOG_DOC_IDS[slug] = reader_url
            CATALOG_DOC_IDS[b_id] = reader_url
            if b.get("title"):
                import re
                doc_k = f"doc_{re.sub(r'[^a-z0-9]+', '_', b['title'].lower()).strip('_')}"
                CATALOG_DOC_IDS[doc_k] = reader_url
    except Exception:
        pass

_populate_pearson_inventory()

_BASENAME_TO_KEY = {
    "hu2021_lora.pdf": "hu2021_lora",
    "devlin2018_bert.pdf": "devlin2018_bert",
    "vaswani2017_attention_is_all_you_need.pdf": "vaswani2017_attention",
    "lewis2020_rag.pdf": "lewis2020_rag",
    "edge2024_graphrag.pdf": "graphrag_ms",
    "08_paging.pdf": "ostep_three_easy_pieces",
    "deisenroth_math_for_ml.pdf": "math_for_ml",
}

def _stock_key(book: dict[str, Any]) -> str:
    for field in ("book_id", "id", "dirname"):
        raw = str(book.get(field) or "").strip().lower()
        if raw in CATALOG_DOC_IDS:
            return raw
    doc = str(book.get("doc_id") or "").replace("\\", "/").strip().lower()
    base = doc.rsplit("/", 1)[-1]
    if base in _BASENAME_TO_KEY:
        return _BASENAME_TO_KEY[base]
    title = str(book.get("book_title") or book.get("title") or "").lower()
    if "lora" in title:
        return "hu2021_lora"
    if "bert" in title:
        return "devlin2018_bert"
    if "attention is all you need" in title or "vaswani" in title:
        return "vaswani2017_attention"
    if "retrieval-augmented" in title or title.startswith("rag"):
        return "lewis2020_rag"
    if "graphrag" in title:
        return "graphrag_ms"
    if "three easy pieces" in title or "ostep" in title:
        return "ostep_three_easy_pieces"
    if "mathematics for machine" in title or "deisenroth" in title:
        return "math_for_ml"
    if "database system concepts" in title:
        return "database_system_concepts_silberschatz"
    if "deep learning" in title and "goodfellow" in title:
        return "deep_learning_goodfellow"
    return ""


def default_core_inventory() -> list[dict[str, Any]]:
    """There is no safe default shelf: holdings must come from catalog data."""
    return []


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


@lru_cache(maxsize=1)
def _koha_holdings() -> dict[str, dict[str, Any]]:
    """Read actual copy counts/accessions from the locally supplied Koha ODS."""
    filename = "Titles List with specified keyword-reportresults.ods"
    repo = Path(__file__).resolve().parents[2]
    path = next((p for p in (
        repo / "data" / "koha" / filename,
        repo.parent / "data" / "koha" / filename,
        repo / filename,
    ) if p.is_file()), None)
    if path is None:
        return {}
    from archipelago.inference.library_catalog_api import parse_ods_rows

    rows = parse_ods_rows(path)
    result: dict[str, dict[str, Any]] = {}
    for values in rows[1:]:
        if len(values) < 7:
            continue
        title = str(values[1] or "").strip()
        key = _normalize_title(title)
        if not key:
            continue
        try:
            total, available = int(values[5] or 0), int(values[6] or 0)
        except (TypeError, ValueError):
            continue
        record = result.setdefault(key, {
            "book_title": title,
            "authors": str(values[2] or "").strip(),
            "publisher": str(values[3] or "").strip(),
            "accession": "",
            "total_copies": 0,
            "available_copies": 0,
            "koha_record_verified": True,
            "inventory_source": path.name,
        })
        record["total_copies"] += total
        record["available_copies"] += available
        accession = str(values[4] or "").strip()
        known_accessions = [part.strip() for part in record["accession"].split(",") if part.strip()]
        if accession and accession not in known_accessions:
            known_accessions.append(accession)
        record["accession"] = ", ".join(known_accessions)
    for record in result.values():
        record["availability"] = (
            f"{record['available_copies']} of {record['total_copies']} copies available in Koha export"
        )
    return result


def inventory_for_books(books: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach circulation fields only when the exact title exists in Koha ODS."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for book in books:
        row = dict(book)
        key = _stock_key(row)
        title = str(row.get("book_title") or row.get("title") or row.get("document_title") or "").strip()
        stock = _koha_holdings().get(_normalize_title(title), {})
        if not row.get("doc_id"):
            row["doc_id"] = CATALOG_DOC_IDS.get(key, "") or row.get("doc_id") or ""
        if not row.get("book_title"):
            row["book_title"] = (
                row.get("title")
                or row.get("document_title")
                or "Library source"
            )
        if not row.get("authors"):
            row["authors"] = stock.get("authors") or row.get("authors") or ""
        for field in ("total_copies", "available_copies", "availability", "accession", "publisher"):
            row.pop(field, None)
        if stock:
            row.update(stock)
        if not row.get("page_number"):
            row["page_number"] = int(row.get("page") or DEFAULT_PAGE)
        if not row.get("book_id"):
            row["book_id"] = key or str(row.get("doc_id") or row["book_title"])
        dedupe = str(row.get("book_title") or row.get("doc_id") or "").strip().lower()
        if dedupe and dedupe in seen:
            continue
        if dedupe:
            seen.add(dedupe)
        out.append(row)
        if len(out) >= MAX_INVENTORY_ROWS:
            break
    return out


def books_from_citations(citations: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Turn graph citation payloads into inventory rows with page numbers."""
    rows: list[dict[str, Any]] = []
    for cite in citations or []:
        doc = str(cite.get("doc_id") or cite.get("document_id") or "").strip()
        title = str(
            cite.get("title")
            or cite.get("document_title")
            or cite.get("source_title")
            or doc
            or "Source"
        )
        page = cite.get("page_number") or cite.get("page") or DEFAULT_PAGE
        try:
            page_n = int(page)
        except (TypeError, ValueError):
            page_n = DEFAULT_PAGE
        if page_n < 1:
            page_n = DEFAULT_PAGE
        rows.append(
            {
                "book_id": doc or title,
                "doc_id": doc,
                "book_title": title,
                "authors": cite.get("authors") or "",
                "shelf_location": cite.get("shelf_location") or "",
                "call_number": cite.get("call_number") or "",
                "library_scope": cite.get("library_scope") or "",
                "total_copies": cite.get("total_copies"),
                "available_copies": cite.get("available_copies"),
                "is_reference": cite.get("is_reference"),
                "availability": cite.get("availability") or "",
                "page_number": page_n,
                "topic": cite.get("topic") or cite.get("section_title") or "",
                "summary": cite.get("text_span") or cite.get("summary") or "",
            }
        )
    return inventory_for_books(rows)


def books_from_catalog_meta(meta: dict[str, Any] | None) -> list[dict[str, Any]]:
    """One inventory row from curated library-book metadata."""
    if not meta:
        return []
    title = str(meta.get("title") or "")
    key = _stock_key({"book_title": title, "book_id": meta.get("id") or ""})
    doc = str(meta.get("doc_id") or CATALOG_DOC_IDS.get(key, "") or "")
    r_url = meta.get("reader_url") or meta.get("pdf_path") or ""
    is_p = bool(meta.get("is_pearson") or ("pearson" in str(r_url).lower()))
    return inventory_for_books(
        [
            {
                "book_id": key or title,
                "doc_id": doc,
                "book_title": title,
                "authors": meta.get("authors") or "",
                "total_copies": meta.get("total_copies"),
                "available_copies": meta.get("available_copies"),
                "shelf_location": meta.get("shelf_location") or "",
                "call_number": meta.get("call_number") or "",
                "library_scope": meta.get("library_scope") or "",
                "page_number": DEFAULT_PAGE,
                "topic": (meta.get("key_sections") or [""])[0],
                "is_reference": "reference" in str(meta.get("format") or "").lower(),
                "is_pearson": is_p,
                "reader_url": r_url,
                "url": r_url,
            }
        ]
    )
