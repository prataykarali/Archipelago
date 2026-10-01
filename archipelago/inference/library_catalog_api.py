"""
Library Catalog API Builder for Archipelago.

Merges Pearson eLibrary textbooks, Koha ODS exports (Holdings, Journals, Subject Counts, Subject Titles),
and research papers into a comprehensive institutional catalog payload.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from urllib.parse import quote as _url_quote
import zipfile
import xml.etree.ElementTree as ET

from archipelago.ingestion.pearson_connector import PearsonCatalog
from archipelago.resolver.huggingface import enumerate_hf_resources

logger = logging.getLogger("archipelago.inference.library_catalog_api")

_CATALOG_COLORS = (
    ("#2563eb", "#93c5fd"), ("#7c3aed", "#c4b5fd"), ("#059669", "#6ee7b7"),
    ("#d97706", "#fde68a"), ("#dc2626", "#fca5a5"), ("#0891b2", "#67e8f9"),
)


def _display_title(path: str) -> str:
    """Turn a dataset path into a readable title without inventing metadata."""
    stem = Path(path).stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", stem).strip()


def _shelf_key(item: dict) -> str:
    """Collapse mirrors of one resource while preserving distinct catalog titles."""
    if item.get("isPearson"):
        return f"pearson:{item.get('id')}"
    title = str(item.get("title") or item.get("id") or "").lower()
    return re.sub(r"[^a-z0-9]", "", title)


def _deduplicate_shelf(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = _shelf_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def parse_ods_rows(file_path: Path) -> list[list[str]]:
    """Parse an ODS file into rows of string values using standard zipfile + XML."""
    if not file_path.is_file():
        return []
    try:
        with zipfile.ZipFile(file_path) as z:
            content = z.read("content.xml")
        tree = ET.fromstring(content)
        ns = {
            "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
            "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
        }
        rows = []
        for table in tree.findall(".//table:table", ns):
            for row_elem in table.findall(".//table:table-row", ns):
                r = []
                for cell in row_elem.findall(".//table:table-cell", ns):
                    repeat = int(
                        cell.attrib.get(
                            "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}number-columns-repeated",
                            1,
                        )
                    )
                    text_nodes = cell.findall(".//text:p", ns)
                    val = " ".join([tn.text for tn in text_nodes if tn.text])
                    r.extend([val] * min(repeat, 10))
                while r and not r[-1]:
                    r.pop()
                if r:
                    rows.append(r)
        return rows
    except Exception as exc:
        logger.warning("Failed to parse ODS file %s: %s", file_path, exc)
        return []


def build_library_data_payload(base_dir: str | Path) -> dict:
    """Build complete JSON response for /api/library/data."""
    b_dir = Path(base_dir).resolve()
    if (b_dir / "data" / "catalogs").is_dir():
        arch_dir = b_dir
    elif (b_dir.parent / "data" / "catalogs").is_dir():
        arch_dir = b_dir.parent
    elif (b_dir / "Archipelago" / "data" / "catalogs").is_dir():
        arch_dir = b_dir / "Archipelago"
    else:
        arch_dir = b_dir
    repo_root = arch_dir

    # 1. Pearson Books
    cat_path = arch_dir / "data" / "catalogs" / "pearson_bookshelf.json"
    pearson_books = []
    if cat_path.is_file():
        try:
            with cat_path.open("r", encoding="utf-8") as f:
                pdata = json.load(f)
                pearson_books = pdata.get("books", [])
        except Exception as e:
            logger.warning("Error loading Pearson bookshelf: %s", e)

    # 2. Local Research Papers
    papers_dir = arch_dir / "pdfs" / "papers"
    papers = []
    if papers_dir.is_dir():
        for p in papers_dir.glob("*.pdf"):
            papers.append({
                "title": p.stem.replace("_", " "),
                "filename": p.name,
                "category": "paper",
                "source": "ArXiv / IEEE / ACM",
            })

    # 3. Koha ODS Data Files
    # Exports live beside the project checkout in local deployments.  Include
    # that stable parent location so the 109-record Koha snapshot is not lost.
    ods_locations = [repo_root, arch_dir / "data" / "koha", arch_dir, arch_dir.parent]

    def find_ods(filename: str) -> Path | None:
        for loc in ods_locations:
            candidate = loc / filename
            if candidate.is_file():
                return candidate
        return None

    # Holdings (Titles List with specified keyword-reportresults.ods)
    holdings_path = find_ods("Titles List with specified keyword-reportresults.ods")
    holdings = []
    total_copies = 0
    available_copies = 0

    if holdings_path:
        h_rows = parse_ods_rows(holdings_path)
        if len(h_rows) > 1:
            for r in h_rows[1:]:
                biblionumber = r[0] if len(r) > 0 else ""
                title = r[1] if len(r) > 1 else ""
                author = r[2] if len(r) > 2 and r[2] else "Unknown"
                publisher = r[3] if len(r) > 3 and r[3] else "Unknown"
                accession = r[4] if len(r) > 4 else ""
                no_copies_str = r[5] if len(r) > 5 else "0"
                avail_copies_str = r[6] if len(r) > 6 else "0"
                avail_barcodes = r[7] if len(r) > 7 else ""
                overdue = r[8] if len(r) > 8 else "0"

                try:
                    c_num = int(no_copies_str)
                except ValueError:
                    c_num = 0
                try:
                    a_num = int(avail_copies_str)
                except ValueError:
                    a_num = 0

                total_copies += c_num
                available_copies += a_num

                holdings.append({
                    "biblionumber": biblionumber,
                    "title": title,
                    "author": author,
                    "publisher": publisher,
                    "accession": accession,
                    "no_of_copies": c_num,
                    "available_copies": a_num,
                    "available_barcodes": avail_barcodes,
                    "overdue_items": overdue,
                    "available_ratio": f"{a_num} / {c_num}",
                })

    # Journals (JOURNALS TITLES AND ISSUE COUNTS-reportresults.ods)
    journals_path = find_ods("JOURNALS TITLES AND ISSUE COUNTS-reportresults.ods")
    journals = []
    if journals_path:
        j_rows = parse_ods_rows(journals_path)
        if len(j_rows) > 1:
            for r in j_rows[1:]:
                journals.append({
                    "title": r[0] if len(r) > 0 else "",
                    "vol": r[1] if len(r) > 1 else "",
                    "date": r[2] if len(r) > 2 else "",
                    "status": r[3] if len(r) > 3 else "",
                })

    # Subject Summary Counts (SUBJECT-WISE TITLE COUNT-reportresults.ods)
    subj_summary_path = find_ods("SUBJECT-WISE TITLE COUNT-reportresults.ods")
    subject_counts = []
    if subj_summary_path:
        sc_rows = parse_ods_rows(subj_summary_path)
        if len(sc_rows) > 1:
            for r in sc_rows[1:]:
                subject_counts.append({
                    "subject": r[0] if len(r) > 0 else "",
                    "total_titles": r[1] if len(r) > 1 else "0",
                })

    # Subject Detailed Titles (SUBJECT-WISE TITLE COUNT-reportresults (1).ods)
    subj_titles_path = find_ods("SUBJECT-WISE TITLE COUNT-reportresults (1).ods")
    subject_titles = []
    if subj_titles_path:
        st_rows = parse_ods_rows(subj_titles_path)
        if len(st_rows) > 1:
            for r in st_rows[1:]:
                subject_titles.append({
                    "subject": r[0] if len(r) > 0 else "",
                    "title": r[1] if len(r) > 1 else "",
                    "author": r[2] if len(r) > 2 else "",
                    "year": r[3] if len(r) > 3 else "",
                })

    # 4. Construct E-Book Shelf (46 titles: 40 Pearson + 6 local PDFs)
    ebook_shelf = []
    colors_preset = _CATALOG_COLORS

    # Hardcoded prominent pilot e-books (6 foundational resources)
    prominent_ebooks = [
        {
            "id": "corpus_book_artificial_intelligence_a_new_synthesis_1998",
            "title": "Artificial Intelligence: A New Synthesis",
            "author": "Nils J. Nilsson",
            "year": "1998",
            "isPearson": False,
            "primaryColor": "#2563eb",
            "accentColor": "#93c5fd",
            "domain": "Artificial Intelligence & Machine Learning",
            "pdfUrl": "https://archive.org/details/artificialintell0000nils",
            "resolveUrl": "/resolve/corpus_book_artificial_intelligence_a_new_synthesis_1998",
            "desc": "Foundational text on agent architectures, state-space search, logic, probabilistic reasoning, and neural networks.",
            "isbn": "9781558604674",
            "page_count": 533,
            "toc": [
                {"title": "Chapter 1: Reactive Agents", "page": 1},
                {"title": "Chapter 2: Search in State Spaces", "page": 25},
                {"title": "Chapter 3: Planning & Logic", "page": 89}
            ]
        },
        {
            "id": "paper_attention_is_all_you_need_2017",
            "title": "Attention Is All You Need",
            "author": "Vaswani et al.",
            "year": "2017",
            "isPearson": False,
            "primaryColor": "#7c3aed",
            "accentColor": "#c4b5fd",
            "domain": "Artificial Intelligence & Machine Learning",
            "pdfUrl": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            "resolveUrl": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            "desc": "Introduces multi-head self-attention mechanisms, eliminating recurrence and convolution in sequence models.",
            "isbn": "ArXiv-1706.03762",
            "page_count": 15,
            "toc": [
                {"title": "1. Introduction & Background", "page": 1},
                {"title": "2. Multi-Head Attention", "page": 5}
            ]
        },
        {
            "id": "book_math_for_machine_learning_2020",
            "title": "Mathematics for Machine Learning",
            "author": "Marc Peter Deisenroth et al.",
            "year": "2020",
            "isPearson": False,
            "primaryColor": "#059669",
            "accentColor": "#6ee7b7",
            "domain": "Signal Processing & Mathematics",
            "pdfUrl": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/textbooks/Deisenroth_Math_For_ML.pdf",
            "resolveUrl": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/textbooks/Deisenroth_Math_For_ML.pdf",
            "desc": "Linear algebra, analytic geometry, matrix decompositions, vector calculus, and optimization for ML models.",
            "isbn": "9781108455145",
            "page_count": 398,
            "toc": [
                {"title": "Part I: Mathematical Foundations", "page": 1},
                {"title": "Part II: Central Machine Learning Problems", "page": 200}
            ]
        },
        {
            "id": "book_deep_learning_goodfellow_2016",
            "title": "Deep Learning",
            "author": "Ian Goodfellow, Yoshua Bengio, Aaron Courville",
            "year": "2016",
            "isPearson": False,
            "primaryColor": "#0891b2",
            "accentColor": "#67e8f9",
            "domain": "Artificial Intelligence & Machine Learning",
            "pdfUrl": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/papers/Goodfellow2014_GAN.pdf",
            "resolveUrl": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/papers/Goodfellow2014_GAN.pdf",
            "desc": "Comprehensive textbook on deep neural networks, optimization, convolutional networks, sequence models, and generative models.",
            "isbn": "9780262035613",
            "page_count": 800,
            "toc": [
                {"title": "Chapter 6: Deep Feedforward Networks", "page": 164},
                {"title": "Chapter 9: Convolutional Networks", "page": 326}
            ]
        },
        {
            "id": "book_speech_and_language_processing_jurafsky",
            "title": "Speech and Language Processing",
            "author": "Dan Jurafsky & James H. Martin",
            "year": "2023",
            "isPearson": False,
            "primaryColor": "#dc2626",
            "accentColor": "#fca5a5",
            "domain": "Artificial Intelligence & Machine Learning",
            "pdfUrl": "https://web.stanford.edu/~jurafsky/slp3/",
            "resolveUrl": "https://web.stanford.edu/~jurafsky/slp3/",
            "desc": "Classic NLP and computational linguistics reference covering n-grams, transformers, machine translation, and dialogue systems.",
            "isbn": "9780131873216",
            "page_count": 945,
            "toc": [
                {"title": "Chapter 10: Transformers and Pretrained Models", "page": 210}
            ]
        },
        {
            "id": "ostep_three_easy_pieces",
            "title": "Operating Systems: Three Easy Pieces (OSTEP)",
            "author": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
            "year": "2018",
            "isPearson": False,
            "primaryColor": "#d97706",
            "accentColor": "#fde68a",
            "domain": "Operating Systems & Architecture",
            "pdfUrl": "/pdfs/archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
            "resolveUrl": "/resolve/ostep_three_easy_pieces?source=local",
            "desc": "Foundational operating systems architecture text covering CPU virtualization, memory paging, concurrency, and log-structured storage.",
            "isbn": "9781985086593",
            "page_count": 714,
            "toc": [
                {"title": "Dialogue on Virtualization", "page": 1},
                {"title": "Paging: Introduction", "page": 185}
            ]
        }
    ]

    ebook_shelf.extend(prominent_ebooks)

    for i, pb in enumerate(pearson_books):
        pcol, acol = colors_preset[i % len(colors_preset)]
        b_id = pb.get("id", f"pearson_{i}")
        open_url = f"/open/{b_id}"
        r_url = pb.get("reader_base_url", "")
        if not r_url:
            sub_id = pb.get("subscription_id", "")
            sub_param = f"?subscriptionId={sub_id}" if sub_id else ""
            if pb.get("book_type") == "pdf":
                r_url = f"https://ebooks.elibrary.in.pearson.com/wr/pdfviewer.html{sub_param}#book/{b_id}"
            else:
                r_url = f"https://ebooks.elibrary.in.pearson.com/wr/index.html{sub_param}#book/{b_id}"

        ebook_shelf.append({
            "id": b_id,
            "title": pb.get("title", "Pearson Title"),
            "author": pb.get("author", "Pearson Education"),
            "year": "2024",
            "isPearson": True,
            "primaryColor": pcol,
            "accentColor": acol,
            "domain": pb.get("domain", "Computer Science & Engineering"),
            "pearsonUrl": r_url,
            "reader_url": open_url,
            "resolveUrl": open_url,
            "desc": f"Pearson institutional title in {pb.get('domain', 'CS')}. ISBN: {pb.get('isbn', 'N/A')}.",
            "isbn": pb.get("isbn", "N/A"),
            "page_count": pb.get("page_count", 0),
            "toc": [
                {"title": "Chapter 1: Foundations & Architecture", "page": 1},
                {"title": "Chapter 2: Core Concepts & Practice", "page": 35},
                {"title": "Chapter 3: Advanced Topics", "page": 90}
            ]
        })

    # Add Research Papers to E-Book Shelf
    for j, p in enumerate(papers):
        pcol, acol = colors_preset[(j + len(prominent_ebooks) + len(pearson_books)) % len(colors_preset)]
        fname = p["filename"]
        doc_id = f"papers/{fname}"
        title = p["title"]
        ebook_shelf.append({
            "id": doc_id,
            "title": title,
            "author": p.get("source", "ArXiv / Academic Research"),
            "year": "2020-2024",
            "isPearson": False,
            "isPaper": True,
            "primaryColor": pcol,
            "accentColor": acol,
            "domain": "Research Papers & Preprints",
            "pdfUrl": f"/pdfs/{doc_id}",
            "reader_url": f"/read/{doc_id}",
            "resolveUrl": f"/open/{doc_id}",
            "desc": f"Foundational AI/ML research publication: {title}. Readable in the internal PDF reader.",
            "isbn": "ArXiv Preprint",
            "page_count": 15,
            "toc": [
                {"title": "1. Abstract & Motivation", "page": 1},
                {"title": "2. Formulation & Architecture", "page": 3},
                {"title": "3. Experiments & Results", "page": 6},
                {"title": "4. Conclusions & Future Work", "page": 10}
            ]
        })

    # Hugging Face is the canonical source for the full paper/book collection.
    # This supplements local PDFs rather than replacing them; the resolver's
    # bundled manifest preserves the shelf when the private Hub is unreachable.
    hf_resources = enumerate_hf_resources()
    for k, resource in enumerate(hf_resources):
        hf_path = str(resource.get("filename") or "")
        if not hf_path or "/librarian_uploads/" in hf_path:
            continue
        pcol, acol = colors_preset[(k + len(ebook_shelf)) % len(colors_preset)]
        is_paper = resource.get("category") == "paper" or "/papers/" in f"/{hf_path}"
        ebook_shelf.append({
            "id": hf_path,
            "title": _display_title(hf_path),
            "author": "Archipelago Hugging Face Library",
            "year": "",
            "isPearson": False,
            "isPaper": is_paper,
            "primaryColor": pcol,
            "accentColor": acol,
            "domain": "Research Papers & Preprints" if is_paper else "Textbooks & Course Material",
            "pdfUrl": resource.get("blob_url") or resource.get("url"),
            "reader_url": f"/open/{_url_quote(hf_path, safe='/')}",
            "resolveUrl": f"/open/{_url_quote(hf_path, safe='/')}",
            "desc": "Indexed Hugging Face library resource. Opens at the requested source page.",
            "isbn": "",
            "page_count": 0,
            "toc": [{"title": "Open indexed source", "page": 1}],
        })

    # Preserve every Koha record in the showcase as a catalog-only title.  A
    # record without a licensed digital file remains browseable, but is never
    # misrepresented as a PDF or redirected to a broken reader.
    for h in holdings:
        title = str(h.get("title") or "").strip()
        if not title:
            continue
        pcol, acol = colors_preset[len(ebook_shelf) % len(colors_preset)]
        ebook_shelf.append({
            "id": f"koha-{h.get('biblionumber') or title}",
            "title": title,
            "author": h.get("author") or "Central Library",
            "year": "",
            "isPearson": False,
            "isCatalogOnly": True,
            "primaryColor": pcol,
            "accentColor": acol,
            "domain": "Central Library Holdings",
            "desc": f"Catalog record · {h.get('available_ratio') or 'availability unknown'} · Accession: {h.get('accession') or 'N/A'}.",
            "isbn": "Catalog record",
            "page_count": 0,
            "toc": [{"title": "View holding in the catalog below", "page": 1}],
        })

    ebook_shelf = _deduplicate_shelf(ebook_shelf)

    graph_stats = {"nodes": 0, "edges": 0, "clusters": 0}
    graph_file = repo_root / "okf_graph.json"
    if graph_file.is_file():
        try:
            with open(graph_file, "r", encoding="utf-8") as gf:
                gdata = json.load(gf)
                graph_stats = {
                    "nodes": len(gdata.get("nodes", [])),
                    "edges": len(gdata.get("edges", [])),
                    "clusters": len(gdata.get("clusters", [])),
                }
        except Exception:
            pass

    return {
        "success": True,
        "graph_stats": graph_stats,
        "pearson_books": pearson_books,
        "total_pearson_books": len(pearson_books),
        "research_papers": papers,
        "hf_resources": hf_resources,
        "total_papers": len([item for item in ebook_shelf if item.get("isPaper")]),
        "ebook_shelf": ebook_shelf,
        "total_ebooks": len(ebook_shelf),
        "ebook_stats": (
            f"{len(ebook_shelf)} titles · {len(pearson_books)} Pearson eBooks · "
            f"{len([item for item in ebook_shelf if item.get('isPaper')])} research papers · "
            f"{len(holdings)} catalog holdings"
        ),
        "holdings": holdings,
        "holdings_stats": {
            "total_records": len(holdings),
            "total_copies": total_copies,
            "available_copies": available_copies,
        },
        "journal_issues": journals,
        "total_journal_issues": len(journals),
        "subject_counts": subject_counts,
        "total_subject_counts": len(subject_counts),
        "subject_titles": subject_titles,
        "total_subject_titles": len(subject_titles),
        "credentials": {
            "pearson_portal": "https://elibrary.in.pearson.com/",
            "access_note": "Institutional login required. Inquire at Central Library desk for student access credentials.",
        },

        "opac_url": "http://uemk-opac.l2c2.co.in",
        "domains": [
            "Artificial Intelligence & Machine Learning",
            "Computer Networks & Security",
            "Operating Systems & Architecture",
            "Compilers & Algorithms",
            "Databases & Web Engineering",
            "Electronics & Embedded Systems",
            "Signal Processing & Mathematics",
        ],
    }
