"""D12 unit tests for Answer Synthesis, Citation Integrity, and Latency/Reliability."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_INFERENCE_DIR = REPO_ROOT / "host_inference"
if str(HOST_INFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_INFERENCE_DIR))

from engine import answer as answer_mod  # noqa: E402
from engine import citation_format, compose, llm, render  # noqa: E402
from engine.answer import Engine  # noqa: E402
from hostapp import create_app, security  # noqa: E402

pytestmark = pytest.mark.unit
FIXTURE_GRAPH = HOST_INFERENCE_DIR / "fixtures" / "okf_graph.json"


# ── Section 1: Answer Generation & Task Completeness ─────────────────────────


@pytest.mark.parametrize(
    "query",
    [
        "How does base-and-bounds hardware address translation relocate a process address space?",
        "What is Third Normal Form (3NF) in relational database design?",
        "What is dynamic programming in algorithm design?",
        "What concepts are prerequisites for understanding paging and address translation?",
    ],
)
def test_live_synthesis_invoked_for_d10_os_b_db_a_dsa_a_and_os_c(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    """D10-OS-B, D10-DB-A, D10-DSA-A, and D10-OS-C must invoke live synthesis, not 1-line stubs."""
    engine = Engine(FIXTURE_GRAPH)
    prepared = engine.answer(query)
    captured: list[tuple[str, str]] = []

    monkeypatch.setattr(
        answer_mod,
        "provider_config",
        lambda: {"provider": "xkiro", "base_url": "https://xkiro.invalid", "key": "k", "model": "m"},
    )
    monkeypatch.setattr(answer_mod, "fallback_config", lambda _cfg: None)

    def fake_stream(_cfg, safe_text: str, q: str, *_args, **_kwargs):
        captured.append((q, safe_text))
        yield "### Direct Answer\nStructured explanation with mechanism and example."

    monkeypatch.setattr(answer_mod, "stream_completion", fake_stream)
    monkeypatch.setattr(
        answer_mod,
        "last_stream_outcome",
        lambda: {"status": "complete", "finish_reason": "stop"},
    )
    monkeypatch.setattr(answer_mod, "last_provider_error", lambda: None)

    chunks = list(engine.stream_chat(query, prepared=prepared))
    meta = json.loads(chunks[0].split("\n[STREAM_START]\n", 1)[0])
    assert captured, f"Live synthesis was NOT invoked for: {query}"
    assert meta["synthesis_mode"] == "xkiro_synthesis"
    assert meta["provider"] == "xkiro"


@pytest.mark.parametrize(
    "query",
    [
        "Hello",
        "Explain Spanner TrueTime and its prerequisites.",
        "How does Raft consensus elect a leader?",
    ],
)
def test_greetings_and_unindexed_abstentions_never_call_provider(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    """Greetings and unindexed abstentions must stay strictly deterministic."""
    engine = Engine(FIXTURE_GRAPH)
    prepared = engine.answer(query)
    monkeypatch.setattr(
        answer_mod,
        "provider_config",
        lambda: {"provider": "xkiro", "base_url": "https://xkiro.invalid", "key": "k", "model": "m"},
    )

    def unexpected_provider(*_args, **_kwargs):
        raise AssertionError(f"Provider should not be called for: {query}")

    monkeypatch.setattr(answer_mod, "stream_completion", unexpected_provider)
    chunks = list(engine.stream_chat(query, prepared=prepared))
    meta = json.loads(chunks[0].split("\n[STREAM_START]\n", 1)[0])
    assert meta["synthesis_mode"] == "verified_deterministic"
    assert meta["provider_status"] == "not_invoked"


def test_worked_example_and_non_evidence_backed_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worked-example queries pass explicit illustrative-example and limitation guidance."""
    engine = Engine(FIXTURE_GRAPH)
    query = "Explain Third Normal Form (3NF) with a worked example."
    prepared = engine.answer(query)
    captured_safe_text: list[str] = []

    monkeypatch.setattr(
        answer_mod,
        "provider_config",
        lambda: {"provider": "xkiro", "base_url": "https://xkiro.invalid", "key": "k", "model": "m"},
    )
    monkeypatch.setattr(answer_mod, "fallback_config", lambda _cfg: None)

    def fake_stream(_cfg, safe_text: str, *_args, **_kwargs):
        captured_safe_text.append(safe_text)
        yield "### Direct Answer\n3NF removes transitive dependencies."

    monkeypatch.setattr(answer_mod, "stream_completion", fake_stream)
    monkeypatch.setattr(
        answer_mod, "last_stream_outcome", lambda: {"status": "complete", "finish_reason": "stop"}
    )
    monkeypatch.setattr(answer_mod, "last_provider_error", lambda: None)

    list(engine.stream_chat(query, prepared=prepared))
    assert captured_safe_text
    assert "independently derived" in captured_safe_text[0].lower()


