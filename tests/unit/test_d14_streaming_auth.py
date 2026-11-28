"""Unit tests for Phase D14.7 Track A (auth/cold-start/chat-hang) & Track B (streaming/cache/trace)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_INFERENCE_DIR = REPO_ROOT / "host_inference"
if str(HOST_INFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_INFERENCE_DIR))


@pytest.mark.unit
def test_remote_cache_hydrate_sets_cooldown_and_skips_pearson_in_open_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """hydrate() must set _LAST_HYDRATE_ATTEMPT so load_books() never double-hydrates."""
    import remote_cache

    calls: list[str] = []

    class _FakeResp:
        status_code = 404
        content = b""

    def _fake_get(url: str, **kwargs: Any) -> _FakeResp:
        calls.append(url)
        return _FakeResp()

    monkeypatch.setattr(remote_cache, "CACHE", tmp_path)
    monkeypatch.setattr(remote_cache, "_LAST_HYDRATE_ATTEMPT", 0.0)
    monkeypatch.setattr(remote_cache, "_headers", lambda: {"url": "https://example.supabase.co", "apikey": "k"})
    monkeypatch.setattr(remote_cache.requests, "get", _fake_get)
    monkeypatch.setenv("ARCHIPELAGO_ACCESS_PROFILE", "open_access")

    remote_cache.hydrate()
    first_count = len(calls)
    assert first_count == 2  # okf_graph.json + library_manifest.json (pearson_bookshelf.json skipped)
    assert all("pearson_bookshelf.json" not in u for u in calls)
    assert remote_cache._LAST_HYDRATE_ATTEMPT > 0.0

    # Immediate load_books() must NOT trigger a second hydrate() within cooldown.
    remote_cache.load_books()
    assert len(calls) == first_count


@pytest.mark.unit
def test_library_index_skips_live_hf_fetch_when_manifest_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cold start must not block on Hugging Face Hub API when manifest paths exist."""
    import library_index
    import remote_cache

    hf_calls: list[str] = []

    monkeypatch.setattr(library_index, "_HF_PATHS_CACHE", (0.0, [], {}))
    monkeypatch.setenv("HF_TOKEN", "fake-token-for-test")
    monkeypatch.setattr(
        remote_cache,
        "load_library_manifest",
        lambda: {"hf_paths": ["ostep_three_easy_pieces/08_Paging.pdf"]},
    )
    monkeypatch.setattr(
        library_index,
        "_fetch_hf_repo_pdfs",
        lambda repo, token: hf_calls.append(repo) or [],
    )

    paths, repo_map = library_index._load_hf_repo_map()
    assert paths == ["ostep_three_easy_pieces/08_Paging.pdf"]
    assert repo_map["ostep_three_easy_pieces/08_Paging.pdf"]
    assert hf_calls == []


