"""Library browsing uses verified catalogue data without demo substitutions."""

from __future__ import annotations

from flask import Flask
import pytest

from host_inference.hostapp.config import PUBLIC_API
from host_inference.hostapp.koha_bridge import public_holdings
from host_inference.hostapp.routes import library

pytestmark = pytest.mark.unit


def test_public_holdings_have_exact_opac_sources() -> None:
    """A Koha ID becomes a citable detail link with bounded copy counts."""
    snapshot = {
        "holdings": [
            {
                "biblionumber": "4671",
                "Title": "Deep Learning",
                "Author": "R. Ramalakshmi",
                "Publisher": "Cengage",
                "Accn Nos.": "40630",
                "No. of copies": "10",
                "Available Copies": "9",
                "isbn": "9789366606606",
                "call_number": "006.31 RAM",
            }
        ]
    }
    rows = public_holdings(snapshot)
    assert rows[0]["available_ratio"] == "9 / 10"
    assert rows[0]["isbn"] == "9789366606606"
    assert rows[0]["opac_url"].endswith("biblionumber=4671")


def test_library_data_uses_snapshot_without_sample_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """The open Library endpoint serves real shelf and dated Koha records."""
    monkeypatch.setattr(
        library,
        "load_library_manifest",
        lambda: {
            "ebook_shelf": [{"id": "reader-book", "title": "Verified reader book"}],
            "holdings": [],
        },
    )
    monkeypatch.setattr(library, "load_inventory", lambda: None)
    monkeypatch.setattr(
        library,
        "load_koha_snapshot",
        lambda: {
            "source": "authorized_koha_ods_export",
            "source_updated_at": "2026-10-03T00:00:00+00:00",
            "stale": True,
            "opac_daily": {"sections": [], "new_arrivals": []},
            "holdings": [
                {
                    "biblionumber": "4671",
                    "Title": "Deep Learning",
                    "No. of copies": "1",
                    "Available Copies": "1",
                }
            ],
        },
    )
    app = Flask(__name__)
    library.register(app, None)  # type: ignore[arg-type]
    response = app.test_client().get("/api/library/data")
    assert response.status_code == 200
    assert response.json["ebook_shelf"][0]["id"] == "reader-book"
    assert response.json["holdings_status"] == "koha_export"
    assert len(response.json["holdings"]) == 1
    assert "/api/library/data" in PUBLIC_API