def test_b_plus_tree_preserved_and_markdown_cleaned() -> None:
    """B+ Tree must never be stripped into 'B Tree'; headings and sections stay clean."""
    engine = Engine(FIXTURE_GRAPH)
    assert compose.resolve_fragment(engine, "B+ Tree") == ("b_plus_tree", True)
    assert compose.resolve_fragment(engine, "B+ trees") == ("b_plus_tree", True)

    engine.graph._query = "Compare B+ Tree vs Hash Indexing"
    mat = compose.matrix(engine, "b_plus_tree", "hash_indexing")
    assert "B+ Tree" in mat
    assert "B Tree ×" not in mat  # noqa: RUF001

    messy = (
        "###**Direct Answer**\nB Tree keeps keys in leaves.\n\n\n\n"
        "**Sources:**\n- [S1: A]\n\n"
        "**Sources:**\n- [S1: A]\n\n"
        "---\n### Institutional e-books\n* Book A\n\n"
        "---\n### Institutional e-books\n* Book A"
    )
    cleaned = render.clean_reply_markdown(messy, query="Compare B+ Tree vs Hash Indexing")
    assert "### Direct Answer" in cleaned
    assert "###**" not in cleaned
    assert "B+ Tree keeps keys in leaves." in cleaned
    assert cleaned.count("**Sources:**") == 1
    assert cleaned.count("### Institutional e-books") == 1


def test_no_duplicate_sources_in_stream_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """When LLM output already includes a Sources section, stream_chat must not append another."""
    engine = Engine(FIXTURE_GRAPH)
    prepared = engine.answer("What is BERT?")
    monkeypatch.setattr(
        answer_mod,
        "provider_config",
        lambda: {"provider": "xkiro", "base_url": "https://xkiro.invalid", "key": "k", "model": "m"},
    )
    monkeypatch.setattr(answer_mod, "fallback_config", lambda _cfg: None)
    monkeypatch.setattr(
        answer_mod,
        "stream_completion",
        lambda *_a, **_kw: iter(
            [
                "### Direct Answer\nBERT uses masked language modeling and next-sentence prediction for bidirectional pre-training.\n\n**Sources:**\n- [S1: BERT]"
            ]
        ),
    )
    monkeypatch.setattr(
        answer_mod, "last_stream_outcome", lambda: {"status": "complete", "finish_reason": "stop"}
    )
    monkeypatch.setattr(answer_mod, "last_provider_error", lambda: None)

    raw = "".join(engine.stream_chat("What is BERT?", prepared=prepared))
    body = raw.split("\n[STREAM_START]\n", 1)[1]
    assert body.count("**Sources:**") == 1


def test_llm_system_prompt_mandates_structured_task_completeness() -> None:
    """REPLY_SYSTEM_PROMPT must enforce structure, illustrative labeling, and B+ Tree fidelity."""
    prompt = llm.REPLY_SYSTEM_PROMPT
    assert "Direct Answer" in prompt
    assert "Worked Example" in prompt
    assert "Limitations" in prompt
    assert "B+ Tree" in prompt


# ── Section 2: Citation & Source Navigation Integrity ────────────────────────