@pytest.mark.unit
def test_lazy_engine_proxy_defers_init_until_accessed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auth/HTML routes must not pay Engine.__init__() cold-start cost."""
    from hostapp.factory import _LazyEngineProxy

    created: list[str] = []

    class _FakeEngine:
        def __init__(self) -> None:
            created.append("init")
            self.graph_tag = "okf-610"

    import engine as engine_mod

    monkeypatch.setattr(engine_mod, "Engine", _FakeEngine)

    proxy = _LazyEngineProxy()
    assert created == []
    assert proxy.graph_tag == "okf-610"
    assert created == ["init"]
    assert proxy.graph_tag == "okf-610"
    assert len(created) == 1


@pytest.mark.unit
def test_llm_failover_budget_and_deadline_prevent_starvation_and_truncation() -> None:
    """Primary provider must leave >=5s for fallback, and stream deadline must be >=45s."""
    from engine import llm
    from hostapp.routes import chat as chat_routes

    remaining_for_fallback = llm.PRE_FIRST_TOKEN_BUDGET_SECONDS - llm.STREAM_FIRST_TOKEN_TIMEOUT_SECONDS
    assert remaining_for_fallback >= 5.0
    assert llm.STREAM_TOTAL_DEADLINE_SECONDS >= 45
    assert chat_routes.CHAT_REQUEST_DEADLINE_SECONDS >= 45.0
    assert llm.REPLY_MAX_TOKENS >= 1200
    assert llm.SSE_CHUNK_BYTES is None


@pytest.mark.unit
def test_versioned_cache_keys_isolate_tenants_profiles_and_versions() -> None:
    """Cache keys must never collide across users, access profiles, graph, corpus, or release."""
    from cache_service import CacheService

    svc = CacheService()
    k_u1 = svc.build_versioned_key(
        "What is paging?",
        tenant_scope="user:u1:role:student",
        access_profile="open_access",
        graph_version="g1",
        corpus_version="c1",
        release_sha="sha1",
    )
    k_u2 = svc.build_versioned_key(
        "What is paging?",
        tenant_scope="user:u2:role:student",
        access_profile="open_access",
        graph_version="g1",
        corpus_version="c1",
        release_sha="sha1",
    )
    k_inst = svc.build_versioned_key(
        "What is paging?",
        tenant_scope="user:u1:role:student",
        access_profile="institutional",
        graph_version="g1",
        corpus_version="c1",
        release_sha="sha1",
    )
    k_g2 = svc.build_versioned_key(
        "What is paging?",
        tenant_scope="user:u1:role:student",
        access_profile="open_access",
        graph_version="g2",
        corpus_version="c1",
        release_sha="sha1",
    )
    k_c2 = svc.build_versioned_key(
        "What is paging?",
        tenant_scope="user:u1:role:student",
        access_profile="open_access",
        graph_version="g1",
        corpus_version="c2",
        release_sha="sha1",
    )
    assert len({k_u1, k_u2, k_inst, k_g2, k_c2}) == 5

    svc.set_versioned_entry(k_u1, {"metadata": {"ok": True}, "text": "Paging answer"})
    hit = svc.get_versioned_entry(k_u1)
    assert hit is not None
    assert hit["text"] == "Paging answer"
    assert svc.get_versioned_entry(k_u2) is None


@pytest.mark.unit
def test_chat_route_emits_full_trace_and_tenant_isolated_cache_hits() -> None:
    """POST /api/chat must emit complete trace fields, null for missing timings, and tenant-isolated cache hits."""
    from cache_service import CacheMetrics, CacheService, RequestDeduplicator
    from flask import Flask
    from hostapp.context import AppContext
    from hostapp.routes.chat import STREAM_MARKER, register

    stream_calls: list[str] = []

    class _FakeGraph:
        graph_version = "g-d14-test"
        corpus_source = "full"

    class _FakeCatalog:
        candidate_passages_info: ClassVar[dict[str, str]] = {
            "sha256": "93f6db39cb10d03beeb41c48469d138b"
        }

    class _FakeEngine:
        graph = _FakeGraph()
        catalog = _FakeCatalog()

        def answer(self, query: str) -> dict[str, Any]:
            return {
                "route": "GENERAL_EXPLANATION",
                "text": "Paging maps virtual pages to physical frames.",
                "payload": {"citations": [], "trace": {"retrieval_mode": "graph_assisted"}},
                "evidence_retrieval_ms": 12.5,
            }

        def stream_chat(self, query: str, **kwargs: Any):
            stream_calls.append(query)
            prepared = kwargs.get("prepared") or self.answer(query)
            payload = dict(prepared["payload"])
            payload["provider"] = "xkiro"
            payload["model"] = {"provider": "xkiro", "model": "cohere/command-a"}
            yield json.dumps(payload) + STREAM_MARKER
            yield "Paging maps virtual pages to physical frames."
            yield "\n[STREAM_META:" + json.dumps(
                {
                    "provider_status": "complete",
                    "fallback_reason": None,
                    "stream_status": "complete",
                    "provider_ttft_ms": 180.0,
                }
            ) + "]\n"

    class _FakeAuth:
        def required(self) -> bool:
            return False

    app = Flask(__name__)
    ctx = AppContext(
        engine=_FakeEngine(),
        auth=_FakeAuth(),
        limiter=None,
        inventory=None,
        cache_service=CacheService(),
        cache_metrics=CacheMetrics(),
        request_dedup=RequestDeduplicator(),
    )
    register(app, ctx)
    client = app.test_client()

    # First request -> cache miss, full trace emitted
    r1 = client.post("/api/chat", json={"query": "Explain paging"})
    assert r1.status_code == 200
    body1 = r1.get_data(as_text=True)
    head1, rest1 = body1.split(STREAM_MARKER, 1)
    meta1 = json.loads(head1)
    trace1 = meta1["trace"]
    for required_key in (
        "request_id",
        "release_sha",
        "graph_version",
        "corpus_version",
        "generation_mode",
        "provider",
        "model",
        "cache_status",
        "stage_timings_ms",
    ):
        assert required_key in trace1
    assert trace1["cache_status"] == "miss"
    assert trace1["stage_timings_ms"]["reranking_ms"] is None
    assert trace1["stage_timings_ms"]["auth_ms"] is None
    assert "[STREAM_META:" in rest1
    tmeta1 = json.loads(rest1.split("[STREAM_META:", 1)[1].split("]", 1)[0])
    assert tmeta1["completion_status"] == "complete"
    assert isinstance(tmeta1["total_ms"], (int, float))
    assert len(stream_calls) == 1

    # Second identical first-turn request -> cache hit (no second stream_chat call)
    r2 = client.post("/api/chat", json={"query": "Explain paging"})
    assert r2.status_code == 200
    body2 = r2.get_data(as_text=True)
    meta2 = json.loads(body2.split(STREAM_MARKER, 1)[0])
    assert meta2["trace"]["cache_status"] == "hit"
    assert meta2["trace"]["completion_status"] == "complete"
    assert len(stream_calls) == 1
    assert ctx.cache_metrics.cache_hits == 1


@pytest.mark.unit
def test_frontend_auth_logout_and_streaming_contracts_and_mirror_sync() -> None:
    """Verify Track A + B frontend fixes and host_inference/ui <-> ui/chat mirror parity."""
    mirrored = [
        "auth_bridge.js",
        "login.html",
        "js/index.js",
        "js/00-current-origin.js",
        "js/08-send-request.js",
        "js/08-send-message.js",
        "js/stream-markers.js",
    ]
    for rel in mirrored:
        a = (REPO_ROOT / "host_inference" / "ui" / rel).read_text(encoding="utf-8")
        b = (REPO_ROOT / "ui" / "chat" / rel).read_text(encoding="utf-8")
        assert a == b, f"Mirror drift detected for {rel}"

    auth_js = (REPO_ROOT / "host_inference" / "ui" / "auth_bridge.js").read_text(encoding="utf-8")
    logout_block = auth_js.split("window.archipelagoLogout = async", 1)[1].split("async function loadConfig", 1)[0]
    assert 'cachedAccessToken = ""' in logout_block
    assert 'fetch("/api/auth/logout"' in logout_block
    assert 'fetch("/api/auth/session"' not in logout_block
    assert 'scope: "local"' in logout_block
    assert "inFlightMePromise" in auth_js

    login_html = (REPO_ROOT / "host_inference" / "ui" / "login.html").read_text(encoding="utf-8")
    assert '<link rel="prefetch" href="/chat">' not in login_html

    index_js = (REPO_ROOT / "host_inference" / "ui" / "js" / "index.js").read_text(encoding="utf-8")
    assert "\nawait window.archipelagoRequireSession();" not in index_js

    send_js = (REPO_ROOT / "host_inference" / "ui" / "js" / "08-send-message.js").read_text(encoding="utf-8")
    assert "STREAM_FIRST_BYTE_TIMEOUT_MS" in send_js
    assert send_js.index("new AbortController()") < send_js.index("window.archipelagoVerifyChatSession")

    markers_js = (REPO_ROOT / "host_inference" / "ui" / "js" / "stream-markers.js").read_text(encoding="utf-8")
    assert "MARKER_TAIL_GUARD = 512" in markers_js
    assert "trace.stage_timings_ms" in markers_js
