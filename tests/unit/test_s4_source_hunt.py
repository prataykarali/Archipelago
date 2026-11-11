"""Live catalog discovery must match exact sources and never imply full-text access."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

from bs4 import BeautifulSoup
import pytest

from archipelago.academic_automation import discovery, external_sources, worker
from archipelago.academic_automation.store import AcademicStore

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "host_research"))

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(
        self, payload: dict[str, Any] | None = None, content: bytes = b"", status: int = 200
    ):
        self._payload = payload or {}
        self.content = content
        self.status_code = status
        self.is_redirect = False

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400 and self.status_code != 404:
            raise ValueError("HTTP error")


def _record(**changes: Any) -> dict[str, Any]:
    row = {
        "biblionumber": "4131",
        "title": "Statistics for Machine Learning Implement Statistical methods using Python",
        "author": "Himanshu Singh",
        "isbn": "9789388511971",
        "holdings": [{"item_type": "Reference Book (RB)", "status": "Available"}],
        "source_url": "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber=4131",
        "fetched_at": "2026-11-11T00:00:00Z",
    }
    row.update(changes)
    return row


def test_open_library_exact_isbn_toc_and_no_full_book_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(_url: str, **_kwargs: Any) -> FakeResponse:
        return FakeResponse(
            {
                "ISBN:9789388511971": {
                    "details": {
                        "key": "/books/OL62107887M",
                        "title": "Statistics for Machine Learning",
                        "isbn_13": ["9789388511971"],
                        "table_of_contents": [{"title": "Probability"}, {"title": "Regression"}],
                    }
                }
            }
        )

    monkeypatch.setattr(external_sources.requests, "get", fake_get)
    result = external_sources.open_library_edition(_record()["isbn"], _record()["title"])
    assert result is not None
    assert result["status"] == "catalog_metadata"
    assert [item["title"] for item in result["table_of_contents"]] == ["Probability", "Regression"]
    assert "text" not in result


def test_wrong_book_isbn_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        external_sources.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(
            {
                "ISBN:9789388511971": {
                    "details": {
                        "key": "/books/OL62107887M",
                        "title": "Other book",
                        "isbn_13": ["9780000000000"],
                    }
                }
            }
        ),
    )
    assert external_sources.open_library_edition("9789388511971", _record()["title"]) is None


def test_academic_cpu_fallback_passes_num_gpu_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared Ollama path must keep a CPU request off the GPU."""
    from okf.extraction import part02_is_local_mode as extraction

    observed: dict[str, Any] = {}

    def fake_chat(**kwargs: Any) -> SimpleNamespace:
        observed.update(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(
                content='[{"concept_name":"Linear Regression","summary":"A linear model fits a numeric target."}]'
            )
        )

    monkeypatch.setenv("ARCHIPELAGO_INGESTION_MODEL", "lib-qwen:latest")
    monkeypatch.setenv("ARCHIPELAGO_ACADEMIC_CPU_ONLY", "1")
    monkeypatch.setattr(extraction.ollama, "chat", fake_chat)
    extraction.extract_okf_v15(
        "Linear regression fits a numerical target.", "test", "chunk", 1, "Basics"
    )
    assert observed["options"]["num_gpu"] == 0
    assert observed["model"] == "lib-qwen:latest"


def test_opac_live_query_records_toc_without_queuing_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import opac_live

    store = AcademicStore(tmp_path / "ledger.sqlite3")
    monkeypatch.setattr(
        opac_live,
        "search_books_page",
        lambda *_args, **_kwargs: {
            "results": [{"biblionumber": "4131"}],
            "next_offset": 20,
            "fetched_at": "2026-11-11T00:00:00Z",
        },
    )
    monkeypatch.setattr(opac_live, "lookup_book", lambda _id: _record())
    monkeypatch.setattr(
        discovery,
        "open_library_edition",
        lambda *_args: {
            "provider": "open_library",
            "source_id": "/books/OL62107887M",
            "source_url": "https://openlibrary.org/books/OL62107887M",
            "title": "Statistics for Machine Learning",
            "isbn": "9789388511971",
            "license": "CC0-1.0",
            "table_of_contents": [{"title": "Probability"}, {"title": "Regression"}],
            "retrieved_at": "2026-11-11T00:00:00Z",
        },
    )
    result = discovery.discover_opac_query(store, tmp_path, "machine learning")
    assert result["next_offset"] == 20
    assert result["records"][0]["job_ids"] == []
    evidence = store.dashboard()["source_evidence"][0]
    assert evidence["content_status"] == "table_of_contents_only"
    assert evidence["eligible_extraction"] == 0
    assert evidence["opac_source_url"].endswith("biblionumber=4131")
    assert worker.run_once(store, tmp_path) is None
    _record_update = _record(fetched_at="2026-11-12T00:00:00Z")
    from archipelago.academic_automation.reconcile import reconcile

    assert reconcile(store, "opac_live", [_record_update])["counts"] == {"unchanged": 1}


