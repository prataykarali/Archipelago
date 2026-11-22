"""Present the verified research parameters in one stable, compact Excel schema."""

from __future__ import annotations

from copy import copy
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .comparable_rank import FIELDS as COMPARABLE_FIELDS
from .comparable_rank import comparable_papers
from .search_rankings import (
    AUTHOR_FIELDS,
    author_values,
    matching_paper,
    ordered_author_keys,
    paper_values,
    ranking_year,
    venue_values,
)
from .standard_validation import distinct_standard_papers
from .workbook_standard import build_standard_workbook

RANKABLE_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "Papers": (
        ("Paper Title", "Paper title"),
        ("Authors", "Authors"),
        *((heading, "") for heading in COMPARABLE_FIELDS),
        ("Publication Year", "Year"),
        ("Paper Link", "Paper link"),
        ("Verified Sources", "Verified sources"),
    ),
    "Authors": (
        ("Author Name", "Author name"),
        *((heading, "") for heading in AUTHOR_FIELDS),
    ),
}


def build_rankable_workbook(run: dict[str, Any]) -> BytesIO:
    """Keep provider facts and add explicit search-scoped ranking measurements."""
    book = load_workbook(build_standard_workbook(run))
    papers = distinct_standard_papers(run.get("papers") or [])
    author_keys = ordered_author_keys(papers)
    topic = str((run.get("options") or {}).get("topic") or "")
    as_of_year = ranking_year(run)
    comparable = comparable_papers(run)
    venue_sheet = book["Publications"]
    venue_headers = {str(cell.value): cell.column for cell in venue_sheet[1]}
    venues = {
        str(venue_sheet.cell(row, venue_headers["Venue name"]).value or "").strip().casefold(): row
        for row in range(2, venue_sheet.max_row + 1)
    }
    for sheet_name, columns in RANKABLE_COLUMNS.items():
        old = book[sheet_name]
        index = book.sheetnames.index(sheet_name)
        new = book.create_sheet(f"_new_{sheet_name}", index)
        old_headers = {str(cell.value): cell.column for cell in old[1]}
        for new_column, (heading, source_heading) in enumerate(columns, 1):
            source_sheet = old if source_heading in old_headers else venue_sheet
            source_column = (old_headers if source_sheet is old else venue_headers).get(
                source_heading
            )
            heading_cell = new.cell(1, new_column, heading)
            if source_column is not None:
                source_header = source_sheet.cell(1, source_column)
                heading_cell._style = copy(source_header._style)
                source_width = source_sheet.column_dimensions[
                    get_column_letter(source_column)
                ].width
                new.column_dimensions[get_column_letter(new_column)].width = source_width
                for row in range(2, old.max_row + 1):
                    venue_name = (
                        str(old.cell(row, old_headers["Publication venue"]).value or "")
                        .strip()
                        .casefold()
                        if sheet_name == "Papers"
                        else ""
                    )
                    venue_row = venues.get(venue_name)
                    original = (
                        source_sheet.cell(venue_row, source_column)
                        if source_sheet is venue_sheet and venue_row
                        else (old.cell(row, source_column) if source_sheet is old else None)
                    )
                    if original is None:
                        continue
                    target = new.cell(row, new_column, original.value)
                    target._style = copy(original._style)
                    if original.hyperlink:
                        target._hyperlink = copy(original.hyperlink)
                        target._hyperlink.ref = target.coordinate
            else:
                heading_cell._style = copy(old.cell(1, 1)._style)
                new.column_dimensions[get_column_letter(new_column)].width = 24
        for row in range(2, old.max_row + 1):
            new.row_dimensions[row].height = old.row_dimensions[row].height
            if sheet_name == "Papers":
                paper = matching_paper(
                    old.cell(row, old_headers["Paper title"]).value,
                    old.cell(row, old_headers["Year"]).value,
                    papers,
                )
                if paper is not None:
                    paper_index = next(
                        (index for index, candidate in enumerate(papers) if candidate is paper),
                        None,
                    )
                    calculated = {
                        **paper_values(paper, topic, as_of_year),
                        **venue_values(str(paper.get("venue") or ""), papers, topic),
                        **(comparable[paper_index] if paper_index is not None else {}),
                    }
                    for column, (heading, _) in enumerate(columns, 1):
                        if heading in calculated:
                            new.cell(row, column, calculated[heading])
            else:
                name = str(old.cell(row, old_headers["Author name"]).value or "")
                identity_key = author_keys[row - 2] if row - 2 < len(author_keys) else None
                calculated = author_values(name, papers, topic, identity_key)
                for column, (heading, _) in enumerate(columns, 1):
                    if heading in calculated:
                        new.cell(row, column, calculated[heading])
        new.freeze_panes = "C2"
        new.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{new.max_row}"
        book.remove(old)
        new.title = sheet_name
    book.remove(venue_sheet)
    book.remove(book["Start Here"])
    start = book.create_sheet("Start Here", 0)
    start.column_dimensions["A"].width = 32
    start.column_dimensions["B"].width = 100
    guide = (
        ("Archipelago Research Export", "Complete, search-scoped discovery ranking"),
        ("Topic", topic),
        ("Retrieved", str(run.get("retrieved_at") or "")),
        ("Papers", len(papers)),
        (
            "Papers sheet",
            "One admitted paper per row. Every ranking column has a value for every row.",
        ),
        (
            "Authors sheet",
            "Search-scoped byline, query-match, collaboration, venue, source and evidence counts; these are not global author impact measures.",
        ),
        (
            "Venue measures",
            "Venue paper counts and title match summarize only papers in this search with a reported venue. Venue Reported distinguishes an absent venue from a genuine zero count.",
        ),
        (
            "Evidence flags",
            "A 1 means the saved provider record reported that item; 0 means it was not reported. Neither proves the item does not exist.",
        ),
        ("Sources sheet", "Provider records and source links for audit."),
        (
            "Discovery fit",
            "50% title query match + 25% abstract query match + 15% recency within this search + 10% source corroboration within this search.",
        ),
        (
            "Normalization",
            "Recency and source corroboration use min-max scaling across these admitted papers. If all values tie, every paper receives a neutral 50 for that component.",
        ),
        (
            "Absent abstract",
            "Abstract query match is 0 observed words when no abstract was supplied; Abstract Reported distinguishes that case.",
        ),
        (
            "Meaning",
            "Discovery fit prioritizes a query within this saved cohort. It does not measure scientific quality or replace peer review.",
        ),
        (
            "Provider facts",
            "Citation, FWCI, benchmark and licensed venue values are excluded from the complete score. Open a paper dossier or advanced audit to inspect reported provider values.",
        ),
    )
    for label, value in guide:
        start.append((label, value))
        start.cell(start.max_row, 2).alignment = copy(book["Papers"].cell(2, 2).alignment)
    for cell in start[1]:
        cell._style = copy(book["Papers"].cell(1, 1)._style)
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output
