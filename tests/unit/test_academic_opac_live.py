"""Check public OPAC parsing and the staff authentication boundary."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import pytest

HOST_RESEARCH = Path(__file__).resolve().parents[2] / "host_research"
sys.path.insert(0, str(HOST_RESEARCH))

from opac_daily import fetch_daily_opac  # noqa: E402
from opac_live import lookup_book  # noqa: E402

import app as research_app  # noqa: E402


@pytest.mark.unit
def test_live_lookup_requires_staff_token() -> None:
    """The live proxy does not offer an unauthenticated scraping endpoint."""
    response = research_app.app.test_client().get("/api/library/opac/live?q=deep+learning")
    assert response.status_code == 401


@pytest.mark.unit
def test_live_lookup_rejects_invalid_book_id() -> None:
    """Only a numeric Koha biblionumber may select a detail record."""
    with pytest.raises(ValueError, match="Invalid Koha book ID"):
        lookup_book("../../private")


@pytest.mark.unit
def test_daily_reader_keeps_source_links_and_checksums() -> None:
    """A bounded daily read preserves links and identifies source changes."""
    from bs4 import BeautifulSoup

    def fake_fetch(path: str, params: dict[str, str]) -> tuple[BeautifulSoup, str]:
        if path.endswith("opac-page.pl"):
            page_id = params["page_id"]
            html = f'<div id="page_{page_id}"><h1>Section</h1><a href="/one">Read more</a></div>'
            return BeautifulSoup(
                html, "html.parser"
            ), f"https://uemk-opac.l2c2.co.in{path}?page_id={page_id}"
        html = '<div class="searchresults"><a class="title" href="/cgi-bin/koha/opac-detail.pl?biblionumber=4671">Book</a></div>'
        return BeautifulSoup(
            html, "html.parser"
        ), "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-search.pl?q=copydate%3A2025"

    with (
        patch("opac_daily._fetch", side_effect=fake_fetch),
        patch("opac_daily._arrivals_query", return_value={"q": "copydate:2025"}),
    ):
        snapshot = fetch_daily_opac()
    assert len(snapshot["sections"]) == 4
    assert snapshot["new_arrivals"][0]["biblionumber"] == "4671"
    assert snapshot["sections"][0]["links"][0]["url"] == "https://uemk-opac.l2c2.co.in/one"
    assert len(snapshot["sha256"]) == 64
