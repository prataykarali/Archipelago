"""Verify the librarian keeps venue measurements aligned with paper rows."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook, load_workbook

from host_research.ranking_overlay import merge_dossier, merge_preview, merge_workbook


def _preview() -> dict:
    return {
        "sheets": {
            "Papers": {
                "headers": ["Paper Title", "Publication Venue"],
                "rows": [
                    {"index": 0, "values": ["One", "Journal A"], "links": {}},
                    {"index": 1, "values": ["Two", "Repository B"], "links": {}},
                ],
            },
            "Authors": {"headers": ["Author Name"], "rows": []},
            "Publications": {
                "headers": ["Venue Name", "Venue h-index", "CiteScore", "Category"],
                "rows": [
                    {"values": ["Journal A", 13, None, "Peer-reviewed journal"], "links": {}},
                    {"values": ["Repository B", None, None, "Preprint repository"], "links": {}},
                ],
            },
        }
    }


def test_preview_and_dossier_move_verified_venue_fields_to_papers() -> None:
    dossier = {
        "paper_headers": ["Paper Title", "Publication Venue"],
        "papers": [
            {"rankable_values": ["One", "Journal A"]},
            {"rankable_values": ["Two", "Repository B"]},
        ],
        "publication_count": 2,
    }
    merged = merge_dossier(dossier, _preview())
    assert "publication_count" not in merged
    assert merged["paper_headers"].index("Venue h-index") > 1
    h_index = merged["paper_headers"].index("Venue h-index")
    citescore = merged["paper_headers"].index("CiteScore")
    assert merged["papers"][0]["rankable_values"][h_index] == 13
    assert merged["papers"][1]["rankable_values"][h_index] is None
    assert merged["papers"][0]["rankable_values"][citescore] is None
    preview = merge_preview(_preview())
    assert "Publications" not in preview["sheets"]


def test_xlsx_moves_venue_values_and_removes_publications_sheet() -> None:
    book = Workbook()
    papers = book.active
    assert papers is not None
    papers.title = "Papers"
    papers.append(["Paper Title", "Publication Venue"])
    papers.append(["One", "Journal A"])
    venues = book.create_sheet("Publications")
    venues.append(["Venue Name", "Venue h-index", "CiteScore"])
    venues.append(["Journal A", 13, None])
    output = BytesIO()
    book.save(output)
    merged = load_workbook(BytesIO(merge_workbook(output.getvalue())))
    assert merged.sheetnames == ["Papers"]
    headers = [cell.value for cell in merged["Papers"][1]]
    assert merged["Papers"].cell(2, headers.index("Venue h-index") + 1).value == 13
    assert merged["Papers"].cell(2, headers.index("CiteScore") + 1).value is None
