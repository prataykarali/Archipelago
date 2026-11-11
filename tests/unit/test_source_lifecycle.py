"""Feature regression — source lifecycle (withdrawal) and ingest proposals.

Two behaviours the library depends on:

1. **Withdrawal.** When Pearson or Hugging Face removes a title, the graph stops
   citing it and says the title is no longer in records — but a concept backed
   by another live document keeps answering, and a *failed* check never retires
   a source.
2. **Proposal.** A newly entitled book surfaces as a pending proposal for the
   librarian instead of being auto-ingested, and the same book is never asked
   about twice.

Deterministic: every test uses ``tmp_path`` for the ledger/queue and a
synthetic graph, so nothing touches the real corpus.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(REPO_ROOT), str(REPO_ROOT / "host_inference")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from engine.withdrawal import (  # noqa: E402
    NEUTRAL_NOTICE,
    best_live_source,
    is_citable_source,
    partition_sources,
    withdrawal_notice_for_doc,
    withdrawn_documents,
)

from archipelago.resolver.source_lifecycle import (  # noqa: E402
    NOT_IN_RECORDS,
    SourceState,
    classify_verdict,
    filter_citable,
    load_ledger,
    record_check,
    withdrawal_notice,
    withdrawn_ids,
)

pytestmark = pytest.mark.unit

PROVIDER = "pearson"
DOC_ID = "textbooks/DSP_4e.pdf"


@pytest.fixture
def ledger_dir(tmp_path, monkeypatch):
    """Isolate the lifecycle ledger + proposal queue into ``tmp_path``.

    Sets the shared state-root override so every module — including the engine,
    which resolves the ledger itself — reads the temporary root. Without this
    the graph tests would consult the real institutional ledger.
    """
    from archipelago.resolver.source_lifecycle import STATE_DIR_ENV

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path))
    return tmp_path


# ─── Verdict classification: only authoritative negatives retire ─────────────


@pytest.mark.parametrize(
    "verdict, expected",
    [
        ("gone", "withdrawn"),
        ("withdrawn", "withdrawn"),
        ("not_found", "withdrawn"),
        ("deleted", "withdrawn"),
        ("404", "withdrawn"),
        ("error", "unknown"),
        ("timeout", "unknown"),
        ("network_error", "unknown"),
        # A credentials problem is NOT evidence the book was removed.
        ("auth_required", "unknown"),
        ("forbidden", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_only_authoritative_negatives_withdraw(verdict, expected):
    assert classify_verdict(verdict) == expected


# ─── Ledger transitions ─────────────────────────────────────────────────────


def test_record_check_marks_gone_source_withdrawn(ledger_dir):
    state = record_check(
        "isbn:9789332526532",
        "gone",
        provider=PROVIDER,
        message="HTTP 410 Gone",
        metadata={
            "title": "Digital Signal Processing, 4e",
            "isbn": "9789332526532",
            "doc_id": DOC_ID,
        },
        base_dir=ledger_dir,
    )
    assert state.status == "withdrawn"
    assert not state.citable
    assert state.tombstone["title"] == "Digital Signal Processing, 4e"
    assert state.tombstone["doc_id"] == DOC_ID
    # The reason is retained so the withdrawal is auditable.
    assert state.tombstone["reason"] == "HTTP 410 Gone"


def test_ledger_survives_a_reload(ledger_dir):
    record_check("isbn:1", "gone", provider=PROVIDER, base_dir=ledger_dir)
    assert "isbn:1" in withdrawn_ids(load_ledger(ledger_dir))


def test_verified_check_clears_a_previous_tombstone(ledger_dir):
    record_check("isbn:1", "gone", provider=PROVIDER, base_dir=ledger_dir)
    state = record_check("isbn:1", "verified", provider=PROVIDER, base_dir=ledger_dir)
    assert state.status == "verified"
    assert state.citable
    assert state.tombstone == {}
    assert state.last_verified


def test_failed_check_does_not_retire_a_healthy_source(ledger_dir):
    record_check("isbn:1", "verified", provider=PROVIDER, base_dir=ledger_dir)
    state = record_check("isbn:1", "timeout", provider=PROVIDER, base_dir=ledger_dir)
    assert state.status == "verified", "a timeout must not withdraw a live book"
    assert state.citable


def test_failed_check_does_not_resurrect_a_withdrawn_source(ledger_dir):
    """The asymmetry that matters: no false re-instatement."""
    record_check("isbn:1", "gone", provider=PROVIDER, base_dir=ledger_dir)
    state = record_check("isbn:1", "timeout", provider=PROVIDER, base_dir=ledger_dir)
    assert state.status == "withdrawn"
    assert not state.citable


def test_unknown_state_is_citable(ledger_dir):
    """Never checked is not the same as gone."""
    assert SourceState(source_id="isbn:x").citable


def test_withdrawal_notice_names_the_provider():
    notice = withdrawal_notice(SourceState(source_id="x", provider="huggingface"))
    assert "huggingface" in notice
    assert "no longer in the library" in notice


def test_withdrawal_notice_without_provider_is_neutral():
    notice = withdrawal_notice(SourceState(source_id="x"))
    assert "huggingface" not in notice
    assert "no longer in the library" in notice


def test_not_in_records_copy_never_speculates_about_cause():
    """Must not claim the book was 'deleted' or 'lost' — only that it is gone."""
    for notice in (
        NOT_IN_RECORDS.format(source="pearson"),
        withdrawal_notice(SourceState(source_id="x")),
    ):
        assert "no longer in the library" in notice
        for speculative in ("lost", "because we", "mistake", "error"):
            assert speculative not in notice.lower()


# ─── Provenance rules ───────────────────────────────────────────────────────


def test_source_without_provenance_is_not_citable():
    assert not is_citable_source({"text_passage": "some text"}, retired=set())


def test_partition_splits_citable_from_withdrawn(ledger_dir):
    record_check(
        "isbn:1",
        "gone",
        provider=PROVIDER,
        metadata={"doc_id": DOC_ID},
        base_dir=ledger_dir,
    )
    sources = [
        {"doc_id": DOC_ID, "text_passage": "gone"},
        {"doc_id": "papers/live.pdf", "text_passage": "live"},
    ]
    citable, gone = partition_sources(sources, withdrawn_documents(load_ledger(ledger_dir)))
    assert [s["doc_id"] for s in citable] == ["papers/live.pdf"]
    assert [s["doc_id"] for s in gone] == [DOC_ID]


def test_best_live_source_reports_when_all_are_withdrawn(ledger_dir):
    record_check(
        "isbn:1",
        "gone",
        provider=PROVIDER,
        metadata={"doc_id": DOC_ID},
        base_dir=ledger_dir,
    )
    retired = withdrawn_documents(load_ledger(ledger_dir))
    best, all_withdrawn = best_live_source(
        [{"doc_id": DOC_ID, "text_passage": "x"}], lambda s: 1, retired
    )
    assert best is None
    assert all_withdrawn is True


def test_best_live_source_prefers_the_higher_scoring_live_document(ledger_dir):
    record_check(
        "isbn:1",
        "gone",
        provider=PROVIDER,
        metadata={"doc_id": DOC_ID},
        base_dir=ledger_dir,
    )
    retired = withdrawn_documents(load_ledger(ledger_dir))
    sources = [
        {"doc_id": DOC_ID, "text_passage": "best text"},
        {"doc_id": "papers/other.pdf", "text_passage": "worse"},
    ]
    best, all_withdrawn = best_live_source(
        sources, lambda s: 10 if s["doc_id"] == DOC_ID else 1, retired
    )
    # The withdrawn document scores highest but must lose.
    assert best["doc_id"] == "papers/other.pdf"
    assert all_withdrawn is False


def test_filter_citable_drops_withdrawn_ids():
    states = {"isbn:1": SourceState(source_id="isbn:1", status="withdrawn")}
    items = [{"isbn": "isbn:1"}, {"isbn": "isbn:2"}]
    assert filter_citable(items, "isbn", states) == [{"isbn": "isbn:2"}]


def test_empty_ledger_keeps_everything_citable(ledger_dir):
    assert withdrawn_documents(load_ledger(ledger_dir)) == set()


def test_withdrawal_notice_names_the_provider_when_lookup_succeeds(ledger_dir):
    record_check(
        "isbn:1",
        "gone",
        provider="huggingface",
        metadata={"doc_id": DOC_ID},
        base_dir=ledger_dir,
    )
    assert "huggingface" in withdrawal_notice_for_doc(DOC_ID)


def test_withdrawal_notice_is_neutral_for_an_unknown_document(ledger_dir):
    """A doc_id nobody withdrew must not be described as withdrawn."""
    assert withdrawal_notice_for_doc("papers/never_withdrawn.pdf") == NEUTRAL_NOTICE


# ─── Graph behaviour: forget the title, keep the concept ────────────────────


def _graph(tmp_path, node):
    from engine.graph import LibraryGraph

    export = tmp_path / "okf_graph.json"
    export.write_text(json.dumps({"nodes": [node]}), encoding="utf-8")
    return LibraryGraph(export)


def test_graph_refuses_to_cite_a_withdrawn_document(ledger_dir, tmp_path):
    record_check(
        "isbn:1",
        "gone",
        provider=PROVIDER,
        metadata={"doc_id": DOC_ID},
        base_dir=ledger_dir,
    )
    graph = _graph(
        tmp_path,
        {
            "id": "dsp",
            "label": "Digital Signal Processing",
            "sources": [{"doc_id": DOC_ID, "page_number": 12, "text_passage": "filtering"}],
        },
    )
    record = graph.cite_record("dsp", "dsp")
    assert record["withdrawn"] is True
    assert record["pdf_url"] == "", "a withdrawn title must not offer a link"
    assert record["doc_id"] == ""
    assert "no longer in the library" in record["notice"]


def test_graph_still_cites_a_live_alternative_for_the_same_concept(ledger_dir, tmp_path):
    """Knowledge supported elsewhere must survive one title's withdrawal."""
    record_check(
        "isbn:1",
        "gone",
        provider=PROVIDER,
        metadata={"doc_id": DOC_ID},
        base_dir=ledger_dir,
    )
    graph = _graph(
        tmp_path,
        {
            "id": "dsp",
            "label": "Digital Signal Processing",
            "sources": [
                {"doc_id": DOC_ID, "page_number": 12, "text_passage": "primary"},
                {"doc_id": "papers/live.pdf", "page_number": 30, "text_passage": "secondary"},
            ],
        },
    )
    record = graph.cite_record("dsp", "dsp")
    assert record["withdrawn"] is False
    assert record["doc_id"] == "papers/live.pdf"
    assert record["pdf_url"]


def test_graph_with_live_source_is_unaffected_by_an_empty_ledger(ledger_dir, tmp_path):
    graph = _graph(
        tmp_path,
        {
            "id": "bert",
            "label": "BERT",
            "sources": [{"doc_id": "papers/bert.pdf", "page_number": 2, "text_passage": "x"}],
        },
    )
    record = graph.cite_record("bert", "bert")
    assert record["withdrawn"] is False
    assert record["doc_id"] == "papers/bert.pdf"


# ─── Reconcile ──────────────────────────────────────────────────────────────
