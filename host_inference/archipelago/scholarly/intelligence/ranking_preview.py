"""Expose the same three ranking sheets used by the standard Excel export."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Any

from openpyxl import load_workbook

from .workbook import build_workbook

RANKING_SHEETS = ("Papers", "Authors", "Publications")


def preview_workbook(workbook: BytesIO, topic: str, retrieved_at: str) -> dict[str, Any]:
    """Read visible values and safe source links from a standard workbook."""
    workbook.seek(0)
    book = load_workbook(workbook, data_only=True)
    sheets: dict[str, dict[str, Any]] = {}
    for name in RANKING_SHEETS:
        sheet = book[name]
        headers = [str(cell.value or "") for cell in sheet[1]]
        rows: list[dict[str, Any]] = []
        for index, cells in enumerate(sheet.iter_rows(min_row=2)):
            values = [
                value.isoformat() if isinstance(value := cell.value, (date, datetime)) else value
                for cell in cells
            ]
            if not any(value is not None for value in values):
                continue
            links = {
                str(index): cell.hyperlink.target
                for index, cell in enumerate(cells)
                if cell.hyperlink is not None
                and cell.hyperlink.target
                and cell.hyperlink.target.startswith("https://")
            }
            rows.append({"index": index, "values": values, "links": links})
        sheets[name] = {"headers": headers, "rows": rows}
    book.close()
    return {"topic": topic, "retrieved_at": retrieved_at, "sheets": sheets}


def preview_run(run: dict[str, Any]) -> dict[str, Any]:
    """Build a rankable preview using the export's exact cleansing rules."""
    return preview_workbook(
        build_workbook(run, mode="standard"),
        str((run.get("options") or {}).get("topic") or "Research"),
        str(run.get("retrieved_at") or ""),
    )
