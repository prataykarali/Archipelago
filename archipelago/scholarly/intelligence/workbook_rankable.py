"""Present the verified research parameters in one stable, compact Excel schema."""

from __future__ import annotations

from copy import copy
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .search_rankings import (
    AUTHOR_FIELDS,
    PAPER_FIELDS,
    VENUE_FIELDS,
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
        ("Citation Count", "Citation count"),
        ("Citations per Year", "Citations per year"),
        ("Field-Weighted Citation Impact (FWCI)", "FWCI (OpenAlex)"),
        ("Citation Percentile", "Citation percentile (OpenAlex)"),
        ("Topic Relevance Score", "Relevance score (0-1)"),
        ("Publication Year", "Year"),
        *((heading, "") for heading in PAPER_FIELDS),
        ("Benchmark Performance", "Benchmark performance"),
        ("Methodological Evidence", "Research method"),
        ("Reproducibility Indicators", "Reproducibility indicators"),
        ("Reference Count", "Indexed references"),
        ("Influential Citation Count", "Influential citations (Semantic Scholar)"),
        ("Open-Access Status", "Open access"),
        ("Publication Venue", "Publication venue"),
        ("DOI", "DOI"),
        ("Paper Link", "Paper link"),
        ("Citation Provider", "Citation source"),
        ("Verified Sources", "Verified sources"),
        *((heading, "") for heading in VENUE_FIELDS),
        ("Venue h-index", "Venue h-index (OpenAlex)"),
        ("Venue i10-index", "Venue i10-index (OpenAlex)"),
        ("Indexed Publication Count", "Indexed works (OpenAlex)"),
        ("Mean Citedness", "2-year mean citedness (OpenAlex)"),
        ("Indexing Status", "Indexed status (OpenAlex)"),
        ("Venue Category", "Category"),
        ("Venue Publisher", "Publisher"),
        ("Venue Official Link", "Official link"),
        ("Venue Metric Provider", "Venue metric provider"),
    ),
    "Authors": (
        ("Author Name", "Author name"),
        *((heading, "") for heading in AUTHOR_FIELDS),
        ("h-index", "h-index"),
        ("i10-index", "i10-index"),
        ("m-quotient", "m-quotient"),
        ("Total Citations", "Citation count"),
        ("Total Publications", "Publication count"),
        ("Average Citations per Paper", "Avg citations / work"),
        ("Recent Citations", "Recent citations (5y)"),
        ("First-Author Publications", "First-author papers in export"),
        ("Last-Author Publications", "Last-author papers in export"),
        ("Research Relevance", "Best paper relevance (0-1)"),
        ("Collaboration Network", "Verified collaborators in export"),
        ("ORCID", "ORCID"),
        ("Verified Affiliations", "Verified affiliations"),
        ("Profile URL", "Profile URL"),
        ("Metric Provider", "Metric provider"),
        ("Verified Sources", "Verified sources"),
    ),
}


def build_rankable_workbook(run: dict[str, Any]) -> BytesIO:
    """Keep provider facts and add explicit search-scoped ranking measurements."""
    book = load_workbook(build_standard_workbook(run))
    papers = distinct_standard_papers(run.get("papers") or [])
    author_keys = ordered_author_keys(papers)
    topic = str((run.get("options") or {}).get("topic") or "")
    as_of_year = ranking_year(run)
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
                    calculated = {
                        **paper_values(paper, topic, as_of_year),
                        **venue_values(str(paper.get("venue") or ""), papers, topic),
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
    start = book["Start Here"]
    for row in start.iter_rows():
        for cell in row:
            if cell.value == "Standard Research Export (5 sheets)":
                cell.value = "Standard Research Export (4 sheets)"
            elif cell.value == "Publications":
                cell.value = "Venue metrics"
            elif isinstance(cell.value, str) and cell.value.startswith("Publications: "):
                cell.value = cell.value.replace("Publications: ", "Papers venue metric: ", 1)
            elif isinstance(cell.value, str) and cell.value.startswith("One row per venue."):
                cell.value = "Venue ranking fields appear on each paper row in the Papers sheet."
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output
