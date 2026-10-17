"""Apify datasets only publish source-linked institutional records."""

from __future__ import annotations

import pytest

from archipelago.ingestion import institutional_apify as source

pytestmark = pytest.mark.unit


def test_opac_requires_biblionumber_and_official_host() -> None:
    items = [
        {
            "url": "http://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-search.pl",
            "markdown": (
                "[Algorithms](opac-detail.pl?biblionumber=123) "
                "[Unverified](https://example.com/?biblionumber=456) "
                "[Home](https://uemk-opac.l2c2.co.in/)"
            ),
        }
    ]
    records = source.extract_public_records("opac", items)
    assert len(records) == 1
    assert records[0]["source_record_id"] == "123"
    assert records[0]["kind"] == "catalog_book"
    assert records[0]["availability"] == "unknown"


def test_iem_navigation_is_never_called_a_holding() -> None:
    items = [
        {
            "url": source.IEM_PORTAL,
            "markdown": "[Digital Library](/iemEn/library.jsp)",
        }
    ]
    records = source.extract_public_records("iemcrp", items)
    assert len(records) == 1
    assert records[0]["kind"] == "resource_link"
    assert records[0]["availability"] == "unknown"


def test_challenge_and_wrong_source_page_produce_no_records() -> None:
    assert not source.extract_public_records(
        "opac",
        [{"url": "https://example.com/", "markdown": "[Book](?biblionumber=123)"}],
    )
    assert not source.extract_public_records(
        "iemcrp",
        [{"url": source.IEM_PORTAL, "markdown": "cf-turnstile [Book](/iemEn/book.jsp)"}],
    )


def test_actor_success_without_records_is_not_live(monkeypatch) -> None:
    monkeypatch.setattr(
        source,
        "actor_run_status",
        lambda _run_id: {"status": "SUCCEEDED", "dataset_id": "dataset-one"},
    )
    monkeypatch.setattr(source, "fetch_dataset_items", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(source, "actor_failure_state", lambda _run_id: None)
    report = source.probe_public_source("iemcrp", run_id="run-one")
    assert report["source_status"] == "no_usable_records"
    assert report["dataset_items"] == 0


def test_actor_pending_is_not_live(monkeypatch) -> None:
    monkeypatch.setattr(
        source, "actor_run_status", lambda _run_id: {"status": "RUNNING", "dataset_id": "d"}
    )
    assert source.probe_public_source("opac", run_id="run-one")["source_status"] == "pending"
