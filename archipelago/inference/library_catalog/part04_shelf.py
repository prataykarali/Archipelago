"""E-book shelf assembly: prominent, Pearson, papers, HF resources, Koha holdings."""

from __future__ import annotations

from urllib.parse import quote as _url_quote

from archipelago.inference.library_catalog.part01_ods import CATALOG_COLORS, display_title
from archipelago.inference.library_catalog.part03_prominent import PROMINENT_EBOOKS

_PEARSON_READER_BASE = "https://ebooks.elibrary.in.pearson.com/wr"
_PEARSON_PDF_VIEWER = f"{_PEARSON_READER_BASE}/pdfviewer.html"
_PEARSON_INDEX_VIEWER = f"{_PEARSON_READER_BASE}/index.html"
_PEARSON_DEFAULT_YEAR = "2024"
_PEARSON_DEFAULT_AUTHOR = "Pearson Education"
_PEARSON_DEFAULT_DOMAIN = "Computer Science & Engineering"
_PAPER_DEFAULT_AUTHOR = "ArXiv / Academic Research"
PAPER_DOMAIN = "Research Papers & Preprints"
TEXTBOOK_DOMAIN = "Textbooks & Course Material"
HOLDINGS_DOMAIN = "Central Library Holdings"

_PEARSON_DEMO_TOC = [
    {"title": "Chapter 1: Foundations & Architecture", "page": 1},
    {"title": "Chapter 2: Core Concepts & Practice", "page": 35},
    {"title": "Chapter 3: Advanced Topics", "page": 90},
]

_PAPER_DEMO_TOC = [
    {"title": "1. Abstract & Motivation", "page": 1},
    {"title": "2. Formulation & Architecture", "page": 3},
    {"title": "3. Experiments & Results", "page": 6},
    {"title": "4. Conclusions & Future Work", "page": 10},
]


def _colors(offset: int = 0) -> tuple[str, str]:
    return CATALOG_COLORS[offset % len(CATALOG_COLORS)]


def build_prominent_ebook_entries() -> list[dict]:
    """Return copies of the prominent pilot entries so callers cannot mutate the source."""
    return [dict(item) for item in PROMINENT_EBOOKS]


def build_pearson_reader_url(book: dict) -> str:
    """Build the exact Pearson eLibrary reader URL for one catalog book."""
    book_id = book.get("id", "")
    explicit = book.get("reader_base_url", "")
    if explicit:
        return explicit
    sub_id = book.get("subscription_id", "")
    sub_param = f"?subscriptionId={sub_id}" if sub_id else ""
    viewer = _PEARSON_PDF_VIEWER if book.get("book_type") == "pdf" else _PEARSON_INDEX_VIEWER
    return f"{viewer}{sub_param}#book/{book_id}"


def append_pearson_books(
    shelf: list[dict],
    pearson_books: list[dict],
    start_offset: int,
) -> list[dict]:
    """Append Pearson eLibrary titles with exact reader URLs."""
    for i, pb in enumerate(pearson_books):
        pcol, acol = _colors(start_offset + i)
        b_id = pb.get("id", f"pearson_{i}")
        open_url = f"/open/{b_id}"
        shelf.append(
            {
                "id": b_id,
                "title": pb.get("title", "Pearson Title"),
                "author": pb.get("author", _PEARSON_DEFAULT_AUTHOR),
                "year": _PEARSON_DEFAULT_YEAR,
                "isPearson": True,
                "primaryColor": pcol,
                "accentColor": acol,
                "domain": pb.get("domain", _PEARSON_DEFAULT_DOMAIN),
                "pearsonUrl": build_pearson_reader_url(pb),
                "reader_url": open_url,
                "resolveUrl": open_url,
                "desc": f"Pearson institutional title in {pb.get('domain', 'CS')}. ISBN: {pb.get('isbn', 'N/A')}.",
                "isbn": pb.get("isbn", "N/A"),
                "page_count": pb.get("page_count", 0),
                "toc": [dict(t) for t in _PEARSON_DEMO_TOC],
            }
        )
    return shelf


def append_papers(shelf: list[dict], papers: list[dict], start_offset: int) -> list[dict]:
    """Append locally indexed research papers."""
    for j, p in enumerate(papers):
        pcol, acol = _colors(start_offset + j)
        fname = p["filename"]
        doc_id = f"papers/{fname}"
        shelf.append(
            {
                "id": doc_id,
                "title": p["title"],
                "author": p.get("source", _PAPER_DEFAULT_AUTHOR),
                "year": "2020-2024",
                "isPearson": False,
                "isPaper": True,
                "primaryColor": pcol,
                "accentColor": acol,
                "domain": PAPER_DOMAIN,
                "pdfUrl": f"/pdfs/{doc_id}",
                "reader_url": f"/read/{doc_id}",
                "resolveUrl": f"/open/{doc_id}",
                "desc": f"Foundational AI/ML research publication: {p['title']}. Readable in the internal PDF reader.",
                "isbn": "ArXiv Preprint",
                "page_count": 15,
                "toc": [dict(t) for t in _PAPER_DEMO_TOC],
            }
        )
    return shelf


def append_hf_resources(
    shelf: list[dict],
    hf_resources: list[dict],
    start_offset: int,
) -> list[dict]:
    """Append Hugging Face dataset resources with exact per-file blob URLs."""
    for k, resource in enumerate(hf_resources):
        hf_path = str(resource.get("filename") or "")
        if not hf_path or "/librarian_uploads/" in hf_path:
            continue
        pcol, acol = _colors(start_offset + k)
        is_paper = resource.get("category") == "paper" or "/papers/" in f"/{hf_path}"
        open_url = f"/open/{_url_quote(hf_path, safe='/')}"
        shelf.append(
            {
                "id": hf_path,
                "title": display_title(hf_path),
                "author": "Archipelago Hugging Face Library",
                "year": "",
                "isPearson": False,
                "isPaper": is_paper,
                "primaryColor": pcol,
                "accentColor": acol,
                "domain": PAPER_DOMAIN if is_paper else TEXTBOOK_DOMAIN,
                "pdfUrl": resource.get("blob_url") or resource.get("url"),
                "resolveUrl": resource.get("resolve_url") or open_url,
                "reader_url": open_url,
                "desc": "Indexed Hugging Face library resource. Opens at the exact dataset file page.",
                "isbn": "",
                "page_count": 0,
                "toc": [{"title": "Open indexed source", "page": 1}],
            }
        )
    return shelf


def append_koha_holdings(shelf: list[dict], holdings: list[dict]) -> list[dict]:
    """Append every Koha record as a browseable catalog-only title.

    A record without a licensed digital file stays browseable but is never
    misrepresented as a PDF or redirected to a broken reader.
    """
    for h in holdings:
        title = str(h.get("title") or "").strip()
        if not title:
            continue
        pcol, acol = _colors(len(shelf))
        shelf.append(
            {
                "id": f"koha-{h.get('biblionumber') or title}",
                "title": title,
                "author": h.get("author") or "Central Library",
                "year": "",
                "isPearson": False,
                "isCatalogOnly": True,
                "primaryColor": pcol,
                "accentColor": acol,
                "domain": HOLDINGS_DOMAIN,
                "desc": (
                    f"Catalog record · {h.get('available_ratio') or 'availability unknown'} · "
                    f"Accession: {h.get('accession') or 'N/A'}."
                ),
                "isbn": "Catalog record",
                "page_count": 0,
                "toc": [{"title": "View holding in the catalog below", "page": 1}],
            }
        )
    return shelf