def test_explicit_source_kind_and_url_validation() -> None:
    """Validate all four source_kind classes and block broken /read? links."""
    # 1. Verified HF-backed OA PDF -> verified_full_text_passage
    valid_pdf = citation_format.sanitize_citation_record(
        {
            "label": "[S1: OSTEP Paging, #page=3]",
            "evidence_id": "S1",
            "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
            "doc_title": "OSTEP Paging",
            "source_type": "ingested_pdf",
            "source_category": "oa_full_text_textbook",
            "page_number": 3,
            "url": "/read?doc=archipelago-books-cs%2Fostep_three_easy_pieces%2F08_Paging.pdf&page=3",
            "reader_resolvable": True,
        },
        open_access_only=True,
    )
    assert valid_pdf["source_kind"] == citation_format.SOURCE_KIND_VERIFIED_FULL_TEXT
    assert valid_pdf["clickable"] is True
    assert "/read?doc=" in valid_pdf["url"] and "&page=3" in valid_pdf["url"]

    # 2. Text card (.txt) -> metadata_only_record, NEVER clickable /read? link
    txt_card = citation_format.sanitize_citation_record(
        {
            "label": "[S2: Silberschatz 3NF Card]",
            "evidence_id": "S2",
            "doc_id": "pilot/silberschatz_3nf_card.txt",
            "doc_title": "Silberschatz 3NF Card",
            "source_type": "ingested_pdf",
            "page_number": 1,
            "url": "/read?doc=pilot%2Fsilberschatz_3nf_card.txt&page=1",
            "reader_resolvable": True,
        },
        open_access_only=True,
    )
    assert txt_card["source_kind"] == citation_format.SOURCE_KIND_METADATA_ONLY
    assert txt_card["url"] == ""
    assert txt_card["clickable"] is False

    # 3. Missing Tanenbaum PDF p.545 -> unavailable_document, NEVER /read?doc=...&page=545
    tanenbaum = citation_format.sanitize_citation_record(
        {
            "label": "[S3: Computer Networks (Tanenbaum), #page=545]",
            "evidence_id": "S3",
            "doc_id": "textbooks/computer_networks_tanenbaum.pdf",
            "doc_title": "Computer Networks",
            "source_type": "ingested_pdf",
            "page_number": 545,
            "url": "/read?doc=textbooks%2Fcomputer_networks_tanenbaum.pdf&page=545",
            "reader_resolvable": True,
        },
        open_access_only=True,
    )
    assert tanenbaum["source_kind"] == citation_format.SOURCE_KIND_UNAVAILABLE
    assert tanenbaum["url"] == ""
    assert tanenbaum["page_number"] is None
    assert tanenbaum["clickable"] is False
    assert "/read?" not in citation_format.citation_link(tanenbaum)

    # 4. Pearson institutional record -> institutional_licensed, stripped in open_access mode
    pearson = citation_format.sanitize_citation_record(
        {
            "label": "[S4: Database Systems]",
            "evidence_id": "S4",
            "doc_id": "doc_fundamentals_of_database_system_7e",
            "source_category": "pearson_catalogue_only",
            "is_pearson": True,
            "url": "/open/4268f15e-ac2c-40dd-bd12-aca2f02dd0ae",
            "reader_resolvable": True,
        },
        open_access_only=True,
    )
    assert pearson["source_kind"] == citation_format.SOURCE_KIND_INSTITUTIONAL
    assert pearson["url"] == ""
    assert pearson["clickable"] is False

    cleaned_list = citation_format.sanitize_citations([valid_pdf, txt_card, tanenbaum, pearson], open_access_only=True)
    assert all(c["source_kind"] != citation_format.SOURCE_KIND_INSTITUTIONAL for c in cleaned_list)


def test_page_bounds_validation_rejects_out_of_bounds_page() -> None:
    """Out-of-bounds page numbers must be stripped from /read? URLs."""
    rec = citation_format.sanitize_citation_record(
        {
            "label": "[S1: BERT, #page=9999]",
            "evidence_id": "S1",
            "doc_id": "papers/Devlin2018_BERT.pdf",
            "source_type": "ingested_pdf",
            "source_category": "oa_research_paper",
            "page_number": 9999,
            "page_count": 16,
            "url": "/read?doc=papers%2FDevlin2018_BERT.pdf&page=9999",
            "reader_resolvable": True,
        },
        open_access_only=True,
    )
    assert rec["source_kind"] == citation_format.SOURCE_KIND_VERIFIED_FULL_TEXT
    assert rec["page_number"] is None
    assert rec["page_verified"] is False
    assert "&page=" not in rec["url"]


