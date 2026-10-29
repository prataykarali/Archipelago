"""Research transport must authenticate readers and never initiate ingestion."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2] / "host_research"


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    """Load the independent Vercel service from its deployment root."""
    monkeypatch.syspath_prepend(str(ROOT))
    for name in ("app", "discovery", "storage"):
        sys.modules.pop(name, None)
    module = importlib.import_module("app")
    module.app.config["TESTING"] = True
    return module


def test_discovery_has_review_links_and_does_not_write(
    transport: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discovery returns metadata with an explicit unstarted ingestion state."""
    source = importlib.import_module("discovery")
    response = Mock()
    response.json.return_value = {
        "results": [
            {
                "display_name": "Graph systems",
                "doi": "https://doi.org/10.1/example",
                "publication_date": "2026-10-29",
                "abstract_inverted_index": {"Graph": [0], "systems": [1]},
            }
        ]
    }
    get = Mock(return_value=response)
    monkeypatch.setattr(source.requests, "get", get)
    monkeypatch.setattr(
        source.requests, "post", Mock(side_effect=AssertionError("No write allowed"))
    )
    report = source.discover("graph systems")
    assert report["ingestion_status"] == "not_started"
    assert report["scholar_review_url"] == "https://scholar.google.com/scholar?q=graph%20systems"
    assert report["candidates"][0]["source_url"] == "https://doi.org/10.1/example"
    get.assert_called_once()


def test_auth_and_cron_boundary(transport: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary readers need a shared session; Cron needs its separate secret."""
    module = transport
    client = module.app.test_client()
    assert client.get("/api/research/intake/records").status_code == 401
    assert client.get("/api/research/intake/scheduled").status_code == 503
    monkeypatch.setenv("CRON_SECRET", "test-only-secret")
    assert client.get("/api/research/intake/scheduled").status_code == 401
    monkeypatch.setattr(module, "verify_user", lambda token: token == "valid")
    monkeypatch.setattr(module, "recent_records", lambda: [{"title": "Saved paper"}])
    response = client.get("/api/research/intake/records", headers={"Authorization": "Bearer valid"})
    assert response.status_code == 200
    assert response.json["records"][0]["title"] == "Saved paper"


def test_cron_reports_proposals_without_persisting(
    transport: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scheduled call only discovers and returns candidates."""
    module = transport
    monkeypatch.setenv("CRON_SECRET", "test-only-secret")
    discover = Mock(return_value={"ingestion_status": "not_started", "candidates": []})
    monkeypatch.setattr(module, "discover", discover)
    client = module.app.test_client()
    response = client.get(
        "/api/research/intake/scheduled",
        headers={"Authorization": "Bearer test-only-secret"},
    )
    assert response.status_code == 200
    assert response.json["ingestion_status"] == "not_started"
    discover.assert_called_once()
