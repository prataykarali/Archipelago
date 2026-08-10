"""Jul 21 institutional catalog — ODS reports + book METADATA (no full book body)."""
from __future__ import annotations

import json
import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BOOKS = ROOT / "pdfs" / "archipelago-books-cs"
INVENTORY = DOCS / "library_book_inventory.csv"


@lru_cache(maxsize=1)
def load_book_inventory() -> dict[str, dict[str, Any]]:
    """Load circulation fields from the maintained inventory spreadsheet."""
    if not INVENTORY.exists():
        return {}
    with INVENTORY.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        return {str(row.get("book_id") or ""): dict(row) for row in rows}


@lru_cache(maxsize=1)
def load_ods_index() -> dict[str, Any]:
    from archipelago.inference.ods_parser import read_ods_sheet, sniff_schema

    out: dict[str, Any] = {"subjects": [], "journals": [], "titles": [], "errors": []}
    if not DOCS.exists():
        return out
    for path in sorted(DOCS.glob("*.ods")):
        try:
            rows = read_ods_sheet(str(path))
            if not rows or len(rows) < 2:
                continue
            kind = sniff_schema(rows) or "unknown"
            header = [str(h).strip() for h in rows[0]]
            body = rows[1:]
            if kind == "subject_report" or "subject" in path.name.lower():
                for r in body:
                    if not r:
                        continue
                    subj = str(r[0]).strip() if len(r) > 0 else ""
                    cnt = str(r[1]).strip() if len(r) > 1 else ""
                    # Drop KOHA junk / header echoes
                    if not subj or len(subj) < 3:
                        continue
                    if subj.lower() in ("subject", "department", "heading"):
                        continue
                    if "heading usage" in subj.lower() or "fast id" in subj.lower():
                        continue
                    if not any(ch.isalpha() for ch in subj):
                        continue
                    out["subjects"].append(
                        {
                            "subject": subj[:120],
                            "title_count": cnt,
                            "source": path.name,
                        }
                    )
            elif kind == "journal_report" or "journal" in path.name.lower():
                for r in body:
                    if not r:
                        continue
                    out["journals"].append(
                        {
                            "title": str(r[0]).strip() if len(r) > 0 else "",
                            "extra": [str(x) for x in r[1:4]],
                            "source": path.name,
                        }
                    )
            else:
                # keyword / titles list
                # expect Title at col 1 often
                for r in body:
                    if len(r) < 2:
                        continue
                    title = str(r[1] if "title" in header[1].lower() else r[0]).strip()
                    author = str(r[2]).strip() if len(r) > 2 else ""
                    copies = str(r[6]).strip() if len(r) > 6 else (str(r[5]).strip() if len(r) > 5 else "")
                    out["titles"].append(
                        {
                            "title": title,
                            "author": author,
                            "available": copies,
                            "source": path.name,
                        }
                    )
        except Exception as exc:
            out["errors"].append(f"{path.name}: {exc}")
    return out


