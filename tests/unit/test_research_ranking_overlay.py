"""Verify the librarian keeps venue measurements aligned with paper rows."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

from openpyxl import Workbook, load_workbook
import pytest

from archipelago.scholarly.intelligence.workbook import build_workbook
from archipelago.scholarly.intelligence.workbook_standard import build_standard_workbook
from host_research.ranking_overlay import merge_dossier, merge_preview, merge_workbook
from tests.unit.test_standard_research_xlsx import _sample_run

HOST_RESEARCH = Path(__file__).resolve().parents[2] / "host_research"
if str(HOST_RESEARCH) not in sys.path:
    sys.path.insert(0, str(HOST_RESEARCH))


def _preview() -> dict:
    return {
        "sheets": {
            "Papers": {
                "headers": ["Paper Title", "Publication Year", "Publication Venue"],
                "rows": [
                    {"index": 0, "values": ["One", 2025, "Journal A"], "links": {}},
                    {"index": 1, "values": ["Two", 2026, "Repository B"], "links": {}},
                ],
            },
            "Authors": {
                "headers": ["Author Name"],
                "rows": [
                    {"values": ["Ada"]},
                    {"values": ["Bea"]},
                ],
            },
            "Publications": {
                "headers": ["Venue Name", "Venue h-index", "CiteScore", "Category"],
                "rows": [
                    {"values": ["Journal A", 13, None, "Peer-reviewed journal"], "links": {}},
                    {"values": ["Repository B", None, None, "Preprint repository"], "links": {}},
                ],
            },
        }
    }


def _run() -> dict:
    return {
        "options": {"topic": "One"},
        "retrieved_at": "2026-11-17T00:00:00Z",
        "papers": [
            {
                "paper_id": "1",
                "title": "One",
                "year": 2025,
                "venue": "Journal A",
                "authors": [{"name": "Ada"}, {"name": "Bea"}],
                "source_metadata": {"author_openalex_ids": ["A1", "A2"]},
                "provenance": [{"source_type": "openalex"}],
                "oa_url": "https://example.org/full",
            },
            {
                "paper_id": "2",
                "title": "Two",
                "year": 2026,
                "venue": "Repository B",
                "authors": [{"name": "Bea"}],
                "source_metadata": {"author_openalex_ids": ["A2"]},
                "provenance": [{"source_type": "arxiv"}],
            },
        ],
    }


def test_preview_and_dossier_move_verified_venue_fields_to_papers() -> None:
    dossier = {
        "paper_headers": ["Paper Title", "Publication Year", "Publication Venue"],
        "papers": [
            {"rankable_values": ["One", 2025, "Journal A"]},
            {"rankable_values": ["Two", 2026, "Repository B"]},
        ],
        "publication_count": 2,
    }
    merged = merge_dossier(dossier, _preview(), _run())
    assert "publication_count" not in merged
    assert merged["paper_headers"].index("Venue h-index") > 1
    h_index = merged["paper_headers"].index("Venue h-index")
    scoped = merged["paper_headers"].index("Venue Papers in This Search")
    assert merged["papers"][0]["rankable_values"][h_index] == 13
    assert merged["papers"][1]["rankable_values"][h_index] is None
    assert merged["papers"][0]["rankable_values"][scoped] == 1
    assert (
        merged["papers"][0]["rankable_values"][
            merged["paper_headers"].index("Title Query Match (%)")
        ]
        == 100
    )
    preview = merge_preview(_preview(), _run())
    assert "Publications" not in preview["sheets"]
    author_headers = preview["sheets"]["Authors"]["headers"]
    assert (
        preview["sheets"]["Authors"]["rows"][1]["values"][
            author_headers.index("Papers in This Search")
        ]
        == 2
    )


def test_xlsx_moves_venue_values_and_removes_publications_sheet() -> None:
    book = Workbook()
    papers = book.active
    assert papers is not None
    papers.title = "Papers"
    papers.append(["Paper Title", "Publication Year", "Publication Venue"])
    papers.append(["One", 2025, "Journal A"])
    authors = book.create_sheet("Authors")
    authors.append(["Author Name"])
    authors.append(["Ada"])
    venues = book.create_sheet("Publications")
    venues.append(["Venue Name", "Venue h-index", "CiteScore"])
    venues.append(["Journal A", 13, None])
    output = BytesIO()
    book.save(output)
    merged = load_workbook(BytesIO(merge_workbook(output.getvalue(), _run())))
    assert merged.sheetnames == ["Papers", "Authors"]
    headers = [cell.value for cell in merged["Papers"][1]]
    assert merged["Papers"].cell(2, headers.index("Venue h-index") + 1).value == 13
    assert (
        merged["Papers"]
        .cell(2, headers.index("Venue Public Full-Text Links in This Search") + 1)
        .value
        == 1
    )
    assert "CiteScore" not in headers


def test_production_overlay_agrees_with_canonical_export() -> None:
    run = _sample_run()
    old_payload = build_standard_workbook(run).getvalue()
    live = load_workbook(BytesIO(merge_workbook(old_payload, run)))
    canonical = load_workbook(BytesIO(build_workbook(run, mode="standard").getvalue()))
    for sheet_name in ("Papers", "Authors"):
        live_headers = [cell.value for cell in live[sheet_name][1]]
        canonical_headers = [cell.value for cell in canonical[sheet_name][1]]
        for live_row, canonical_row in zip(
            live[sheet_name].iter_rows(min_row=2, values_only=True),
            canonical[sheet_name].iter_rows(min_row=2, values_only=True),
            strict=True,
        ):
            for heading in (
                "Paper Age (Years)",
                "Title Query Match (%)",
                "Venue Papers in This Search",
                "Papers in This Search",
                "Distinct Coauthor Bylines in This Search",
            ):
                if heading in live_headers:
                    assert (
                        live_row[live_headers.index(heading)]
                        == canonical_row[canonical_headers.index(heading)]
                    )


def test_standard_export_proxy_marks_current_schema_and_cannot_return_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from host_research import app as research_app

    run = _sample_run()
    old_payload = build_standard_workbook(run).getvalue()
    monkeypatch.setattr(
        research_app.requests,
        "request",
        lambda *args, **kwargs: SimpleNamespace(
            ok=True,
            status_code=200,
            content=old_payload,
            headers={
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            },
        ),
    )
    monkeypatch.setattr(
        research_app.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(ok=True, json=lambda: run),
    )
    with research_app.app.test_request_context(
        "/api/research/intelligence/runs/11111111-1111-1111-1111-111111111111/xlsx?mode=standard"
    ):
        response = research_app._forward(
            "/api/research/intelligence/runs/11111111-1111-1111-1111-111111111111/xlsx"
        )
    assert response.status_code == 200
    assert response.headers["X-Archipelago-Export-Schema"] == "paper-venue-v2"
    assert response.cache_control.no_store
    workbook = load_workbook(BytesIO(response.get_data()), read_only=True)
    assert "Publications" not in workbook.sheetnames
    assert "Venue h-index" in [cell.value for cell in workbook["Papers"][1]]
