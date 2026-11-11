"""Daily campus snapshots never retire pages after a transient source failure."""

from __future__ import annotations

from pathlib import Path
import sys

import requests

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp import research_campus_sync as campus  # noqa: E402


def test_sync_retirement_requires_explicit_gone_and_complete_sitemap(monkeypatch) -> None:
    current = "https://iem.edu.in/library/"
    missing = "https://iem.edu.in/old-library/"
    rows = [
        {
            "record_key": "old",
            "source_url": missing,
            "metadata": {"sync_scope": "campus_public", "active": True},
        }
    ]
    retired: list[str] = []
    monkeypatch.setattr(
        campus,
        "fetch_college_page",
        lambda url, user: {
            "record_key": "current",
            "source_url": url,
            "metadata": {"source_timestamp": "2026-10-21T00:00:00Z"},
        },
    )
    monkeypatch.setattr(campus, "save_records", lambda records: len(records))
    monkeypatch.setattr(campus, "list_managed_college_records", lambda: rows)
    monkeypatch.setattr(
        campus, "retire_record", lambda row, checked: retired.append(row["record_key"])
    )
    monkeypatch.setattr(campus, "_confirmed_gone", lambda url: False)
    report = campus.sync_public_campus_pages([current], complete_sitemap=True)
    assert report["saved"] == 1
    assert report["retired"] == 0
    assert not retired
    monkeypatch.setattr(campus, "_confirmed_gone", lambda url: True)
    report = campus.sync_public_campus_pages([current], complete_sitemap=False)
    assert report["retired"] == 0
    report = campus.sync_public_campus_pages([current], complete_sitemap=True)
    assert report["retired"] == 1
    assert retired == ["old"]


def test_sync_keeps_timed_out_page(monkeypatch) -> None:
    url = "https://iem.edu.in/library/"
    monkeypatch.setattr(
        campus,
        "fetch_college_page",
        lambda *_args: (_ for _ in ()).throw(requests.Timeout("timed out")),
    )
    monkeypatch.setattr(campus, "_confirmed_gone", lambda _url: False)
    monkeypatch.setattr(campus, "save_records", lambda records: len(records))
    monkeypatch.setattr(campus, "list_managed_college_records", lambda: [])
    report = campus.sync_public_campus_pages([url], complete_sitemap=True)
    assert report["saved"] == 0
    assert report["retired"] == 0
    assert report["errors"][0]["error"] == "Timeout"
