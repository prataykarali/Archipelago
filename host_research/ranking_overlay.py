"""Show search-scoped rankings consistently in librarian previews and Excel."""

from __future__ import annotations

from copy import copy
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

if __package__:
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
else:
    from search_rankings import (
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

REMOVED_PAPER_COLUMNS = frozenset(
    {
        "Journal Impact Factor (JIF)",
        "CiteScore",
        "SCImago Journal Rank (SJR)",
        "Source Normalized Impact per Paper (SNIP)",
        "Q1-Q4 Quartile",
        "CORE/ICORE Rank",
        "h5-index",
        "h5-median",
        "Acceptance Rate",
    }
)
REMOVED_AUTHOR_COLUMNS = frozenset(
    {
        "g-index",
        "Median Citations per Paper",
        "Field-Normalized Impact",
    }
)
VENUE_COLUMNS = (
    "Venue h-index",
    "Venue i10-index",
    "Indexed Publication Count",
    "Mean Citedness",
    "Indexing Status",
    "Category",
    "Publisher",
    "Official Link",
    "Metric Provider",
)
VENUE_RENAMES = {
    "Category": "Venue Category",
    "Publisher": "Venue Publisher",
    "Official Link": "Venue Official Link",
    "Metric Provider": "Venue Metric Provider",
}


def _key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _index(headers: list[str], *names: str) -> int | None:
    return next((headers.index(name) for name in names if name in headers), None)


def _paper_metrics(
    row: dict[str, Any],
    headers: list[str],
    run: dict[str, Any],
    selected: list[dict[str, Any]],
) -> dict[str, Any]:
    values = row.get("values") or []
    title_index = _index(headers, "Paper Title", "Paper title")
    year_index = _index(headers, "Publication Year", "Year")
    title = values[title_index] if title_index is not None else ""
    year = values[year_index] if year_index is not None else None
    paper = matching_paper(title, year, run.get("papers") or [])
    if paper is None:
        return {}
    topic = str((run.get("options") or {}).get("topic") or "")
    return {
        **paper_values(paper, topic, ranking_year(run)),
        **venue_values(str(paper.get("venue") or ""), selected, topic),
    }


def _filter_row(row: dict[str, Any], keep: list[int]) -> None:
    values = row.get("values") or []
    links = row.get("links") or {}
    row["values"] = [values[index] if index < len(values) else None for index in keep]
    row["links"] = {
        str(offset): links[str(index)] for offset, index in enumerate(keep) if str(index) in links
    }


def merge_preview(preview: dict[str, Any], run: dict[str, Any] | None = None) -> dict[str, Any]:
    """Put venue and derived metrics beside papers, and remove empty columns."""
    sheets = preview.get("sheets") or {}
    paper_sheet = sheets.get("Papers") or {}
    author_sheet = sheets.get("Authors") or {}
    venue_sheet = sheets.get("Publications") or {}
    old_headers = list(paper_sheet.get("headers") or [])
    if not venue_sheet and all(heading in old_headers for heading in PAPER_FIELDS):
        return preview
    venue_headers = venue_sheet.get("headers") or []
    venue_name_index = _index(venue_headers, "Venue Name", "Venue name")
    venue_rows = {
        _key(row["values"][venue_name_index]): row
        for row in venue_sheet.get("rows") or []
        if venue_name_index is not None and len(row.get("values") or []) > venue_name_index
    }
    keep = [
        index for index, heading in enumerate(old_headers) if heading not in REMOVED_PAPER_COLUMNS
    ]
    selected = []
    title_index = _index(old_headers, "Paper Title", "Paper title")
    if run and title_index is not None:
        year_index = _index(old_headers, "Publication Year", "Year")
        for row in paper_sheet.get("rows") or []:
            values = row.get("values") or []
            title = values[title_index] if len(values) > title_index else ""
            year = (
                values[year_index] if year_index is not None and len(values) > year_index else None
            )
            paper = matching_paper(title, year, run.get("papers") or [])
            if paper is not None:
                selected.append(paper)
    author_keys = ordered_author_keys(selected)
    added = (
        *PAPER_FIELDS,
        *VENUE_FIELDS,
        *(VENUE_RENAMES.get(name, name) for name in VENUE_COLUMNS),
    )
    paper_sheet["headers"] = [old_headers[index] for index in keep] + list(added)
    venue_index = _index(old_headers, "Publication Venue", "Publication venue")
    for row in paper_sheet.get("rows") or []:
        original = row.get("values") or []
        venue_name = (
            original[venue_index] if venue_index is not None and len(original) > venue_index else ""
        )
        venue_row = venue_rows.get(_key(venue_name)) or {}
        venue_values_row = venue_row.get("values") or []
        venue_links = venue_row.get("links") or {}
        calculated = _paper_metrics(row, old_headers, run, selected) if run else {}
        _filter_row(row, keep)
        for heading in (*PAPER_FIELDS, *VENUE_FIELDS):
            row["values"].append(calculated.get(heading))
        for name in VENUE_COLUMNS:
            index = venue_headers.index(name) if name in venue_headers else None
            column = len(row["values"])
            row["values"].append(
                venue_values_row[index]
                if index is not None and index < len(venue_values_row)
                else None
            )
            if index is not None and str(index) in venue_links:
                row["links"][str(column)] = venue_links[str(index)]
    author_headers = list(author_sheet.get("headers") or [])
    author_keep = [
        index
        for index, heading in enumerate(author_headers)
        if heading not in REMOVED_AUTHOR_COLUMNS
    ]
    author_sheet["headers"] = [author_headers[index] for index in author_keep] + list(AUTHOR_FIELDS)
    for author_number, row in enumerate(author_sheet.get("rows") or []):
        original = row.get("values") or []
        name_index = _index(author_headers, "Author Name", "Author name")
        name = original[name_index] if name_index is not None and len(original) > name_index else ""
        _filter_row(row, author_keep)
        identity_key = author_keys[author_number] if author_number < len(author_keys) else None
        values = (
            author_values(
                str(name),
                selected,
                str((run.get("options") or {}).get("topic") or ""),
                identity_key,
            )
            if run
            else {}
        )
        row["values"].extend(values.get(heading) for heading in AUTHOR_FIELDS)
    sheets.pop("Publications", None)
    return preview


def merge_dossier(
    dossier: dict[str, Any], preview: dict[str, Any], run: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Align each paper page with exactly the preview and Excel columns."""
    merged = merge_preview(preview, run)
    sheet = (merged.get("sheets") or {}).get("Papers") or {}
    rows = sheet.get("rows") or []
    papers = dossier.get("papers") or []
    if len(rows) == len(papers):
        dossier["paper_headers"] = sheet.get("headers") or dossier.get("paper_headers")
        for paper, row in zip(papers, rows, strict=True):
            paper["rankable_values"] = row.get("values") or paper.get("rankable_values")
    dossier.pop("publication_count", None)
    return dossier


def merge_workbook(payload: bytes, run: dict[str, Any] | None = None) -> bytes:
    """Apply the same ranking schema to the downloaded standard workbook."""
    book = load_workbook(BytesIO(payload))
    if "Publications" not in book or "Papers" not in book:
        return payload
    preview: dict[str, Any] = {"sheets": {}}
    for name in ("Papers", "Authors", "Publications"):
        sheet = book[name]
        preview["sheets"][name] = {
            "headers": [str(cell.value or "") for cell in sheet[1]],
            "rows": [
                {
                    "values": [cell.value for cell in cells],
                    "links": {
                        str(index): cell.hyperlink.target
                        for index, cell in enumerate(cells)
                        if cell.hyperlink
                        and cell.hyperlink.target
                        and cell.hyperlink.target.startswith("https://")
                    },
                }
                for cells in sheet.iter_rows(min_row=2)
            ],
        }
    merged = merge_preview(preview, run)
    for name in ("Papers", "Authors"):
        sheet = book[name]
        current = merged["sheets"][name]
        heading_style = copy(sheet.cell(1, 1)._style)
        row_styles = {
            row_number: copy(sheet.cell(row_number, 1)._style)
            for row_number in range(2, sheet.max_row + 1)
        }
        sheet.delete_cols(1, sheet.max_column)
        for column, heading in enumerate(current["headers"], 1):
            cell = sheet.cell(1, column, heading)
            cell._style = copy(heading_style)
            sheet.column_dimensions[get_column_letter(column)].width = 24
        for row_number, row in enumerate(current["rows"], 2):
            for column, value in enumerate(row["values"], 1):
                cell = sheet.cell(row_number, column, value)
                cell._style = copy(row_styles[row_number])
                link = (row.get("links") or {}).get(str(column - 1))
                if link:
                    cell.hyperlink = link
        sheet.auto_filter.ref = f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}"
    book.remove(book["Publications"])
    if "Start Here" in book:
        for cells in book["Start Here"]:
            for cell in cells:
                if cell.value == "Publications":
                    cell.value = "Venue metrics on Papers"
                elif cell.value == "Standard Research Export (5 sheets)":
                    cell.value = "Standard Research Export (4 sheets)"
                elif isinstance(cell.value, str) and cell.value.startswith("Publications: "):
                    cell.value = cell.value.replace("Publications: ", "Papers venue metric: ", 1)
    output = BytesIO()
    book.save(output)
    return output.getvalue()
