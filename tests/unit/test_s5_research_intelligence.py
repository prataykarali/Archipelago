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
    papers = {c.value: i for i, c in enumerate(book["Papers"][1], 1)}
    assert book["Papers"].cell(2, papers["Year"]).value == 2025
    assert book["Papers"].cell(2, papers["Citations"]).value == 7
    assert book["Papers"].cell(2, papers["DOI"]).hyperlink is not None
    assert book["Papers"].cell(2, papers["Publication date"]).number_format == "yyyy-mm-dd"
    assert book["References"]["B2"].value == "https://openalex.org/W2"
    assert "Topic_Rankings" not in book.sheetnames
    assert book["Topic_Results"]["C2"].value == 1
    every_header = [c.value for ws in book for c in ws[1]]
    assert not any(("score" in str(h).lower() and h != "CiteScore") or "rank" in str(h).lower() for h in every_header)
    assert book["Authors"]["L2"].value == "N/A"  # i10 unavailable, not zero
    assert run["papers"][0]["author_ids"] == []


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


@pytest.mark.unit
def test_methods_datasets_only_when_abstract_supports_them():
    from archipelago.scholarly.intelligence.extraction import extract_evidence

    found = extract_evidence(
        "Graph attention for citation graphs",
        "We train a graph attention network on Cora. Accuracy improves over baselines.",
    )
    assert [m["name"] for m in found["methods"]] == ["graph attention network"]
    assert [d["name"] for d in found["datasets"]] == ["cora"]
    assert [m["name"] for m in found["evaluation_metrics"]] == ["accuracy"]
    empty = extract_evidence("A title", None)
    assert empty == {"methods": [], "datasets": [], "evaluation_metrics": []}


@pytest.mark.unit
def test_loosely_related_papers_are_not_used_to_fill_the_count():
    class Loose(FakeOrchestrator):
        def discover_with_status(self, query, limit):
            records, sources = super().discover_with_status(query, limit)
            other = {**records[0], "paper": records[0]["paper"].model_copy(deep=True)}
            other["paper"].paper_id = "paper-cnn"
            other["paper"].title = "Convolutional neural networks for images"
            other["paper"].abstract = "A neural network for image recognition."
            return [records[0], other], sources

    run = discover({"topic": "graph neural networks", "top_k": 100}, Loose())
    assert [p["paper_id"] for p in run["papers"]] == ["paper-one"]
    assert all("rank" not in p and "relevance_score" not in p for p in run["papers"])


@pytest.mark.unit
def test_graph_has_method_edges_and_stable_provider_author_ids():
    class Rich(FakeOrchestrator):
        def discover_with_status(self, query, limit):
            records, sources = super().discover_with_status(query, limit)
            records[0]["paper"].authors.append(PaperAuthor(name="B Researcher"))
            records[0]["source_metadata"].update(
                {"author_openalex_ids": ["https://openalex.org/A1", "https://openalex.org/A2"]}
            )
            return records, sources

    run = discover({"topic": "graph neural networks", "top_k": 1}, Rich())
    graph = build_graph(run)
    ids = {n["id"] for n in graph["nodes"]}
    assert {"author:A1", "author:A2"} <= ids
    assert any(e["type"] == "COAUTHORED_WITH" for e in graph["edges"])
    assert any(e["type"] == "USES_METHOD" for e in graph["edges"])
    assert all(e["provider"] != "ranking" for e in graph["edges"])


@pytest.mark.unit
def test_research_chat_answers_from_snapshot_and_never_invents_metrics(tmp_path):
    import sys

    sys.path.insert(0, "host_inference")
    from hostapp.research_run_chat import research_chat_reply

    store = ResearchStore(tmp_path / "chat.sqlite3")
    run = discover({"topic": "graph neural networks", "top_k": 5}, FakeOrchestrator())
    run_id = store.save_run("alice", run)
    ask = lambda q, h=None, o="alice": research_chat_reply(q, h, o, store, run_id)  # noqa: E731
    listing = ask("Show all the collected papers with their authors and publication years.")
    assert "A Researcher" in listing["text"] and "2025" in listing["text"]
    authored = ask("Who authored the first paper?")
    assert "A Researcher" in authored["text"]
    hist = [{"role": "assistant", "content": authored["text"]}]
    hindex = ask("What is that author's h-index, if available?", hist)
    assert "not available" in hindex["text"] and "0" not in hindex["text"].split("(")[0]
    assert "Journal of Graphs" in ask("Which journals or conferences published these works?")["text"]
    assert "No provider-verified citation" in ask("Show the citation relationships between these papers.")["text"]
    assert f"/runs/{run_id}/xlsx" in ask("Export this research collection to Excel.")["text"]
    assert "No monitoring run" in ask("Are there new papers since the last monitoring run?")["text"]
    assert ask("What is a graph neural network?") is None
    assert research_chat_reply("Who authored the first paper?", None, "bob", store, run_id) is None
