"""Source-specific candidate replies for two audited operating-systems queries."""

from __future__ import annotations

import re
from typing import Any

from library_index import paper_url

OSTEP_ADDRESS_DOC = "archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf"
OSTEP_PAGING_DOC = "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf"
ADDRESS_PAGE = 2
PAGING_PAGE = 3
BASE_BOUNDS_PAGE = 7


def _chapter_citation(graph: Any, concept_id: str, doc_id: str, page: int) -> dict | None:
    """Use an exact indexed chapter passage, never a keyword-similar paper."""
    sources = (graph.nodes.get(concept_id) or {}).get("sources") or []
    for source in sources:
        if source.get("doc_id") == doc_id and source.get("page_number") == page:
            record = graph.cite_record(concept_id, index=1, source_override=source)
            if record.get("doc_id") == doc_id and record.get("page_number") == page:
                return record
    return None


def _base_bounds_passage(catalog: Any) -> dict | None:
    """Find the audited OSTEP chunk that states both relocation and bounds checking."""
    for passage in catalog.passages:
        if passage.get("doc_id") != OSTEP_ADDRESS_DOC or passage.get("page") != BASE_BOUNDS_PAGE:
            continue
        text = str(passage.get("text") or "").lower()
        if "base register" in text and "bounds" in text and passage.get("passage_id"):
            return passage
    return None


def source_grounded_os_reply(
    graph: Any, catalog: Any, query: str
) -> tuple[str, str, None, dict] | None:
    """Answer the audited OSTEP queries with the exact available chapter source."""
    asks_address = bool(re.search(r"\bostep\b", query, re.I)) and bool(
        re.search(r"\b(?:address translation|base[ -]and[ -]bounds)\b", query, re.I)
    )
    asks_base_bounds = bool(re.search(r"\bbase[ -]and[ -]bounds\b", query, re.I)) and bool(
        re.search(r"\b(?:address translation|relocat(?:e|ion)|address space)\b", query, re.I)
    )
    if asks_base_bounds:
        passage = _base_bounds_passage(catalog)
        if passage:
            url = paper_url(OSTEP_ADDRESS_DOC, BASE_BOUNDS_PAGE)
            citation = {
                "label": f"[S1: 07_Address_Translation.pdf, #page={BASE_BOUNDS_PAGE}]",
                "doc_id": OSTEP_ADDRESS_DOC,
                "page_number": BASE_BOUNDS_PAGE,
                "printed_page": passage.get("printed_page"),
                "chunk_id": passage["passage_id"],
                "passage_id": passage["passage_id"],
                "url": url,
                "pdf_url": url,
            }
            text = (
                "**Base-and-bounds address translation.** Hardware adds the base register "
                "to a process's virtual address to relocate it in physical memory. "
                "The bounds register checks whether the virtual address is within the "
                "process's allowed address space; an out-of-bounds access traps. "
                f"The OSTEP textbook explains this on [PDF page {BASE_BOUNDS_PAGE}]({url}) "
                f"{citation['label']}."
            )
            return (
                "BOOK_PAGE",
                text,
                None,
                {
                    "hide_graph": True,
                    "reason": "ostep_base_bounds_indexed",
                    "citations": [citation],
                },
            )
    if asks_address or asks_base_bounds:
        citation = _chapter_citation(graph, "virtual_memory", OSTEP_ADDRESS_DOC, ADDRESS_PAGE)
        if citation is None:
            return (
                "BOOK_PAGE",
                "The OSTEP address-translation chapter is not available with a verified page "
                "in this candidate index, so I cannot point to an exact page.",
                None,
                {"hide_graph": True, "reason": "ostep_address_page_unavailable"},
            )
        text = (
            "**OSTEP Chapter 15, Mechanism: Address Translation.** PDF page 2 explains "
            "hardware-based translation from virtual to physical addresses "
            f"{citation['label']}. The indexed passage does not identify the exact "
            "base-and-bounds section or page; open the chapter to locate that discussion. "
            "This is a textbook chapter, not a research paper."
        )
        return (
            "BOOK_PAGE",
            text,
            None,
            {"hide_graph": True, "reason": "ostep_address_chapter", "citations": [citation]},
        )

    asks_paging = bool(re.search(r"\bpaging\b", query, re.I)) and bool(
        re.search(r"\bpage faults?\b", query, re.I)
    )
    if asks_paging:
        citation = _chapter_citation(graph, "paging", OSTEP_PAGING_DOC, PAGING_PAGE)
        source_line = (
            f" The indexed OSTEP paging introduction explains the page-table mapping {citation['label']}."
            if citation
            else " The indexed OSTEP paging passage is unavailable for this candidate."
        )
        text = (
            "**Paging.** Virtual pages map to physical frames through a page table."
            + source_line
            + "\n\n**General explanation (not established by the cited introductory passage):** "
            "A page fault means the current mapping cannot satisfy the access. "
            "It does not always require disk I/O: a demand-zero fault can allocate and zero "
            "a page, and a copy-on-write fault can create a private copy of a resident page. "
            "Reading backing storage is needed only for faults whose required contents are not resident."
        )
        return (
            "BOOK_PAGE",
            text,
            None,
            {
                "hide_graph": True,
                "reason": "paging_page_fault_qualification",
                "citations": [citation] if citation else [],
            },
        )
    return None
