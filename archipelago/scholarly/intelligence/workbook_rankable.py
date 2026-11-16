"""Present the verified research parameters in one stable, compact Excel schema."""

from __future__ import annotations

from copy import copy
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

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
    ),
    "Authors": (
        ("Author Name", "Author name"),
        ("h-index", "h-index"),
        ("i10-index", "i10-index"),
        ("g-index", "g-index"),
        ("m-quotient", "m-quotient"),
        ("Total Citations", "Citation count"),
        ("Total Publications", "Publication count"),
        ("Average Citations per Paper", "Avg citations / work"),
        ("Median Citations per Paper", "Median citations / work"),
        ("Recent Citations", "Recent citations (5y)"),
        ("Field-Normalized Impact", "Field-normalized impact"),
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
    "Publications": (
        ("Venue Name", "Venue name"),
        ("Journal Impact Factor (JIF)", "JIF (Clarivate)"),
        ("CiteScore", "CiteScore (Scopus)"),
        ("SCImago Journal Rank (SJR)", "SJR (SCImago)"),
        ("Source Normalized Impact per Paper (SNIP)", "SNIP"),
        ("Q1-Q4 Quartile", "Journal quartile"),
        ("CORE/ICORE Rank", "CORE / ICORE rank"),
        ("h5-index", "h5-index"),
        ("h5-median", "h5-median"),
        ("Venue h-index", "Venue h-index (OpenAlex)"),
        ("Venue i10-index", "Venue i10-index (OpenAlex)"),
        ("Acceptance Rate", "Acceptance rate"),
        ("Indexed Publication Count", "Indexed works (OpenAlex)"),
        ("Mean Citedness", "2-year mean citedness (OpenAlex)"),
        ("Indexing Status", "Indexed status (OpenAlex)"),
        ("Category", "Category"),
        ("Publisher", "Publisher"),
        ("Official Link", "Official link"),
        ("Metric Provider", "Venue metric provider"),
    ),
}


def build_rankable_workbook(run: dict[str, Any]) -> BytesIO:
    """Keep source-backed values while presenting all requested parameters in fixed order."""
    book = load_workbook(build_standard_workbook(run))
    for sheet_name, columns in RANKABLE_COLUMNS.items():
        old = book[sheet_name]
        index = book.sheetnames.index(sheet_name)
        new = book.create_sheet(f"_new_{sheet_name}", index)
        old_headers = {str(cell.value): cell.column for cell in old[1]}
        for new_column, (heading, source_heading) in enumerate(columns, 1):
            source_column = old_headers.get(source_heading)
            heading_cell = new.cell(1, new_column, heading)
            if source_column is not None:
                source_header = old.cell(1, source_column)
                heading_cell._style = copy(source_header._style)
                source_width = old.column_dimensions[get_column_letter(source_column)].width
                new.column_dimensions[get_column_letter(new_column)].width = source_width
                for row in range(2, old.max_row + 1):
                    original = old.cell(row, source_column)
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
        new.freeze_panes = "C2"
        new.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{new.max_row}"
        book.remove(old)
        new.title = sheet_name
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output
