"""Place source-backed venue rankings beside their papers in librarian responses."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

VENUE_COLUMNS = (
    ("Journal Impact Factor (JIF)", "Journal Impact Factor (JIF)"),
    ("CiteScore", "CiteScore"),
    ("SCImago Journal Rank (SJR)", "SCImago Journal Rank (SJR)"),
    ("Source Normalized Impact per Paper (SNIP)", "Source Normalized Impact per Paper (SNIP)"),
    ("Q1-Q4 Quartile", "Q1-Q4 Quartile"),
    ("CORE/ICORE Rank", "CORE/ICORE Rank"),
    ("h5-index", "h5-index"),
    ("h5-median", "h5-median"),
    ("Venue h-index", "Venue h-index"),
    ("Venue i10-index", "Venue i10-index"),
    ("Acceptance Rate", "Acceptance Rate"),
    ("Indexed Publication Count", "Indexed Publication Count"),
    ("Mean Citedness", "Mean Citedness"),
    ("Indexing Status", "Indexing Status"),
    ("Venue Category", "Category"),
    ("Venue Publisher", "Publisher"),
    ("Venue Official Link", "Official Link"),
    ("Venue Metric Provider", "Metric Provider"),
)


def _venue_key(name: Any) -> str:
    return " ".join(str(name or "").casefold().split())


def merge_preview(preview: dict[str, Any]) -> dict[str, Any]:
    """Append venue values to each paper row and remove the venue-only table."""
    sheets = preview.get("sheets") or {}
    papers = sheets.get("Papers") or {}
    venues = sheets.get("Publications")
    if not venues:
        return preview
    paper_headers = papers.get("headers") or []
    venue_headers = venues.get("headers") or []
    if "Publication Venue" not in paper_headers or "Venue Name" not in venue_headers:
        return preview
    venue_name_index = venue_headers.index("Venue Name")
    venue_rows = {
        _venue_key(row["values"][venue_name_index]): row
        for row in venues.get("rows") or []
        if len(row.get("values") or []) > venue_name_index
    }
    indices = [
        venue_headers.index(source) if source in venue_headers else None
        for _, source in VENUE_COLUMNS
    ]
    original_count = len(paper_headers)
    paper_headers.extend(heading for heading, _ in VENUE_COLUMNS)
    paper_venue_index = paper_headers.index("Publication Venue")
    for paper in papers.get("rows") or []:
        values = paper.get("values") or []
        venue = (
            venue_rows.get(_venue_key(values[paper_venue_index]))
            if len(values) > paper_venue_index
            else None
        )
        source_values = (venue or {}).get("values") or []
        source_links = (venue or {}).get("links") or {}
        for offset, index in enumerate(indices):
            values.append(
                source_values[index] if index is not None and index < len(source_values) else None
            )
            if index is not None and str(index) in source_links:
                paper.setdefault("links", {})[str(original_count + offset)] = source_links[
                    str(index)
                ]
    sheets.pop("Publications", None)
    return preview


def merge_dossier(dossier: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    """Align paper detail ranking values with the merged preview."""
    merged = merge_preview(preview)
    paper_sheet = (merged.get("sheets") or {}).get("Papers") or {}
    rows = paper_sheet.get("rows") or []
    papers = dossier.get("papers") or []
    if len(rows) == len(papers):
        dossier["paper_headers"] = paper_sheet.get("headers") or dossier.get("paper_headers")
        for paper, row in zip(papers, rows, strict=True):
            paper["rankable_values"] = row.get("values") or paper.get("rankable_values")
    dossier.pop("publication_count", None)
    return dossier


def merge_workbook(payload: bytes) -> bytes:
    """Move existing venue values into paper columns in the downloaded workbook."""
    book = load_workbook(BytesIO(payload))
    if "Publications" not in book or "Papers" not in book:
        return payload
    papers = book["Papers"]
    venues = book["Publications"]
    paper_headers = {str(cell.value): cell.column for cell in papers[1]}
    venue_headers = {str(cell.value): cell.column for cell in venues[1]}
    if "Publication Venue" not in paper_headers or "Venue Name" not in venue_headers:
        return payload
    venue_rows = {
        _venue_key(venues.cell(row, venue_headers["Venue Name"]).value): row
        for row in range(2, venues.max_row + 1)
    }
    for heading, source in VENUE_COLUMNS:
        column = papers.max_column + 1
        papers.cell(1, column, heading)
        papers.column_dimensions[get_column_letter(column)].width = 24
        for row in range(2, papers.max_row + 1):
            venue_name = papers.cell(row, paper_headers["Publication Venue"]).value
            venue_row = venue_rows.get(_venue_key(venue_name))
            source_col = venue_headers.get(source)
            if venue_row is None or source_col is None:
                continue
            original = venues.cell(venue_row, source_col)
            target = papers.cell(row, column, original.value)
            if original.hyperlink:
                target.hyperlink = original.hyperlink.target
    papers.auto_filter.ref = f"A1:{get_column_letter(papers.max_column)}{papers.max_row}"
    book.remove(venues)
    if "Start Here" in book:
        for row in book["Start Here"]:
            for cell in row:
                if cell.value == "Publications":
                    cell.value = "Venue metrics"
                elif cell.value == "Standard Research Export (5 sheets)":
                    cell.value = "Standard Research Export (4 sheets)"
                elif isinstance(cell.value, str) and cell.value.startswith("Publications: "):
                    cell.value = cell.value.replace("Publications: ", "Papers venue metric: ", 1)
    output = BytesIO()
    book.save(output)
    return output.getvalue()
