"""Regression checks for the hosted release's source and security boundaries."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask
import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


def test_production_auth_cannot_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale host setting must not expose staff routes in production."""
    from hostapp.security import AuthGuard

    monkeypatch.setenv("ARCHIPELAGO_ENV", "production")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    assert AuthGuard().required() is True


def test_concept_request_does_not_turn_into_a_paper_lookup() -> None:
    """Shared title tokens alone are insufficient for a book-page route."""
    from engine import Engine

    engine = Engine(graph_path=HOST / "fixtures" / "okf_graph.json")
    engine.catalog.reply = lambda _query: {
        "text": "A paper was found.",
        "citation": {"doc_id": "papers/example.pdf", "page_number": 1},
    }
    concept = engine.answer("What are the prerequisites for backpropagation?")
    source = engine.answer("Open the backpropagation paper at page 2")

    assert concept["route"] != "BOOK_PAGE"
    assert source["route"] == "BOOK_PAGE"


def test_requested_dataset_page_is_preserved_without_fake_passage() -> None:
    """An explicit page wins over a passage from another page."""
    from library_index import Catalog

    catalog = Catalog({}, [])
    catalog.best_passage = lambda _query, _hint: {
        "page": 1,
        "text": "A passage from the first page.",
    }
    result = catalog._hf_reply(
        "Open this paper at page 2",
        {"path": "papers/example.pdf", "title": "Example paper"},
    )
    assert result["citation"]["page_number"] == 2
    assert "page=2" in result["citation"]["url"]
    assert "A passage from the first page" not in result["text"]


def test_pearson_export_does_not_claim_physical_copies() -> None:
    """An e-book export has no evidence for a campus shelf count."""
    from engine import catalogue, inventory

    record = catalogue._normalise({"id": "book-1", "title": "Example e-book"})
    card = inventory.shelf_card(record)
    assert record["available_copies"] == 0
    assert "no physical copy" in card.lower()
    assert "physical copy available" not in card.lower()


def test_read_then_submit_is_not_rate_limited() -> None:
    """A harmless GET must not consume the minimum gap for a following POST."""
    from hostapp.security import RateLimiter

    app = Flask(__name__)
    limiter = RateLimiter()
    with app.test_request_context("/api/library/data", method="GET"):
        assert limiter.check_api()[0] is False
    with app.test_request_context("/api/chat/adaptive-step", method="POST"):
        assert limiter.check_api()[0] is False


def test_public_auth_pages_have_no_shared_login_shortcut() -> None:
    """No client-delivered HTML should embed a shared login shortcut."""
    for root in (HOST / "ui", ROOT / "ui" / "chat"):
        for name in ("landing.html", "login.html"):
            html = (root / name).read_text(encoding="utf-8")
            assert "Quick 1-Click Access" not in html
            assert "quickFill(" not in html
            assert "doLandingQuickLogin(" not in html


def test_institutional_marks_are_local_assets() -> None:
    """Landing logos survive a clean checkout without external image hosting."""
    html = (HOST / "ui" / "landing.html").read_text(encoding="utf-8")
    for name in ("iem-logo.png", "uem-logo.png"):
        assert f"/assets/{name}" in html
        assert (HOST / "ui_assets" / name).read_bytes().startswith(b"\x89PNG")
