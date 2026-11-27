"""Stage 3 scientific & UX consolidation tests for F02-F08."""

from __future__ import annotations

import inspect
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_INFERENCE_DIR = REPO_ROOT / "host_inference"
if str(HOST_INFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_INFERENCE_DIR))

from engine import compose, render, route_logic  # noqa: E402
from engine.answer import Engine  # noqa: E402
from engine.evidence_selection import select_catalog_passages  # noqa: E402
from engine.graph import LibraryGraph  # noqa: E402
from engine.inventory_card import inventory_cards_for_concept  # noqa: E402
from engine.math_guard import audit_worked_address_translation  # noqa: E402

FIXTURE_GRAPH = HOST_INFERENCE_DIR / "fixtures" / "okf_graph.json"


def test_f02_concept_resolution_specificity_and_acronyms() -> None:
    graph = LibraryGraph(FIXTURE_GRAPH)
    paging_hits = [cid for _score, cid in graph.rank("virtual memory paging", top_k=3)]
    assert paging_hits[0] == "paging"

    nf_hits = [cid for _score, cid in graph.rank("Explain Third Normal Form (3NF)", top_k=3)]
    assert nf_hits[0] == "third_normal_form"


def test_f03_no_hardcoded_diagnostic_rules_in_route_logic() -> None:
    src = inspect.getsource(route_logic)
    assert "source_grounded_os_reply(" not in src
    assert "special_book_reply(" not in src


def test_f03_f07_generalizable_catalog_passage_retrieval() -> None:
    engine = Engine(FIXTURE_GRAPH)
    # Fixture graph's address_translation node has 0 node sources; catalog fallback must cover it.
    assert len(engine.graph.nodes["address_translation"].get("sources") or []) == 0
    cites = select_catalog_passages(
        engine.catalog,
        "How does base and bounds address translation work?",
        concept_label="Address Translation",
        anchor_cid="address_translation",
    )
    assert cites
    assert any("07_address_translation" in str(c.get("doc_id") or "").lower() for c in cites)

    paging_cites = select_catalog_passages(
        engine.catalog,
        "How does virtual memory paging work?",
        concept_label="Paging",
        anchor_cid="paging",
    )
    assert paging_cites
    assert any("08_paging" in str(c.get("doc_id") or "").lower() for c in paging_cites)


def test_f04_math_guard_flags_invalid_offset_and_accepts_valid_offset() -> None:
    bad = audit_worked_address_translation(
        "Under 4 KiB paging, virtual address 0x1234 maps to physical address 0x5678."
    )
    assert bad is not None
    assert "0x234" in bad and "0x678" in bad

    good = audit_worked_address_translation(
        "Under 4 KiB paging, virtual address 0x1234 maps to physical address 0x5234."
    )
    assert good is None


def test_f05_graph_direction_and_inverse_edge_labels() -> None:
    assert compose._step_relation_label("inv-REQUIRES") == "UNLOCKS"
    assert compose._step_relation_label("inv-UNLOCKS") == "REQUIRES"
    assert compose._step_relation_label("REQUIRES") == "REQUIRES"

    graph = LibraryGraph(FIXTURE_GRAPH)
    rendered = render.lineage(graph, "paging")
    if rendered and "->" in rendered:
        assert "--[UNLOCKS]--> **Paging**" in rendered


def test_f06_honest_inspector_labels_and_null_timings() -> None:
    inspector_js = (REPO_ROOT / "host_inference" / "ui" / "js" / "15-inspector.js").read_text(
        encoding="utf-8"
    )
    assert "'Not reported'" in inspector_js
    assert "'Automatically checked'" in inspector_js
    assert "Graph Edges Review Pending" in inspector_js
    assert "Provenance-Verified" not in inspector_js

    chat_route = (REPO_ROOT / "host_inference" / "hostapp" / "routes" / "chat.py").read_text(
        encoding="utf-8"
    )
    assert "if should_enrich else None" in chat_route
    assert '"provider_ttft_ms": None' in chat_route


def test_f08_no_cross_domain_pearson_books_on_os_queries(monkeypatch) -> None:
    sample_records = [
        {
            "title": "Digital Design (M. Morris Mano)",
            "subject": "Digital Logic",
            "keywords": ["logic gates", "boolean algebra", "flip flops"],
            "is_pearson": True,
        },
        {
            "title": "Fundamentals of Database Systems (Elmasri & Navathe)",
            "subject": "Database Management",
            "keywords": ["relational algebra", "sql", "normalization"],
            "is_pearson": True,
        },
    ]
    cards = inventory_cards_for_concept(
        "paging",
        "Paging",
        "How does virtual memory paging work in operating systems?",
        sample_records,
    )
    assert cards == []

    monkeypatch.setenv("ARCHIPELAGO_ACCESS_PROFILE", "open_access")
    engine = Engine(FIXTURE_GRAPH)
    assert engine.best_book("paging") is None


def test_c_bounded_provider_wait_and_honest_abstention_without_evidence(monkeypatch) -> None:
    import json

    from engine import answer as answer_mod
    from engine import llm as llm_mod

    assert llm_mod.STREAM_FIRST_TOKEN_TIMEOUT_SECONDS <= 20
    assert llm_mod.STREAM_READ_TIMEOUT_SECONDS <= 30

    engine = Engine(FIXTURE_GRAPH)
    monkeypatch.setattr(
        answer_mod,
        "provider_config",
        lambda: {"provider": "xkiro", "base_url": "https://xkiro.invalid", "key": "k", "model": "m"},
    )
    monkeypatch.setattr(answer_mod, "fallback_config", lambda _cfg: None)
    monkeypatch.setattr(answer_mod, "stream_completion", lambda *a, **kw: iter([]))
    monkeypatch.setattr(
        answer_mod,
        "last_provider_error",
        lambda: {"provider": "xkiro", "error_type": "first_token_timeout"},
    )

    # Without anchor/citations on an unindexed query, provider unavailability must abstain honestly.
    prepared_empty = {
        "route": "GENERAL_EXPLANATION",
        "text": "General explanation.",
        "anchor": None,
        "extra": {},
        "payload": {"anchor_concept": None, "citations": [], "logs": []},
    }
    raw_empty = "".join(engine.stream_chat("What is a quantum Turing machine?", prepared=prepared_empty))
    meta_empty = json.loads(raw_empty.split("\n[STREAM_START]\n", 1)[0])
    body_empty = raw_empty.split("\n[STREAM_START]\n", 1)[1]
    assert meta_empty["provider_status"] == "unavailable"
    assert meta_empty["fallback_reason"] == "first_token_timeout"
    assert meta_empty["trace"]["grounding_status"] == "abstained"
    assert "insufficient indexed evidence" in body_empty.lower()

    # With indexed anchor & citation, provider unavailability falls back to grounded draft.
    prepared_grounded = engine.answer("How does virtual memory paging work?")
    raw_grounded = "".join(engine.stream_chat("How does virtual memory paging work?", prepared=prepared_grounded))
    meta_grounded = json.loads(raw_grounded.split("\n[STREAM_START]\n", 1)[0])
    assert meta_grounded["synthesis_mode"] == "provider_unavailable_fallback"
    assert meta_grounded["provider_status"] == "unavailable"
    assert meta_grounded["fallback_reason"] == "first_token_timeout"
