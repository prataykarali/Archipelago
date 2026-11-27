"""Isolated unit tests for D11-B-UX backend features (synthetic/non-benchmark queries)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest

HOST_INFERENCE_DIR = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST_INFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_INFERENCE_DIR))

from engine.access_profile import (  # noqa: E402
    ACCESS_PROFILE_ENV,
    ACCESS_PROFILE_INSTITUTIONAL,
    ACCESS_PROFILE_OPEN_ACCESS,
    active_access_profile,
    is_open_access_profile,
    strip_institutional_payload,
)
from engine.answer import Engine  # noqa: E402
from engine.catalogue import load_catalogue  # noqa: E402
from engine.citation_format import citation_link  # noqa: E402
from engine.conversational import (  # noqa: E402
    build_capability_reply,
    build_conversational_reply,
    build_unsupported_reply,
    classify_conversational_intent,
)
from engine.corpus_titles import OPEN_CORPUS_TITLES, clean_bibliographic_title  # noqa: E402
from engine.evidence_export import (  # noqa: E402
    EXPORT_SCHEMA_VERSION,
    REDACTED_MARKER,
    build_evidence_export,
    render_evidence_markdown,
)
from engine.followups import MAX_FOLLOW_UP_QUESTIONS, build_follow_up_questions  # noqa: E402
from engine.links import source_links  # noqa: E402
from engine.source_resolution import resolve_source_target  # noqa: E402
from engine.suggestions import (  # noqa: E402
    MAX_SUGGESTION_COUNT,
    MIN_SUGGESTION_COUNT,
    build_suggestions_payload,
    discover_knowledge_areas,
    generate_starter_questions,
)
from hostapp.context import AppContext  # noqa: E402
from hostapp.factory import create_app  # noqa: E402


class _FakeAuth:
    def required(self) -> bool:
        return False

    def supabase(self) -> tuple[str, str]:
        return ("", "")

    def principal(self) -> tuple[dict[str, Any] | None, str | None]:
        return (None, None)


class _FakeLimiter:
    def check_rate(self, *_args: Any, **_kwargs: Any) -> tuple[bool, int]:
        return (False, 0)

    def check_chat(self, *_args: Any, **_kwargs: Any) -> tuple[bool, int]:
        return (False, 0)

    def check_api(self, *_args: Any, **_kwargs: Any) -> tuple[bool, int]:
        return (False, 0)

    def check_auth(self, *_args: Any, **_kwargs: Any) -> tuple[bool, int]:
        return (False, 0)

    def quota_status(self, _uid: str) -> dict[str, Any]:
        return {"used": 0, "limit": 10, "remaining": 10}


class _FakeMetrics:
    def record_request(self) -> None:
        return None

    def record_miss(self) -> None:
        return None


def _write_synthetic_graph(tmp_path: Path) -> Path:
    """Create a small, self-contained synthetic concept graph for isolated testing."""
    data = {
        "stats": {"fixture": True},
        "nodes": [
            {
                "id": "virtual_memory",
                "label": "Virtual Memory",
                "summary": "Abstraction providing each process a private virtual address space.",
                "sources": [
                    {
                        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf",
                        "page_number": 4,
                        "chunk_id": "chunk_101",
                        "text_passage": "The OS creates an abstraction of physical memory called an address space.",
                    }
                ],
                "degree": 3,
                "source_count": 1,
            },
            {
                "id": "page_table",
                "label": "Page Table",
                "summary": "Per-process structure mapping virtual page numbers to physical frames.",
                "sources": [
                    {
                        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
                        "page_number": 3,
                        "chunk_id": "chunk_202",
                        "text_passage": "A page table stores address translations for each virtual page.",
                    }
                ],
                "degree": 2,
                "source_count": 1,
            },
            {
                "id": "tlb_cache",
                "label": "Translation Lookaside Buffer",
                "summary": "Hardware cache accelerating virtual-to-physical address translations.",
                "sources": [
                    {
                        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/09_TLBs.pdf",
                        "page_number": 2,
                        "chunk_id": "chunk_303",
                        "text_passage": "A TLB is part of the chip's memory-management unit.",
                    }
                ],
                "degree": 2,
                "source_count": 1,
            },
            {
                "id": "self_attention",
                "label": "Scaled Dot-Product Attention",
                "summary": "Computes weighted combinations of values from query-key similarity scores.",
                "sources": [
                    {
                        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
                        "page_number": 4,
                        "chunk_id": "chunk_404",
                        "text_passage": "We call our particular attention Scaled Dot-Product Attention.",
                    }
                ],
                "degree": 2,
                "source_count": 1,
            },
            {
                "id": "low_rank_adaptation",
                "label": "LoRA",
                "summary": "Freezes pretrained weights and injects trainable low-rank matrices.",
                "sources": [
                    {
                        "doc_id": "papers/Hu2021_LoRA.pdf",
                        "page_number": 3,
                        "chunk_id": "chunk_505",
                        "text_passage": "LoRA constrains weight updates via a low-rank decomposition.",
                    }
                ],
                "degree": 1,
                "source_count": 1,
            },
            {
                "id": "dense_retrieval",
                "label": "Dense Passage Retrieval",
                "summary": "Uses dual encoders to retrieve relevant passages in dense vector space.",
                "sources": [
                    {
                        "doc_id": "papers/Karpukhin2020_DPR.pdf",
                        "page_number": 2,
                        "chunk_id": "chunk_606",
                        "text_passage": "DPR learns dense representations for questions and passages.",
                    }
                ],
                "degree": 1,
                "source_count": 1,
            },
            {
                "id": "eigendecomposition",
                "label": "Eigenvalues and Eigenvectors",
                "summary": "Linear transformations scaling characteristic vectors without changing direction.",
                "sources": [
                    {
                        "doc_id": "textbooks/Deisenroth_Math_For_ML.pdf",
                        "page_number": 112,
                        "chunk_id": "chunk_707",
                        "text_passage": "An eigenvector satisfies A x = lambda x.",
                    }
                ],
                "degree": 1,
                "source_count": 1,
            },
        ],
        "edges": [
            {"from_id": "page_table", "to_id": "virtual_memory", "edge_type": "REQUIRES"},
            {"from_id": "page_table", "to_id": "tlb_cache", "edge_type": "UNLOCKS"},
            {"from_id": "virtual_memory", "to_id": "tlb_cache", "edge_type": "RELATED"},
            {"from_id": "low_rank_adaptation", "to_id": "self_attention", "edge_type": "REQUIRES"},
        ],
    }
    graph_path = tmp_path / "synthetic_okf_graph.json"
    graph_path.write_text(json.dumps(data), encoding="utf-8")
    return graph_path


@pytest.fixture()
def synthetic_engine(tmp_path: Path) -> Engine:
    return Engine(graph_path=_write_synthetic_graph(tmp_path))


@pytest.fixture()
def synthetic_client(synthetic_engine: Engine):
    ctx = AppContext(
        engine=synthetic_engine,
        auth=_FakeAuth(),
        limiter=_FakeLimiter(),
        inventory=None,
        cache_service=None,
        cache_metrics=_FakeMetrics(),
        request_dedup=None,
    )
    app = create_app(ctx)
    app.config["TESTING"] = True
    return app.test_client()


# ── 1. Deterministic conversational intents ───────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("Hello!", "greeting"),
        ("good morning", "greeting"),
        ("Thanks a lot!", "thanks"),
        ("thank you", "thanks"),
        ("goodbye", "farewell"),
        ("help", "help"),
        ("how do I use this?", "help"),
        ("who are you?", "help"),
    ],
)
def test_conversational_intent_classification(query: str, expected_intent: str) -> None:
    assert classify_conversational_intent(query) == expected_intent


@pytest.mark.unit
def test_conversational_and_capability_replies_use_zero_llm_calls(
    synthetic_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_called = False

    def _forbid_llm(*_args: Any, **_kwargs: Any):
        nonlocal llm_called
        llm_called = True
        raise AssertionError("External LLM must not be called for deterministic intents")

    monkeypatch.setattr("engine.answer.stream_completion", _forbid_llm)
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_OPEN_ACCESS)

    for query in ("hello", "thank you", "help", "what topics do you cover?"):
        chunks = list(synthetic_engine.stream_chat(query))
        assert chunks, f"Expected deterministic stream output for {query!r}"
        meta = json.loads(chunks[0].split("\n[STREAM_START]\n", 1)[0])
        body = "".join(chunks[1:])
        assert meta["synthesis_mode"] == "verified_deterministic"
        assert meta["model"]["provider"] == "deterministic"
        assert "Pearson" not in body
        assert "UEM Kolkata" not in body
        assert isinstance(meta.get("follow_up_questions"), list)

    assert not llm_called


@pytest.mark.unit
def test_capability_reply_uses_live_concept_count(
    synthetic_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_OPEN_ACCESS)
    reply = build_capability_reply(synthetic_engine.graph)
    assert f"`{len(synthetic_engine.graph.nodes)}`" in reply
    assert "1." in reply
    assert "Pearson" not in reply


# ── 2. Dynamic welcome suggestions & supported-topic discovery ────────────────


@pytest.mark.unit
def test_dynamic_suggestions_derive_from_graph_without_hardcoded_counts(
    synthetic_engine: Engine, synthetic_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_OPEN_ACCESS)
    resp = synthetic_client.get("/api/chat/suggestions?seed=42&count=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["access_profile"] == ACCESS_PROFILE_OPEN_ACCESS
    assert data["open_access_only"] is True
    assert data["total_concepts"] == len(synthetic_engine.graph.nodes)

    areas = data["knowledge_areas"]
    assert areas, "Expected dynamically discovered knowledge areas"
    assert [a["index"] for a in areas] == list(range(1, len(areas) + 1))

    questions = data["suggested_questions"]
    assert MIN_SUGGESTION_COUNT <= len(questions) <= MAX_SUGGESTION_COUNT
    valid_labels = {
        str(node.get("label") or "") for node in synthetic_engine.graph.nodes.values()
    }
    for q in questions:
        assert any(lbl in q for lbl in valid_labels), f"Unindexed concept in suggestion: {q!r}"

    # Different seeds should shuffle questions rather than returning a static list.
    q_a = generate_starter_questions(synthetic_engine.graph, count=5, seed=1)
    q_b = generate_starter_questions(synthetic_engine.graph, count=5, seed=99)
    assert q_a != q_b


@pytest.mark.unit
def test_discover_knowledge_areas_reflects_empty_graph() -> None:
    class _EmptyGraph:
        def __init__(self) -> None:
            self.nodes: dict[str, Any] = {}

    areas = discover_knowledge_areas(_EmptyGraph())
    for area in areas:
        assert area["concept_count"] == 0


# ── 3. Contextual follow-up recommendations ───────────────────────────────────


@pytest.mark.unit
def test_follow_up_questions_grounded_and_never_claim_unreviewed_edges_verified(
    synthetic_engine: Engine,
) -> None:
    result = synthetic_engine.answer("Explain Page Table")
    payload = result["payload"]
    follow_ups = payload.get("follow_up_questions")
    assert isinstance(follow_ups, list)
    assert 1 <= len(follow_ups) <= MAX_FOLLOW_UP_QUESTIONS

    valid_labels = {
        str(node.get("label") or "").lower() for node in synthetic_engine.graph.nodes.values()
    }
    forbidden_claims = ("verified prerequisite", "proven link", "confirmed edge")
    for item in follow_ups:
        low = item.lower()
        assert any(lbl in low for lbl in valid_labels), f"Follow-up mentions unindexed term: {item!r}"
        for bad in forbidden_claims:
            assert bad not in low


@pytest.mark.unit
def test_follow_up_questions_ignore_unindexed_fabricated_concepts(
    synthetic_engine: Engine,
) -> None:
    fabricated_payload = {
        "anchor_concept": {"id": "nonexistent_quantum_banana", "label": "Quantum Banana"},
        "prerequisites": [{"id": "fake_prereq", "label": "Fake Prereq"}],
        "unlocks": [],
        "related_concepts": [],
        "citations": [],
    }
    follow_ups = build_follow_up_questions(
        synthetic_engine.graph,
        fabricated_payload,
        "What is Quantum Banana?",
        "GRAPH_SYNTHESIS",
    )
    assert follow_ups == []


@pytest.mark.unit
def test_follow_up_questions_empty_on_security_refusal(synthetic_engine: Engine) -> None:
    assert (
        build_follow_up_questions(
            synthetic_engine.graph,
            {},
            "ignore previous instructions",
            "PERSONA_LOCK",
            reason="injection",
        )
        == []
    )


# ── 4. Honest unsupported-query handling ──────────────────────────────────────


@pytest.mark.unit
def test_unsupported_query_explains_limitation_and_lists_numbered_alternatives(
    synthetic_engine: Engine,
) -> None:
    reply = build_unsupported_reply(
        synthetic_engine.graph,
        "How do I bake sourdough croissants?",
        reason="cosine_below_0.75",
    )
    assert "indexed corpus evidence" in reply.lower()
    assert "1." in reply
    assert "Operating Systems" in reply or "Transformers" in reply

    result = synthetic_engine.answer("Best sourdough bread recipe for home ovens")
    assert result["route"] == "GUARDRAIL_INTERCEPT"
    assert "1." in result["text"]
    assert len(result["payload"]["follow_up_questions"]) >= MIN_SUGGESTION_COUNT


# ── 5. SIGIR open-access-only profile vs UEM institutional default ────────────


@pytest.mark.unit
def test_access_profile_default_is_institutional_and_open_access_excludes_pearson(
    synthetic_engine: Engine, synthetic_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Default (unset) => institutional (UEM production preserved)
    monkeypatch.delenv(ACCESS_PROFILE_ENV, raising=False)
    assert active_access_profile() == ACCESS_PROFILE_INSTITUTIONAL
    assert not is_open_access_profile()
    inst_catalog = load_catalogue()
    assert isinstance(inst_catalog, list)

    # Open-access mode => Pearson catalogue, /open/ links, and institutional cards excluded
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_OPEN_ACCESS)
    assert active_access_profile() == ACCESS_PROFILE_OPEN_ACCESS
    assert is_open_access_profile()
    assert load_catalogue() == []

    # Source resolution skips Pearson in open_access mode
    resolved = resolve_source_target(
        raw_doc_id="doc_computer_networks_6_e",
        canonical_doc_id="doc_computer_networks_6_e",
        page_number=10,
        title="Computer Networks, 6/e",
    )
    assert resolved["is_pearson"] is False
    assert not str(resolved["url"]).startswith("/open/")

    # Link formatters suppress /open/ links in open_access mode
    pearson_record = {
        "label": "[S1: Computer Networks]",
        "evidence_id": "S1",
        "doc_id": "doc_computer_networks_6_e",
        "doc_title": "Computer Networks, 6/e",
        "url": "/open/pearson-book-123",
        "is_pearson": True,
        "reader_resolvable": True,
    }
    assert citation_link(pearson_record) == ""
    assert "/open/" not in source_links(pearson_record, {"id": "pearson-book-123", "title": "CN"})

    # Payload sanitizer removes Pearson cards & /open/ citations
    dirty_payload: dict[str, Any] = {
        "citations": [
            pearson_record,
            {
                "doc_id": "papers/Hu2021_LoRA.pdf",
                "url": "/read?doc=papers%2FHu2021_LoRA.pdf&page=3",
                "is_pearson": False,
            },
        ],
        "inventory": [{"title": "Pearson Book", "publisher": "Pearson eLibrary", "reader_url": "/open/1"}],
        "digital_resources": [{"title": "Closed Ebook", "resource_type": "institutional_e_book"}],
    }
    clean_payload = strip_institutional_payload(dirty_payload)
    assert clean_payload["open_access_only"] is True
    assert len(clean_payload["citations"]) == 1
    assert clean_payload["inventory"] == []
    assert clean_payload["digital_resources"] == []

    # HTTP routes enforce open_access isolation
    open_resp = synthetic_client.get("/open/any-pearson-id")
    assert open_resp.status_code == 404
    assert open_resp.get_json()["error"] == "unavailable_in_open_access"

    cat_resp = synthetic_client.get("/api/catalog/all")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.get_json()
    assert cat_data["open_access_only"] is True
    assert all(not d.get("is_pearson") for d in cat_data["documents"])
    assert all(not str(d.get("open_url") or "").startswith("/open/") for d in cat_data["documents"])

    auth_resp = synthetic_client.get("/api/auth/config")
    assert auth_resp.status_code == 200
    auth_data = auth_resp.get_json()
    assert auth_data["access_profile"] == ACCESS_PROFILE_OPEN_ACCESS
    assert auth_data["open_access_only"] is True


# ── 6. Clean bibliographic titles (all 43 open corpus docs) & evidence export ─


@pytest.mark.unit
def test_all_43_open_corpus_docs_have_clean_bibliographic_titles() -> None:
    hf_files_path = HOST_INFERENCE_DIR / "fixtures" / "hf_files.json"
    raw = json.loads(hf_files_path.read_text(encoding="utf-8"))
    unique_open_basenames = sorted(
        {
            p.rsplit("/", 1)[-1].lower()
            for p in raw.get("pdfs", [])
            if "librarian_uploads/" not in p.lower()
        }
    )
    assert len(unique_open_basenames) == 43
    for base in unique_open_basenames:
        assert base in OPEN_CORPUS_TITLES, f"Missing bibliographic title for {base}"
        title = clean_bibliographic_title(base)
        assert not title.lower().endswith(".pdf")
        assert "_" not in title
        assert len(title) >= 15


@pytest.mark.unit
def test_evidence_export_includes_required_fields_and_scrubs_credentials(
    synthetic_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_OPEN_ACCESS)
    fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEifQ.signature_secret_val"
    dirty_metadata: dict[str, Any] = {
        "route": "GRAPH_SYNTHESIS",
        "contract": "GRAPH_SYNTHESIS",
        "authorization": "Bearer super_secret_token_12345",
        "cookie": "archipelago_token=secret_cookie_val; archipelago_csrf=csrf123",
        "api_key": "sk-live-abcdef1234567890",
        "anchor_concept": {
            "id": "page_table",
            "label": "Page Table",
            "summary": "Maps virtual pages to physical frames.",
        },
        "prerequisites": [{"id": "virtual_memory", "label": "Virtual Memory"}],
        "unlocks": [{"id": "tlb_cache", "label": "Translation Lookaside Buffer"}],
        "citations": [
            {
                "evidence_id": "S1",
                "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
                "page_number": 3,
                "chunk_id": "chunk_202",
                "canonical_passage_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf::chunk_202",
                "provenance_status": "provenance_verified",
                "claim_support_status": "not_assessed",
                "url": "/read?doc=08_Paging.pdf&page=3",
                "hf_token": "hf_secretToken1234567890",
            }
        ],
        "trace": {
            "intent": "GRAPH_SYNTHESIS",
            "passage_ids": ["archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf::chunk_202"],
            "session_token": fake_jwt,
        },
    }

    bundle = build_evidence_export(
        query="Explain Page Table with Bearer my_leaked_token_abc",
        answer=f"A page table maps pages. Debug: hf_leakedtoken99999999 {fake_jwt}",
        payload=dirty_metadata,
    )
    serialized = json.dumps(bundle)
    assert bundle["schema_version"] == EXPORT_SCHEMA_VERSION
    assert "super_secret_token_12345" not in serialized
    assert "secret_cookie_val" not in serialized
    assert "sk-live-abcdef1234567890" not in serialized
    assert "hf_secretToken1234567890" not in serialized
    assert "hf_leakedtoken99999999" not in serialized
    assert fake_jwt not in serialized
    assert REDACTED_MARKER in bundle["query"]
    assert REDACTED_MARKER in bundle["answer"]
    assert bundle["citations"][0]["doc_title"].startswith("Operating Systems: Three Easy Pieces — Ch. 8")
    assert "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf::chunk_202" in bundle["passage_ids"]
    assert any(e["relation"] == "REQUIRES" for e in bundle["graph_edges"])
    assert any(e["relation"] == "UNLOCKS" for e in bundle["graph_edges"])

    md = render_evidence_markdown(bundle)
    assert "# Archipelago Evidence Export" in md
    assert "Operating Systems: Three Easy Pieces — Ch. 8" in md

    # Endpoint test
    resp = synthetic_client.post(
        "/api/chat/export",
        json={
            "query": "Explain Page Table",
            "answer": "A page table maps virtual pages.",
            "metadata": dirty_metadata,
            "format": "markdown",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert "markdown" in payload and "bundle" in payload
    assert fake_jwt not in json.dumps(payload)


@pytest.mark.unit
def test_build_suggestions_payload_clamps_count(synthetic_engine: Engine) -> None:
    small = build_suggestions_payload(synthetic_engine.graph, count=1, seed=7)
    large = build_suggestions_payload(synthetic_engine.graph, count=99, seed=7)
    assert len(small["suggested_questions"]) == MIN_SUGGESTION_COUNT
    assert len(large["suggested_questions"]) == MAX_SUGGESTION_COUNT


@pytest.mark.unit
def test_build_conversational_reply_all_intents(synthetic_engine: Engine) -> None:
    for intent in ("greeting", "thanks", "farewell", "help"):
        route, text, extra = build_conversational_reply(synthetic_engine.graph, intent)
        assert route == "GREETING"
        assert text.strip()
        assert extra["hide_graph"] is True
        assert extra["conversational_intent"] == intent
