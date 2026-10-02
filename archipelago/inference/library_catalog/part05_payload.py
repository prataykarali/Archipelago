"""Library catalog payload assembly for /api/library/data."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from archipelago.inference.library_catalog.part01_ods import (
    _deduplicate_shelf,
    find_ods,
    resolve_ods_locations,
)
from archipelago.inference.library_catalog.part02_koha import (
    HOLDINGS_ODS,
    JOURNALS_ODS,
    SUBJECT_COUNTS_ODS,
    SUBJECT_TITLES_ODS,
    load_holdings,
    load_journals,
    load_subject_counts,
    load_subject_titles,
)
from archipelago.inference.library_catalog.part04_shelf import (
    append_hf_resources,
    append_koha_holdings,
    append_papers,
    append_pearson_books,
    build_prominent_ebook_entries,
)
from archipelago.resolver.huggingface import enumerate_hf_resources

logger = logging.getLogger("archipelago.inference.library_catalog_api")

PEARSON_BOOKSHELF = "pearson_bookshelf.json"
GRAPH_EXPORT_FILE = "okf_graph.json"
PEARSON_PORTAL = "https://elibrary.in.pearson.com/"
OPAC_URL = "https://uemk-opac.l2c2.co.in"
CATALOG_DOMAINS = [
    "Artificial Intelligence & Machine Learning",
    "Computer Networks & Security",
    "Operating Systems & Architecture",
    "Compilers & Algorithms",
    "Databases & Web Engineering",
    "Electronics & Embedded Systems",
    "Signal Processing & Mathematics",
]


def _resolve_arch_dir(base_dir: str | Path) -> Path:
    """Locate the Archipelago root that holds data/catalogs."""
    b_dir = Path(base_dir).resolve()
    if (b_dir / "data" / "catalogs").is_dir():
        return b_dir
    if (b_dir.parent / "data" / "catalogs").is_dir():
        return b_dir.parent
    if (b_dir / "Archipelago" / "data" / "catalogs").is_dir():
        return b_dir / "Archipelago"
    return b_dir


def load_pearson_books(arch_dir: Path) -> list[dict]:
    """Load the Pearson eLibrary bookshelf catalog."""
    cat_path = arch_dir / "data" / "catalogs" / PEARSON_BOOKSHELF
    if not cat_path.is_file():
        return []
    try:
        with cat_path.open("r", encoding="utf-8") as f:
            return json.load(f).get("books", [])
    except Exception as e:
        logger.warning("Error loading Pearson bookshelf: %s", e)
        return []


def load_local_papers(arch_dir: Path) -> list[dict]:
    """List locally indexed research papers."""
    papers_dir = arch_dir / "pdfs" / "papers"
    if not papers_dir.is_dir():
        return []
    return [
        {
            "title": p.stem.replace("_", " "),
            "filename": p.name,
            "category": "paper",
            "source": "ArXiv / IEEE / ACM",
        }
        for p in sorted(papers_dir.glob("*.pdf"))
    ]


def load_graph_stats(repo_root: Path) -> dict:
    """Read live graph counts from the export; never hard-code them."""
    graph_file = repo_root / GRAPH_EXPORT_FILE
    if not graph_file.is_file():
        return {"nodes": 0, "edges": 0, "clusters": 0}
    try:
        with open(graph_file, encoding="utf-8") as gf:
            gdata = json.load(gf)
        return {
            "nodes": len(gdata.get("nodes", [])),
            "edges": len(gdata.get("edges", [])),
            "clusters": len(gdata.get("clusters", [])),
        }
    except Exception:
        return {"nodes": 0, "edges": 0, "clusters": 0}


def build_library_data_payload(base_dir: str | Path) -> dict:
    """Build complete JSON response for /api/library/data."""
    arch_dir = _resolve_arch_dir(base_dir)

    pearson_books = load_pearson_books(arch_dir)
    papers = load_local_papers(arch_dir)

    ods_locations = resolve_ods_locations(arch_dir)
    holdings, total_copies, available_copies = load_holdings(find_ods(ods_locations, HOLDINGS_ODS))
    journals = load_journals(find_ods(ods_locations, JOURNALS_ODS))
    subject_counts = load_subject_counts(find_ods(ods_locations, SUBJECT_COUNTS_ODS))
    subject_titles = load_subject_titles(find_ods(ods_locations, SUBJECT_TITLES_ODS))

    prominent_ebooks = build_prominent_ebook_entries()
    shelf: list[dict] = list(prominent_ebooks)
    append_pearson_books(shelf, pearson_books, len(shelf))
    append_papers(shelf, papers, len(shelf))
    hf_resources = enumerate_hf_resources()
    append_hf_resources(shelf, hf_resources, len(shelf))
    append_koha_holdings(shelf, holdings)
    ebook_shelf = _deduplicate_shelf(shelf)

    paper_count = len([item for item in ebook_shelf if item.get("isPaper")])

    return {
        "success": True,
        "graph_stats": load_graph_stats(arch_dir),
        "pearson_books": pearson_books,
        "total_pearson_books": len(pearson_books),
        "research_papers": papers,
        "hf_resources": hf_resources,
        "total_papers": paper_count,
        "ebook_shelf": ebook_shelf,
        "total_ebooks": len(ebook_shelf),
        "ebook_stats": (
            f"{len(ebook_shelf)} titles · {len(pearson_books)} Pearson eBooks · "
            f"{paper_count} research papers · {len(holdings)} catalog holdings"
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
            "pearson_portal": PEARSON_PORTAL,
            "access_note": (
                "Institutional login required. Inquire at Central Library desk "
                "for student access credentials."
            ),
        },
        "opac_url": OPAC_URL,
        "domains": list(CATALOG_DOMAINS),
    }