def test_journal_holding_does_not_turn_into_article_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = AcademicStore(tmp_path / "ledger.sqlite3")
    from archipelago.academic_automation.reconcile import reconcile

    journal = _record(
        isbn="",
        title="International Journal of Game Theory",
        holdings=[{"item_type": "Journal (J)"}],
    )
    reconcile(store, "opac_live", [journal])
    monkeypatch.setattr(
        discovery, "crossref_article", lambda *_args: pytest.fail("journal matched to article")
    )
    result = discovery.hunt_record(store, tmp_path, journal)
    assert result["kind"] == "journal"
    assert result["job_ids"] == []


def test_exact_article_licensed_text_queues_one_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = AcademicStore(tmp_path / "ledger.sqlite3")
    from archipelago.academic_automation.reconcile import reconcile

    paper = _record(isbn="", title="Attention Is All You Need", holdings=[])
    reconcile(store, "opac_live", [paper])
    monkeypatch.setattr(
        discovery,
        "crossref_article",
        lambda *_args: {
            "provider": "crossref",
            "source_id": "10.1234/paper",
            "source_url": "https://doi.org/10.1234/paper",
            "doi": "10.1234/paper",
            "title": paper["title"],
        },
    )
    monkeypatch.setattr(
        discovery,
        "europe_pmc_open_article",
        lambda *_args: {
            "provider": "europe_pmc",
            "source_id": "PMC12345",
            "source_url": "https://europepmc.org/articles/PMC12345",
            "title": paper["title"],
            "license": "CC-BY-4.0",
            "text": "An explanatory open article passage about attention mechanisms and their implementation.",
        },
    )
    result = discovery.hunt_record(store, tmp_path, paper)
    assert len(result["job_ids"]) == 1
    assert [item["provider"] for item in result["matches"]] == ["crossref", "europe_pmc"]
    assert store.job(result["job_ids"][0])["status"] == "awaiting_approval"


def test_unlicensed_article_is_not_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    xml = b"<article><permissions><license><license-p>All rights reserved</license-p></license></permissions><abstract><p>Real abstract</p></abstract></article>"
    responses = iter(
        [
            FakeResponse(
                {
                    "resultList": {
                        "result": [
                            {
                                "doi": "10.1234/paper",
                                "title": "Attention Is All You Need",
                                "isOpenAccess": "Y",
                                "pmcid": "PMC12345",
                            }
                        ]
                    }
                }
            ),
            FakeResponse(content=xml),
        ]
    )
    monkeypatch.setattr(external_sources.requests, "get", lambda *_args, **_kwargs: next(responses))
    assert (
        external_sources.europe_pmc_open_article("10.1234/paper", "Attention Is All You Need")
        is None
    )


def test_opac_next_cursor_is_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    import opac_live

    soup = BeautifulSoup(
        '<div class="searchresults"><a class="title" href="/cgi-bin/koha/opac-detail.pl?biblionumber=4131">Book</a></div>'
        '<a href="/cgi-bin/koha/opac-search.pl?q=machine%20learning&offset=20">Next</a>',
        "html.parser",
    )
    monkeypatch.setattr(
        opac_live,
        "_fetch",
        lambda *_args: (
            soup,
            "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-search.pl?q=machine+learning",
        ),
    )
    page = opac_live.search_books_page("machine learning")
    assert page["next_offset"] == 20
    with pytest.raises(ValueError):
        opac_live.search_books_page("machine learning", offset=21)


def test_configured_scan_resumes_pagination_and_rotates_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from archipelago.academic_automation import scan

    store = AcademicStore(tmp_path / "ledger.sqlite3")
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps(["machine learning", "physics"]))
    calls: list[tuple[str, int]] = []

    def fake_discover(
        _store: AcademicStore, _root: Path, query: str, *, offset: int = 0
    ) -> dict[str, Any]:
        calls.append((query, offset))
        return {"next_offset": 20 if len(calls) == 1 else None}

    monkeypatch.setattr(scan, "discover_opac_query", fake_discover)
    scan.scan_configured_queries(store, tmp_path, queries)
    scan.scan_configured_queries(store, tmp_path, queries)
    scan.scan_configured_queries(store, tmp_path, queries)
    assert calls == [("machine learning", 0), ("machine learning", 20), ("physics", 0)]