def test_open_access_mode_never_leaks_pearson_in_payload_or_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SIGIR open_access mode must strip Pearson links from both payload and markdown text."""
    monkeypatch.setenv("ARCHIPELAGO_ACCESS_PROFILE", "open_access")
    engine = Engine(FIXTURE_GRAPH)
    res = engine.answer("What is Third Normal Form (3NF) in relational database design?")
    payload = res["payload"]
    assert payload["open_access_only"] is True
    assert "### Institutional e-books" not in res["text"]
    assert "/open/" not in res["text"]
    assert "pearson.com" not in res["text"].lower()
    for cite in payload.get("citations") or []:
        assert cite.get("source_kind") != citation_format.SOURCE_KIND_INSTITUTIONAL
        assert "/open/" not in str(cite.get("url") or "")


def test_evidence_backed_boolean_is_false_when_zero_verified_sources() -> None:
    """evidence_backed must be True only when verified_full_text_passage citations exist."""
    engine = Engine(FIXTURE_GRAPH)
    bert_res = engine.answer("What is BERT?")
    assert bert_res["payload"]["evidence_backed"] is True
    assert bert_res["payload"]["trace"]["evidence_backed"] is True

    unindexed_res = engine.answer("Explain Spanner TrueTime and its prerequisites.")
    assert unindexed_res["payload"]["evidence_backed"] is False
    assert unindexed_res["payload"]["trace"]["evidence_backed"] is False


# ── Section 3: Reliability, Latency & D10-OS-C Pre-Header Timeout ────────────


def test_security_supabase_timeouts_are_bounded_tuples() -> None:
    """Supabase HTTP timeouts must use bounded (connect, read) tuples, never hang 95s."""
    for timeout in (security.SUPABASE_USER_TIMEOUT_SEC, security.SUPABASE_PROFILE_TIMEOUT_SEC):
        assert isinstance(timeout, tuple) and len(timeout) == 2
        connect_s, read_s = timeout
        assert 0 < connect_s <= 5.0
        assert 0 < read_s <= 8.0


def test_llm_pre_first_token_budget_and_exhausted_deadline_fast_exit() -> None:
    """Provider timeouts and pre-first-token budget must stay well under Vercel proxy limits."""
    assert llm.STREAM_CONNECT_TIMEOUT_SECONDS <= 6
    assert llm.STREAM_FIRST_TOKEN_TIMEOUT_SECONDS <= 10
    assert llm.PRE_FIRST_TOKEN_BUDGET_SECONDS <= 12.0
    assert llm.STREAM_TOTAL_DEADLINE_SECONDS <= 25

    t0 = time.perf_counter()
    cfg: llm.ProviderConfig = {
        "provider": "xkiro",
        "base_url": "https://xkiro.invalid",
        "key": "k",
        "model": "m",
    }
    # Already-expired first_token_deadline must return immediately without network call.
    out = list(llm.stream_completion(cfg, "evidence", "query", first_token_deadline=t0 - 1.0))
    elapsed = time.perf_counter() - t0
    assert out == []
    assert elapsed < 1.0
    assert (llm.last_provider_error() or {}).get("error_type") == "first_token_timeout"


def test_chat_route_latency_fields_deterministic_vs_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """[STREAM_START] and [STREAM_META] must distinguish auth_ms, evidence_retrieval_ms,
    ttft_visible_ms, provider_ttft_ms (strictly None for deterministic), and total_ms.
    """
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    app = create_app()
    client = app.test_client()

    # 1. Deterministic route (greeting): provider_ttft_ms MUST be None in both frames.
    resp = client.post("/api/chat", json={"query": "Hello"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Accel-Buffering") == "no"
    raw = resp.get_data(as_text=True)
    head, tail = raw.split("\n[STREAM_START]\n", 1)
    start_meta = json.loads(head)
    timings = start_meta["stage_timings_ms"]
    assert isinstance(timings["auth_ms"], (int, float))
    assert "evidence_retrieval_ms" in timings
    assert isinstance(timings["ttft_visible_ms"], (int, float))
    assert timings["provider_ttft_ms"] is None
    assert "total_ms" in timings

    assert "[STREAM_META:" in tail
    meta_str = tail.split("[STREAM_META:", 1)[1].split("]", 1)[0]
    term_meta = json.loads(meta_str)
    assert isinstance(term_meta["auth_ms"], (int, float))
    assert "evidence_retrieval_ms" in term_meta
    assert isinstance(term_meta["ttft_visible_ms"], (int, float))
    assert term_meta["provider_ttft_ms"] is None
    assert isinstance(term_meta["total_ms"], (int, float)) and term_meta["total_ms"] >= 0.0

    # 2. Live synthesis route (D10-OS-C): provider_ttft_ms is numeric in both frames.
    monkeypatch.setattr(
        answer_mod,
        "provider_config",
        lambda: {"provider": "xkiro", "base_url": "https://xkiro.invalid", "key": "k", "model": "m"},
    )
    monkeypatch.setattr(answer_mod, "fallback_config", lambda _cfg: None)
    monkeypatch.setattr(
        answer_mod,
        "stream_completion",
        lambda *_a, **_kw: iter(
            ["### Direct Answer\nPrerequisites for paging and address translation include virtual memory and memory management."]
        ),
    )
    monkeypatch.setattr(
        answer_mod, "last_stream_outcome", lambda: {"status": "complete", "finish_reason": "stop"}
    )
    monkeypatch.setattr(answer_mod, "last_provider_error", lambda: None)

    resp_live = create_app().test_client().post(
        "/api/chat",
        json={"query": "What concepts are prerequisites for understanding paging and address translation?"},
    )
    assert resp_live.status_code == 200
    raw_live = resp_live.get_data(as_text=True)
    head_live, tail_live = raw_live.split("\n[STREAM_START]\n", 1)
    start_live = json.loads(head_live)
    timings_live = start_live["stage_timings_ms"]
    assert isinstance(timings_live["auth_ms"], (int, float))
    assert isinstance(timings_live["ttft_visible_ms"], (int, float))
    assert isinstance(timings_live["provider_ttft_ms"], (int, float))

    term_live_str = tail_live.split("[STREAM_META:", 1)[1].split("]", 1)[0]
    term_live = json.loads(term_live_str)
    assert isinstance(term_live["auth_ms"], (int, float))
    assert isinstance(term_live["ttft_visible_ms"], (int, float))
    assert isinstance(term_live["provider_ttft_ms"], (int, float))
    assert isinstance(term_live["total_ms"], (int, float)) and term_live["total_ms"] >= 0.0