@lru_cache(maxsize=1)
def load_book_shelf() -> list[dict[str, Any]]:
    """Pilot books from METADATA.json only (Jul 21 — no body)."""
    books: list[dict[str, Any]] = []
    inventory = load_book_inventory()
    if not BOOKS.exists():
        return books
    for meta_path in BOOKS.glob("*/METADATA.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        dirname = meta_path.parent.name
        stock = inventory.get(dirname, {})
        # chapter TOC from filenames only
        toc = []
        for pdf in sorted(meta_path.parent.glob("*.pdf")):
            stem = re.sub(r"^\d+[_-]?", "", pdf.stem).replace("_", " ").replace("-", " ")
            toc.append(stem[:100])
        books.append(
            {
                "dirname": dirname,
                "id": dirname,
                "doc_id": dirname,
                "title": meta.get("title") or dirname,
                "authors": meta.get("authors") or meta.get("author") or "",
                "subject": meta.get("subject") or "",
                "publisher": meta.get("publisher") or "",
                "call_no": meta.get("call_number") or meta.get("call_no") or f"PILOT/{dirname[:12].upper()}",
                "rack": meta.get("rack") or "Pilot shelf (metadata index)",
                "publication_year": stock.get("publication_year") or "—",
                "category": stock.get("category") or ("Circulating" if meta.get("open_access") else "Reference"),
                "total_copies": int(stock.get("total_copies") or 0),
                "available_copies": int(stock.get("available_copies") or 0),
                "availability": stock.get("availability") or "Available in library",
                "take_home": str(stock.get("take_home") or "No").lower() == "yes",
                "open_access": bool(meta.get("open_access")),
                "id": dirname,
                "doc_id": dirname,
                "toc_sample": toc[:12],
                "compliance": meta.get("compliance_note")
                or "Index/TOC/authors only — no full book body (Jul 21).",
            }
        )
    return books


def _book_search_score(query: str, book: dict[str, Any]) -> int:
    """Score a shelf book against title, author, subject, and common aliases."""
    title = str(book.get("title") or "").lower()
    blob = f"{title} {book.get('authors', '')} {book.get('subject', '')} {book.get('dirname', '')}".lower()
    ignored = {
        "the", "and", "for", "with", "what", "where", "find", "book", "books",
        "about", "from", "library", "pilot", "physical", "copy", "copies", "take",
        "home", "borrow", "checkout", "check", "available", "availability",
    }
    tokens = set(re.findall(r"[a-z0-9]{3,}", query)) - ignored
    score = sum(1 for token in tokens if token in blob)
    aliases = {
        "dbms": "database",
        "clrs": "introduction to algorithms",
        "ostep": "three easy pieces",
        "dinosaur": "operating system concepts",
    }
    for alias, phrase in aliases.items():
        if alias in query and phrase in blob:
            score += 5
    if len(title) >= 8 and title in query:
        score += 6
    return score


def _matching_books(query: str, books: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return shelf books ordered by relevance, without duplicate titles."""
    scored = [(_book_search_score(query, book), book) for book in books]
    scored.sort(key=lambda item: -item[0])
    matched = [book for score, book in scored if score > 0]
    use = matched or books
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for book in use:
        title = str(book.get("title") or "")
        if title and title not in seen:
            seen.add(title)
            unique.append(book)
    return unique


def _inventory_table(books: list[dict[str, Any]]) -> str:
    """Render book circulation details as a Markdown table."""
    lines = [
        "| Title | Authors | Year | Category | Availability | Copies | Take home? |",
        "|---|---|---:|---|---|---:|---|",
    ]
    for book in books:
        authors = str(book.get("authors") or "—").replace("|", "/")
        available = int(book.get("available_copies") or 0)
        total = int(book.get("total_copies") or 0)
        lines.append(
            f"| {book.get('title') or '—'} | {authors} | "
            f"{book.get('publication_year') or '—'} | {book.get('category') or '—'} | "
            f"{book.get('availability') or '—'} | {available}/{total} | "
            f"{'Yes' if book.get('take_home') and available > 0 else 'No'} |"
        )
    return "\n".join(lines)


def _take_home_reply(query: str, books: list[dict[str, Any]]) -> str | None:
    """Answer whether a named book may leave the library."""
    matched = _matching_books(query, books)
    if not matched:
        return None
    book = matched[0]
    available = int(book.get("available_copies") or 0)
    if book.get("take_home") and available > 0:
        answer = f"**Yes.** {book['title']} is circulating and may be taken home."
    elif str(book.get("category") or "").lower() == "reference":
        answer = (
            f"**No.** {book['title']} is available in the library, but it is a "
            "reference book and cannot be taken home."
        )
    else:
        answer = f"**No.** {book['title']} currently has no take-home copy available."
    return f"{answer}\n\n**Book details**\n\n{_inventory_table([book])}"



def format_catalog_reply(query: str) -> str | None:
    """Answer catalog and circulation questions from local spreadsheet data."""
    q = (query or "").lower().strip()
    if not q:
        return None

    idx = load_ods_index()
    books = load_book_shelf()
    take_home_query = any(
        phrase in q
        for phrase in ("can i take", "take home", "can i borrow", "may i borrow", "check out", "checkout")
    )
    if take_home_query and books:
        return _take_home_reply(q, books)

    # Subject-wise title counts
    if any(k in q for k in ("subject-wise", "subject wise", "title count", "subject leaderboard", "how many titles")):
        lines = ["**Subject-wise title counts** (pilot ODS export):", ""]
        for row in idx["subjects"][:25]:
            if row.get("subject"):
                lines.append(f"- **{row['subject']}**: {row.get('title_count') or '—'} titles")
        if len(lines) <= 2:
            lines.append("_No subject ODS rows loaded — check docs/*.ods._")
        lines.append("")
        lines.append("_not live against Koha - - Pilot catalog sample from institutional KOHA exports under docs/._")
        return "\n".join(lines)

    # Journal titles / issues
    if any(k in q for k in ("journal", "periodical", "magazine", "issue count", "subscription")):
        lines = ["**Journals / periodicals** (pilot ODS):", ""]
        hits = idx["journals"][:20]
        if not hits and idx["titles"]:
            # fall back: titles that look like journals
            hits = [{"title": t["title"], "extra": [t.get("available", "")]} for t in idx["titles"][:15]]
        for j in hits:
            extra = ", ".join(x for x in (j.get("extra") or []) if x)
            lines.append(f"- **{j.get('title') or '—'}**" + (f" — {extra}" if extra else ""))
        if len(lines) <= 2:
            lines.append("_No journal rows in ODS index yet._")
        return "\n".join(lines)

    # Physical book, shelf location, availability, and inventory details.
    shelf_keys = (
        "shelf", "call number", "call no", "rack", "silberschatz", "ramakrishnan",
        "physical book", "where is", "available copies", "availability", "borrow",
        "ostep", "weiss", "clrs", "database system concepts", "operating system concepts",
        "paging", "segmentation", "virtual memory", "page table", "frame", "tlb",
    )
    if any(key in q for key in shelf_keys) or (
        "book" in q
        and any(key in q for key in ("dbms", "database", "os ", "operating", "dsa", "data structure"))
    ):
        use = _matching_books(q, books)[:6]
        if not use:
            return "No pilot book metadata was found in the library inventory."
        lines = ["**Library book details**", "", _inventory_table(use)]
        lines.extend(["", "Reference books are available in the library only; circulating books may be taken home when a copy is available."])
        return "\n".join(lines)

    # Keyword title search
    if any(k in q for k in ("search the library", "find book", "title list", "available copies", "catalog")):
        # pick a keyword from query
        stop = {"the", "and", "for", "with", "what", "where", "find", "book", "books", "search", "library", "catalog", "about", "on"}
        tokens = [t for t in re.findall(r"[a-z0-9]{3,}", q) if t not in stop]
        lines = ["**Catalog title hits** (ODS keyword/titles export):", ""]
        hits = []
        for t in idx["titles"]:
            blob = f"{t.get('title','')} {t.get('author','')}".lower()
            if tokens and any(tok in blob for tok in tokens):
                hits.append(t)
        for t in (hits or idx["titles"])[:15]:
            avail = t.get("available") or "?"
            lines.append(f"- **{t.get('title') or '—'}** — {t.get('author') or '—'} (avail: {avail})")
        if len(lines) <= 2:
            lines.append("_No title rows loaded from docs/ ODS._")
        return "\n".join(lines)

    return None
