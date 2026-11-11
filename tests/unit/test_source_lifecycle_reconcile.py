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
    withdrawn_documents,
)

from archipelago.resolver.ingest_proposals import (  # noqa: E402
    IngestProposal,
    approved_for_ingest,
    decide,
    detect_new_sources,
    fingerprint_for,
    load_queue,
    pending_proposals,
)
from archipelago.resolver.source_lifecycle import (  # noqa: E402
    SourceState,
    load_ledger,
    reconcile,
    record_check,
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


def test_reconcile_counts_only_newly_withdrawn(ledger_dir):
    first = reconcile(
        live_ids=["isbn:1", "isbn:2"],
        checked={"isbn:1": ("gone", PROVIDER, "410 Gone"), "isbn:2": ("verified", PROVIDER, "")},
        base_dir=ledger_dir,
    )
    assert first["newly_withdrawn"] == ["isbn:1"]
    assert set(first["verified"]) == {"isbn:2"}

    # A second sweep reports the same state: nothing is "newly" withdrawn.
    second = reconcile(
        live_ids=["isbn:1", "isbn:2"],
        checked={"isbn:1": ("gone", PROVIDER, "410 Gone"), "isbn:2": ("verified", PROVIDER, "")},
        base_dir=ledger_dir,
    )
    assert second["newly_withdrawn"] == []
    assert second["withdrawn_total"] == 1


def test_reconcile_leaves_unchecked_sources_alone(ledger_dir):
    """Absence of a check is not evidence of withdrawal."""
    record_check("isbn:1", "verified", provider=PROVIDER, base_dir=ledger_dir)
    reconcile(live_ids=["isbn:1"], checked={}, base_dir=ledger_dir)
    assert load_ledger(ledger_dir)["isbn:1"].status == "verified"


# ─── Proposals: ask the librarian ───────────────────────────────────────────


def test_new_book_becomes_a_pending_proposal(ledger_dir):
    result = detect_new_sources(
        discovered=[{"title": "New Textbook", "isbn": "9781234567890", "provider": "pearson"}],
        held_ids=[],
        base_dir=ledger_dir,
    )
    assert len(result["proposed"]) == 1
    proposal = pending_proposals(ledger_dir)[0]
    assert proposal.title == "New Textbook"
    assert proposal.actionable
    # Nothing is auto-ingested: the default posture is structure only.
    assert proposal.license_mode == "toc_only"


def test_already_held_book_is_not_proposed(ledger_dir):
    result = detect_new_sources(
        discovered=[{"title": "Held Book", "isbn": "9781111111111", "provider": "pearson"}],
        held_ids=["9781111111111"],
        base_dir=ledger_dir,
    )
    assert result["proposed"] == []
    assert result["already_held"] == 1


def test_resweep_does_not_duplicate_a_proposal(ledger_dir):
    discovered = [{"title": "New Textbook", "isbn": "9781234567890", "provider": "pearson"}]
    detect_new_sources(discovered, [], base_dir=ledger_dir)
    detect_new_sources(discovered, [], base_dir=ledger_dir)
    assert len(load_queue(ledger_dir)) == 1


def test_declined_book_is_not_re_asked(ledger_dir):
    discovered = [{"title": "New Textbook", "isbn": "9781234567890", "provider": "pearson"}]
    detect_new_sources(discovered, [], base_dir=ledger_dir)
    fingerprint = fingerprint_for("pearson", "New Textbook", "9781234567890")
    decide(fingerprint, "declined", note="not purchased", base_dir=ledger_dir)

    detect_new_sources(discovered, [], base_dir=ledger_dir)
    assert pending_proposals(ledger_dir) == []
    assert load_queue(ledger_dir)[fingerprint].decision == "declined"


def test_approved_proposal_is_offered_to_the_ingestion_worker(ledger_dir):
    discovered = [{"title": "New Textbook", "isbn": "9781234567890", "provider": "pearson"}]
    detect_new_sources(discovered, [], base_dir=ledger_dir)
    fingerprint = fingerprint_for("pearson", "New Textbook", "9781234567890")
    decide(fingerprint, "approved", license_mode="full", base_dir=ledger_dir)

    ready = approved_for_ingest(ledger_dir)
    assert len(ready) == 1
    assert ready[0].license_mode == "full"
    assert ready[0].decided_at


def test_decide_rejects_unknown_decision_and_unknown_key(ledger_dir):
    detect_new_sources([{"title": "T", "provider": "pearson"}], [], base_dir=ledger_dir)
    with pytest.raises(ValueError):
        decide(fingerprint_for("pearson", "T"), "maybe", base_dir=ledger_dir)
    with pytest.raises(KeyError):
        decide("title:nope", "approved", base_dir=ledger_dir)


def test_fingerprint_prefers_isbn_over_title():
    by_isbn = fingerprint_for("pearson", "Some Book", "9781234567890")
    assert by_isbn == "isbn:9781234567890"
    # Different provider, same ISBN -> same identity (one book, one question).
    assert fingerprint_for("huggingface", "Renamed Book", "9781234567890") == by_isbn


def test_fingerprint_falls_back_to_title_without_isbn():
    assert fingerprint_for("pearson", "Some Book").startswith("title:")
    assert fingerprint_for("pearson", "Some Book") == fingerprint_for("pearson", "some   book")


@pytest.mark.parametrize("bad", [None, {}, {"title": ""}, "not-a-dict", {"title": "   "}])
def test_detection_skips_malformed_entries_without_raising(ledger_dir, bad):
    result = detect_new_sources(discovered=[bad], held_ids=[], base_dir=ledger_dir)
    assert result["proposed"] == []
    assert result["skipped"] == 1


def test_queue_file_is_valid_json_and_versioned(ledger_dir):
    detect_new_sources([{"title": "T", "provider": "pearson"}], [], base_dir=ledger_dir)
    from archipelago.resolver.ingest_proposals import queue_path

    payload = json.loads(queue_path(ledger_dir).read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["proposals"]


def test_corrupt_queue_is_treated_as_empty(ledger_dir):
    from archipelago.resolver.ingest_proposals import queue_path

    path = queue_path(ledger_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")
    assert load_queue(ledger_dir) == {}


def test_proposal_roundtrips_through_dict():
    proposal = IngestProposal(title="T", provider="pearson")
    assert IngestProposal.from_dict(proposal.to_dict()).fingerprint == proposal.fingerprint


def test_ledger_roundtrips_through_dict():
    state = SourceState(source_id="x", status="withdrawn", provider="pearson")
    assert SourceState.from_dict(state.to_dict()).status == "withdrawn"


# ─── End-to-end: the notice reaches the chat payload ────────────────────────


def _solo_graph(tmp_path, doc_id, concept_id="lora"):
    """A graph with one concept whose only supporting doc is ``doc_id``."""
    payload = {
        "nodes": [
            {
                "id": concept_id,
                "label": "Low-Rank Adaptation",
                "sources": [
                    {
                        "doc_id": doc_id,
                        "page_number": 2,
                        "text_passage": "Low-Rank Adaptation freezes the base weights.",
                    }
                ],
            }
        ]
    }
    path = tmp_path / "solo_graph.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_chat_payload_carries_the_notice_when_the_only_source_is_withdrawn(
    ledger_dir, tmp_path, monkeypatch
):
    """A student must be told the title left the record, not shown a dead link."""
    import engine.graph as gmod
    from hostapp.factory import create_app

    solo = _solo_graph(tmp_path, "papers/Hu2021_LoRA.pdf")
    record_check(
        "isbn:lora",
        "gone",
        provider="huggingface",
        message="HTTP 404 - file removed from repo",
        metadata={"title": "LoRA paper", "doc_id": "papers/Hu2021_LoRA.pdf"},
        base_dir=ledger_dir,
    )

    original_init = gmod.LibraryGraph.__init__

    def patched(self, path):
        original_init(self, solo)

    monkeypatch.setattr(gmod.LibraryGraph, "__init__", patched)
    app = create_app()
    # A distinct query from the live-alternative test: cache_service is a
    # process-wide singleton, so reusing a query would replay a cached frame
    # and hide whether the fresh-compute path is correct.
    body = (
        app.test_client()
        .post("/api/chat", json={"query": "explain low-rank adaptation"})
        .get_data(as_text=True)
    )
    meta = json.loads(body.split("\n[STREAM_START]\n", 1)[0].strip())

    assert meta["withdrawn_notice"]
    assert "no longer in the library" in meta["withdrawn_notice"]
    assert meta["text_override"] == meta["withdrawn_notice"]
    citation = meta["citations"][0]
    assert citation["withdrawn"] is True
    assert citation["url"] == ""


def test_chat_payload_has_no_notice_when_a_live_source_remains(ledger_dir, tmp_path, monkeypatch):
    """One title's withdrawal must not mute a question another document answers."""
    import engine.graph as gmod
    from hostapp.factory import create_app

    payload = {
        "nodes": [
            {
                "id": "lora",
                "label": "Low-Rank Adaptation",
                "sources": [
                    {
                        "doc_id": "papers/Hu2021_LoRA.pdf",
                        "page_number": 2,
                        "text_passage": "primary",
                    },
                    {"doc_id": "papers/live.pdf", "page_number": 9, "text_passage": "secondary"},
                ],
            }
        ]
    }
    graph_file = tmp_path / "alt_graph.json"
    graph_file.write_text(json.dumps(payload), encoding="utf-8")
    record_check(
        "isbn:lora",
        "gone",
        provider="huggingface",
        metadata={"title": "LoRA paper", "doc_id": "papers/Hu2021_LoRA.pdf"},
        base_dir=ledger_dir,
    )

    original_init = gmod.LibraryGraph.__init__

    def patched(self, path):
        original_init(self, graph_file)

    monkeypatch.setattr(gmod.LibraryGraph, "__init__", patched)
    app = create_app()
    body = (
        app.test_client().post("/api/chat", json={"query": "explain LoRA"}).get_data(as_text=True)
    )
    meta = json.loads(body.split("\n[STREAM_START]\n", 1)[0].strip())

    assert "withdrawn_notice" not in meta
    assert "text_override" not in meta
    assert meta["citations"][0]["doc_id"] == "papers/live.pdf"


# ─── Demo cards: hand-built citations must honour the ledger ────────────────


def test_demo_card_citations_are_withdrawal_checked(ledger_dir):
    """Demo cards hard-code citations, bypassing cite_record.

    Without an explicit check, a retired title keeps being offered in the demo
    answers even after the graph stopped citing it.
    """
    import demo_cards

    assert withdrawn_documents(load_ledger(ledger_dir)) == set()

    citations = [
        {"doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf", "url": "/read?doc=x"},
    ]
    record_check(
        "isbn:vaswani",
        "gone",
        provider="huggingface",
        metadata={"doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf"},
        base_dir=ledger_dir,
    )

    marked = demo_cards._mark_withdrawn(citations)
    assert marked[0]["withdrawn"] is True
    assert marked[0]["url"] == ""
    assert "no longer in the library" in marked[0]["notice"]


def test_demo_card_marking_leaves_live_citations_usable(ledger_dir):
    import demo_cards

    citations = [{"doc_id": "papers/live.pdf", "url": "/read?doc=live"}]
    marked = demo_cards._mark_withdrawn(citations)
    assert marked[0]["withdrawn"] is False
    assert marked[0]["url"] == "/read?doc=live"


def test_demo_card_marking_is_a_no_op_without_a_ledger(ledger_dir):
    import demo_cards

    citations = [{"doc_id": "papers/live.pdf", "url": "/read?doc=live"}]
    assert demo_cards._mark_withdrawn([]) == []
    assert len(demo_cards._mark_withdrawn(citations)) == 1
