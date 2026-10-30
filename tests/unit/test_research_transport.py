"""Research transport must authenticate readers and never initiate ingestion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib
import os
from pathlib import Path
import sys
from unittest.mock import Mock
import zipfile

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
    assert report["papers"][0]["source_name"] == "OpenAlex"
    get.assert_called_once()


def test_auth_and_cron_boundary(transport: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary readers need a shared session; Cron needs its separate secret."""
    module = transport
    client = module.app.test_client()
    assert client.get("/api/research/intake/records").status_code == 401
    assert client.get("/api/research/intake/scheduled").status_code == 503
    monkeypatch.setenv("CRON_SECRET", "test-only-secret")
    assert client.get("/api/research/intake/scheduled").status_code == 401
    monkeypatch.setattr(
        module,
        "verify_user",
        lambda token: (
            {"id": "staff-id", "role": "faculty", "username": "staff"} if token == "valid" else None
        ),
    )
    upstream = Mock()
    upstream.status_code = 200
    upstream.content = b'{"records":[{"title":"Saved paper"}]}'
    upstream.headers = {"Content-Type": "application/json"}
    request_upstream = Mock(return_value=upstream)
    monkeypatch.setattr(module.requests, "request", request_upstream)
    response = client.get("/api/research/intake/records", headers={"Authorization": "Bearer valid"})
    assert response.status_code == 200
    assert response.json["records"][0]["title"] == "Saved paper"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert request_upstream.call_args.kwargs["headers"]["Authorization"] == "Bearer valid"
    assert (
        client.get("/api/auth/me", headers={"Authorization": "Bearer valid"}).json["role"]
        == "faculty"
    )
    assert b"Ingest 25 papers locally" in client.get("/research").data
    assert client.get("/research/progress").status_code == 200
    assert client.get("/research/paper").status_code == 200
    assert client.get("/research_home.js").status_code == 200
    assert client.get("/academic/graph").status_code == 200
    assert (
        client.post("/api/research/jobs", headers={"Authorization": "Bearer valid"}).status_code
        == 200
    )
    assert request_upstream.call_args.args[0] == "POST"


def test_students_cannot_read_research(transport: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid account without a staff profile is denied research data."""
    module = transport
    monkeypatch.setattr(module, "verify_user", lambda token: None)
    response = module.app.test_client().get(
        "/api/research/topics", headers={"Authorization": "Bearer student-token"}
    )
    assert response.status_code == 401


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


def test_koha_snapshot_is_dated_and_keeps_all_four_exports(
    transport: object, tmp_path: Path
) -> None:
    """A valid ODS set becomes metadata with a visible stale-source flag."""
    koha = importlib.import_module("koha_snapshot")
    table_ns = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    text_ns = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    old = (datetime.now(UTC) - timedelta(days=4)).timestamp()

    def cells(values: list[str] | tuple[str, ...]) -> str:
        return "".join(
            f"<table:table-cell><text:p>{value}</text:p></table:table-cell>" for value in values
        )

    for kind, filename in koha.FILES.items():
        xml = (
            f'<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            f'xmlns:table="{table_ns}" xmlns:text="{text_ns}">'
            f"<table:table><table:table-row>{cells(koha.HEADERS[kind])}</table:table-row>"
            f"<table:table-row>{cells(['Example'] * len(koha.HEADERS[kind]))}</table:table-row>"
            "</table:table></office:document-content>"
        )
        path = tmp_path / filename
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("content.xml", xml)
        os.utime(path, (old, old))
    snapshot = koha.build_snapshot(tmp_path)
    assert snapshot["stale"] is True
    assert all(len(snapshot[kind]) == 1 for kind in koha.FILES)
    assert all(snapshot["exports"][kind]["sha256"] for kind in koha.FILES)
