"""S5 metadata search, isolation, graph and workbook checks."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from io import BytesIO

from openpyxl import load_workbook
import pytest

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.intelligence.graph import build_graph
from archipelago.scholarly.intelligence.monitor import run_monitor
from archipelago.scholarly.intelligence.search import discover, validate_options
from archipelago.scholarly.intelligence.storage import ResearchStore
from archipelago.scholarly.intelligence.workbook import HEADERS, build_workbook, safe_cell


class FakeOrchestrator:
    """Return an evidence-bearing candidate without network access."""

    def discover_with_status(self, query: str, limit: int):
        paper = PaperRecord(
            paper_id="paper-one",
            title="Graph neural networks for molecules",
            abstract="Graph neural networks represent molecular structures.",
            identifiers=PaperIdentifiers(
                doi="10.1000/example", openalex_id="https://openalex.org/W1"
            ),
            authors=[
                PaperAuthor(name="A Researcher", orcid="https://orcid.org/0000-0001-0000-0000")
            ],
            venue="Journal of Graphs",
            publication_date="2025-01-01",
            is_open_access=True,
        )
        provenance = ProvenancePointer(
            source_type="openalex", artifact_sha256="a" * 64, source_url="https://openalex.org/W1"
        )
        return (
            [
                {
                    "paper": paper,
                    "source": "openalex",
                    "provenance": provenance,
                    "citation_count": 7,
                    "source_metadata": {"referenced_works": ["https://openalex.org/W2"]},
                }
            ],
            [{"source": "openalex", "status": "live", "record_count": 1}],
        )


@pytest.mark.unit
def test_filters_and_workbook_are_real_typed_cells(tmp_path):
    run = discover({"topic": "graph neural networks", "top_k": 1}, FakeOrchestrator())
    assert len(run["papers"]) == 1
    store = ResearchStore(tmp_path / "research.sqlite3")
    run_id = store.save_run("alice", run)
    assert store.get_run(run_id, "bob") is None
    saved = store.get_run(run_id, "alice")
    assert saved is not None
    graph = build_graph(saved)
    assert any(edge["type"] == "AUTHORED_BY" for edge in graph["edges"])
    assert not any(edge["type"] == "CITES" for edge in graph["edges"])
    book = load_workbook(BytesIO(build_workbook(saved).getvalue()))
    assert book.sheetnames == list(HEADERS)
    assert book["Papers"]["C2"].value == 2025
    assert book["Papers"]["I2"].value == 7
    assert book["Papers"]["E2"].hyperlink is not None
    assert book["References"]["B2"].value == "https://openalex.org/W2"


@pytest.mark.unit
def test_options_and_untrusted_spreadsheet_text():
    with pytest.raises(ValueError, match="invalid_top_k"):
        validate_options({"topic": "graph neural networks", "top_k": 1000})
    assert safe_cell('=IMPORTXML("https://example.com")').startswith("'")


@pytest.mark.unit
def test_explicit_doi_versions_collapse_only_when_identity_agrees():
    class Versioned(FakeOrchestrator):
        def discover_with_status(self, query: str, limit: int):
            records, sources = super().discover_with_status(query, limit)
            first = records[0]
            first["paper"].identifiers.doi = "10.1000/example/v1"
            second = {**first, "paper": first["paper"].model_copy(deep=True)}
            second["paper"].paper_id = "paper-two"
            second["paper"].identifiers.doi = "10.1000/example/v2"
            return [first, second], sources

    run = discover({"topic": "graph neural networks", "top_k": 2}, Versioned())
    assert [paper["doi"] for paper in run["papers"]] == ["10.1000/example/v2"]


@pytest.mark.unit
def test_year_and_open_access_filters_exclude_unknown_or_mismatched_records():
    run = discover({"topic": "graph neural networks", "year_from": 2026}, FakeOrchestrator())
    assert run["papers"] == []
    run = discover({"topic": "graph neural networks", "open_access": False}, FakeOrchestrator())
    assert run["papers"] == []


@pytest.mark.unit
def test_monitor_is_opt_in_and_unchanged_refresh_is_idempotent(tmp_path, monkeypatch):
    from archipelago.scholarly.intelligence import monitor

    store = ResearchStore(tmp_path / "monitor.sqlite3")
    options = validate_options({"topic": "graph neural networks"})
    monitor_id = store.save_monitor("alice", options)
    assert run_monitor(monitor_id, store)["status"] == "not_enabled_or_claimed"
    assert store.set_monitor_enabled(monitor_id, "bob", True) is False
    assert store.set_monitor_enabled(monitor_id, "alice", True) is True
    monkeypatch.setattr(monitor, "discover", lambda _options: discover(options, FakeOrchestrator()))
    first = run_monitor(monitor_id, store)
    second = run_monitor(monitor_id, store)
    assert first["status"] == "updated"
    assert second == {"status": "unchanged", "run_id": first["run_id"], "new_papers": []}
    assert len(store.list_runs("alice")) == 1
    assert len(store.list_history(monitor_id, "alice")) == 2
    assert store.list_history(monitor_id, "bob") == []
    assert [event["kind"] for event in store.list_events("alice")] == ["newly_indexed_paper"]
    assert store.list_events("bob") == []


@pytest.mark.unit
def test_monitor_records_provider_failure_and_releases_lease(tmp_path, monkeypatch):
    from archipelago.scholarly.intelligence import monitor

    store = ResearchStore(tmp_path / "monitor-failure.sqlite3")
    monitor_id = store.save_monitor("alice", validate_options({"topic": "graph neural networks"}))
    assert store.set_monitor_enabled(monitor_id, "alice", True)
    monkeypatch.setattr(
        monitor,
        "discover",
        lambda _options: {"papers": [], "sources": [{"status": "rate_limited"}]},
    )
    first = run_monitor(monitor_id, store)
    first_retry = datetime.fromisoformat(store.list_monitors("alice")[0]["next_run_at"])
    second = run_monitor(monitor_id, store)
    assert first == {"status": "failed", "error": "RuntimeError"}
    assert second == first
    assert datetime.fromisoformat(store.list_monitors("alice")[0]["next_run_at"]) > first_retry
    assert store.list_monitors("alice")[0]["consecutive_failures"] == 2
    assert [row["status"] for row in store.list_history(monitor_id, "alice")] == [
        "failed",
        "failed",
    ]
    assert all(event["kind"] == "monitor_failed" for event in store.list_events("alice"))
    assert store.list_events("bob") == []


@pytest.mark.unit
def test_monitor_cadence_and_removal_are_owner_scoped(tmp_path):
    store = ResearchStore(tmp_path / "monitor-controls.sqlite3")
    options = validate_options({"topic": "graph neural networks"})
    with pytest.raises(ValueError, match="invalid_cadence_hours"):
        store.save_monitor("alice", options, True)
    monitor_id = store.save_monitor("alice", options, 6)
    assert store.list_monitors("alice")[0]["cadence_hours"] == 6
    assert not store.set_monitor_cadence(monitor_id, "bob", 24)
    assert store.set_monitor_cadence(monitor_id, "alice", 24)
    assert store.set_monitor_enabled(monitor_id, "alice", True)
    assert store.list_monitors("alice")[0]["next_run_at"] is not None
    assert not store.delete_monitor(monitor_id, "bob")
    assert store.delete_monitor(monitor_id, "alice")
    assert store.list_monitors("alice") == []


@pytest.mark.unit
def test_monitor_detects_source_backed_author_and_venue_changes(tmp_path, monkeypatch):
    from archipelago.scholarly.intelligence import monitor

    store = ResearchStore(tmp_path / "metadata-changes.sqlite3")
    options = validate_options({"topic": "graph neural networks"})
    monitor_id = store.save_monitor("alice", options)
    store.set_monitor_enabled(monitor_id, "alice", True)
    baseline = discover(options, FakeOrchestrator())
    baseline["author_observations"] = [
        {
            "id": "A1",
            "provider": "openalex",
            "metrics": {"citation_count": 7},
            "retrieved_at": "first",
        }
    ]
    baseline["papers"][0]["venue_details"] = {
        "id": "S1",
        "publisher": "First",
        "retrieved_at": "first",
    }
    timestamp_only = deepcopy(baseline)
    timestamp_only["author_observations"][0]["retrieved_at"] = "second"
    timestamp_only["papers"][0]["venue_details"]["retrieved_at"] = "second"
    changed = deepcopy(timestamp_only)
    changed["author_observations"][0]["metrics"]["citation_count"] = 8
    changed["papers"][0]["venue_details"]["publisher"] = "Corrected"
    runs = iter((baseline, timestamp_only, changed))
    monkeypatch.setattr(monitor, "discover", lambda _options: next(runs))

    assert run_monitor(monitor_id, store)["status"] == "updated"
    assert run_monitor(monitor_id, store)["status"] == "unchanged"
    outcome = run_monitor(monitor_id, store)
    assert outcome["author_changes"] == ["A1"]
    assert outcome["venue_changes"] == ["paper-one"]
    kinds = {event["kind"] for event in store.list_events("alice")}
    assert {"newly_indexed_paper", "author_metadata_changed", "venue_metadata_changed"} <= kinds
