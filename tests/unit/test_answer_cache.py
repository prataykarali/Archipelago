"""Feature regression — answer cache, request dedup and cache metrics.

Covers doc 03 (AI call minimisation): query normalisation, versioned cache keys,
hit/miss accounting, TTL expiry, retrieval/graph caches, in-flight request
coalescing, the metrics surface, and a full ``/api/chat`` cache round-trip that
proves a cache hit makes **zero** model calls.

Deterministic: no network. Supabase env vars are cleared so every test exercises
the in-memory path.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST = REPO_ROOT / "host_inference"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cache_mod():
    """Load ``host_inference/cache_service.py`` without polluting sys.path."""
    return _load("_test_cache_service", HOST / "cache_service.py")


@pytest.fixture
def isolated_env(monkeypatch):
    """Force the in-memory cache path (no Supabase REST calls)."""
    for var in (
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


# ─── Query normalisation ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("What is BERT?", "bert"),
        ("explain gradient descent", "gradient descent"),
        ("  Can you please explain to me backpropagation?  ", "backpropagation"),
        ("Tell me about LoRA.", "lora"),
        ("How does attention work?", "how does attention work"),
        ("", ""),
    ],
)
def test_normalize_query_semantic_equivalence(cache_mod, raw, expected):
    assert cache_mod.CacheService.normalize_query(raw) == expected


def test_normalize_query_collapses_punctuation_and_whitespace(cache_mod):
    a = cache_mod.CacheService.normalize_query("What is   BERT?!")
    b = cache_mod.CacheService.normalize_query("what is bert")
    assert a == b == "bert"


# ─── Versioned cache keys ────────────────────────────────────────────────────


def test_cache_key_is_stable_for_same_versions(cache_mod, isolated_env):
    svc = cache_mod.CacheService()
    assert svc.generate_cache_key("bert") == svc.generate_cache_key("bert")


@pytest.mark.parametrize(
    "field",
    ["model_version", "graph_version", "prompt_version", "library_version"],
)
def test_cache_key_changes_when_any_version_changes(cache_mod, isolated_env, field):
    base = cache_mod.CacheService()
    bumped = cache_mod.CacheService(**{field: "different-version"})
    assert base.generate_cache_key("bert") != bumped.generate_cache_key("bert")


def test_cache_key_uses_query_content(cache_mod, isolated_env):
    svc = cache_mod.CacheService()
    assert svc.generate_cache_key("bert") != svc.generate_cache_key("gpt")


# ─── Response cache hit / miss / TTL ─────────────────────────────────────────


def test_miss_then_hit_round_trip(cache_mod, isolated_env):
    svc = cache_mod.CacheService()
    assert svc.get_cached_response("what is bert") is None

    svc.cache_response("what is bert", "BERT is a transformer.", sources=[{"doc_id": "d1"}])
    hit = svc.get_cached_response("explain bert")  # different phrasing, same normal form
    assert hit is not None
    assert hit["response"] == "BERT is a transformer."
    assert hit["sources"] == [{"doc_id": "d1"}]


def test_repeated_hits_increment_hit_count(cache_mod, isolated_env):
    svc = cache_mod.CacheService()
    svc.cache_response("lora", "LoRA is low-rank adaptation.")
    # The stored entry is mutated in place, so read the count immediately.
    first = svc.get_cached_response("lora")["hit_count"]
    second = svc.get_cached_response("lora")["hit_count"]
    assert first == 1
    assert second == 2


def test_expired_entry_is_a_miss(cache_mod, isolated_env):
    svc = cache_mod.CacheService()
    svc.cache_response("bert", "text", ttl_seconds=-1)
    assert svc.get_cached_response("bert") is None


def test_empty_query_and_empty_response_are_not_cached(cache_mod, isolated_env):
    svc = cache_mod.CacheService()
    svc.cache_response("", "text")
    svc.cache_response("bert", "")
    assert svc.get_cached_response("") is None
    assert svc.get_cached_response("bert") is None


def test_cached_payload_records_versions(cache_mod, isolated_env):
    svc = cache_mod.CacheService(model_version="m1", graph_version="g1")
    svc.cache_response("bert", "text")
    entry = svc.get_cached_response("bert")
    assert entry["model_version"] == "m1"
    assert entry["graph_version"] == "g1"
    assert entry["normalized_query"] == "bert"


# ─── Retrieval + graph caches ────────────────────────────────────────────────


def test_retrieval_cache_round_trip_and_ttl(cache_mod, isolated_env):
    svc = cache_mod.CacheService()
    assert svc.get_cached_retrieval("bert") is None
    svc.cache_retrieval("bert", {"chunks": 3})
    assert svc.get_cached_retrieval("bert")["chunks"] == 3

    svc.cache_retrieval("gpt", {"chunks": 1}, ttl_seconds=-1)
    assert svc.get_cached_retrieval("gpt") is None


def test_graph_cache_round_trip_and_ttl(cache_mod, isolated_env):
    svc = cache_mod.CacheService()
    assert svc.get_cached_graph("bert") is None
    svc.cache_graph("bert", {"edges": 2})
    entry = svc.get_cached_graph("bert")
    assert entry["edges"] == 2
    assert entry["concept_id"] == "bert"

    svc.cache_graph("gpt", {"edges": 0}, ttl_seconds=-1)
    assert svc.get_cached_graph("gpt") is None


def test_graph_cache_key_includes_graph_version(cache_mod, isolated_env):
    old = cache_mod.CacheService(graph_version="g-old")
    new = cache_mod.CacheService(graph_version="g-new")
    old.cache_graph("bert", {"edges": 5})
    # A new graph version must not read the previous version's cache.
    assert new.get_cached_graph("bert") is None


# ─── Cache metrics ───────────────────────────────────────────────────────────


def test_metrics_accounting_and_ratio(cache_mod):
    m = cache_mod.CacheMetrics()
    for _ in range(10):
        m.record_request()
    for _ in range(4):
        m.record_hit(tokens_saved=100)
    for _ in range(2):
        m.record_dedup(tokens_saved=100)

    stats = m.stats()
    assert stats["ai_requests_total"] == 10
    assert stats["ai_cache_hits"] == 4
    assert stats["ai_dedup_hits"] == 2
    assert stats["ai_requests_saved"] == 6
    assert stats["tokens_saved"] == 600
    assert stats["cache_hit_ratio"] == 0.6
    assert stats["cache_hit_percentage"] == "60.0%"


def test_metrics_ratio_is_zero_with_no_requests(cache_mod):
    stats = cache_mod.CacheMetrics().stats()
    assert stats["ai_requests_total"] == 0
    assert stats["cache_hit_ratio"] == 0.0


def test_metrics_concurrent_updates_are_lossless(cache_mod):
    m = cache_mod.CacheMetrics()
    threads = 8
    per_thread = 250

    def worker():
        for _ in range(per_thread):
            m.record_request()
            m.record_hit()

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()

    stats = m.stats()
    assert stats["ai_requests_total"] == threads * per_thread
    assert stats["ai_cache_hits"] == threads * per_thread
    assert stats["cache_hit_ratio"] == 1.0


# ─── Request deduplication ───────────────────────────────────────────────────


def test_dedup_leader_and_follower_share_one_result(cache_mod):
    dedup = cache_mod.RequestDeduplicator()
    assert dedup.start_flight("bert") is True
    assert dedup.start_flight("bert") is False
    assert dedup.is_in_flight("bert") is True

    shared = ["meta-frame", "answer text"]
    dedup.complete("bert", shared)
    assert dedup.wait("bert") == shared

    dedup.cleanup("bert")
    assert dedup.is_in_flight("bert") is False


def test_dedup_wait_returns_none_when_never_completed(cache_mod):
    dedup = cache_mod.RequestDeduplicator(wait_timeout=0.05)
    dedup.start_flight("slow")
    assert dedup.wait("slow") is None


def test_dedup_follower_thread_receives_leader_result(cache_mod):
    dedup = cache_mod.RequestDeduplicator()
    dedup.start_flight("bert")
    received = {}

    def follower():
        received["value"] = dedup.wait("bert")

    t = threading.Thread(target=follower)
    t.start()
    time.sleep(0.02)
    dedup.complete("bert", "shared-answer")
    t.join(timeout=1.0)

    assert received.get("value") == "shared-answer"


# ─── End-to-end: /api/chat cache round trip ──────────────────────────────────

CACHE_MARKER = "\n[STREAM_START]\n"


class _PermissiveLimiter:
    """Never limits — isolates cache behaviour from rate limiting."""

    def check_chat(self):
        return (False, 0)

    def check_api(self):
        return (False, 0)


class _StubEngine:
    """Emits a metadata frame + marker + text and counts model calls."""

    def __init__(self):
        self.calls = 0

    def stream_chat(self, query: str):
        self.calls += 1
        meta = {
            "target_id": "bert",
            "citations": [{"doc_id": "papers/d1.pdf", "page_number": 3}],
            "roadmap": [],
        }
        yield json.dumps(meta) + CACHE_MARKER
        yield "BERT is a transformer encoder."


@pytest.fixture
def cache_app(cache_mod, isolated_env):
    """Build the host app with an isolated cache + stub engine."""
    if str(HOST) not in sys.path:
        sys.path.insert(0, str(HOST))
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from hostapp.context import AppContext
    from hostapp.factory import create_app

    engine = _StubEngine()
    ctx = AppContext(
        engine=engine,
        auth=SimpleNamespace(required=lambda: False, principal=lambda: ({"role": "student"}, None)),
        limiter=_PermissiveLimiter(),
        inventory=SimpleNamespace(),
        cache_service=cache_mod.CacheService(),
        cache_metrics=cache_mod.CacheMetrics(),
        request_dedup=cache_mod.RequestDeduplicator(),
    )
    return SimpleNamespace(app=create_app(ctx), engine=engine, ctx=ctx)


def test_chat_miss_then_hit_makes_zero_second_model_call(cache_app):
    client = cache_app.app.test_client()

    first = client.post("/api/chat", json={"query": "explain BERT"})
    assert first.status_code == 200
    # The stream is lazy: reading the body is what runs the generator and
    # therefore what persists the cache entry.
    first_body = first.get_data(as_text=True)
    assert "BERT is a transformer encoder." in first_body
    assert cache_app.engine.calls == 1

    second = client.post("/api/chat", json={"query": "what is bert"})
    assert second.status_code == 200
    body = second.get_data(as_text=True)
    meta = json.loads(body.split(CACHE_MARKER, 1)[0].strip())

    assert cache_app.engine.calls == 1, "cache hit must not call the model"
    assert meta["target_id"] == "bert"
    assert meta["citations"][0]["doc_id"] == "papers/d1.pdf"
    assert "BERT is a transformer encoder." in body


def test_legacy_cache_entry_replays_with_cache_provider(cache_app):
    """A cache entry without an embedded metadata frame is rebuilt as JSON."""
    cache_app.ctx.cache_service.cache_response(
        "explain BERT", "Legacy cached answer.", sources=[{"doc_id": "papers/old.pdf"}]
    )
    body = cache_app.app.test_client().post(
        "/api/chat", json={"query": "explain BERT"}
    ).get_data(as_text=True)
    meta = json.loads(body.split(CACHE_MARKER, 1)[0].strip())

    assert cache_app.engine.calls == 0
    assert meta["model"] == {"provider": "cache", "model": "ai_response_cache"}
    assert meta["citations"][0]["doc_id"] == "papers/old.pdf"
    assert "Legacy cached answer." in body


def test_cache_metrics_endpoint_reports_hit_ratio(cache_app):
    client = cache_app.app.test_client()
    client.post("/api/chat", json={"query": "explain BERT"}).get_data(as_text=True)  # miss
    client.post("/api/chat", json={"query": "explain BERT"}).get_data(as_text=True)  # hit

    stats = client.get("/api/metrics/cache").get_json()
    assert stats["ai_requests_total"] == 2
    assert stats["ai_cache_hits"] == 1
    assert stats["ai_cache_misses"] == 1
    assert stats["cache_hit_ratio"] == 0.5


def test_cache_hit_preserves_stream_metadata_frame(cache_app):
    client = cache_app.app.test_client()
    client.post("/api/chat", json={"query": "explain BERT"}).get_data(as_text=True)
    hit = client.post("/api/chat", json={"query": "explain BERT"})
    text = hit.get_data(as_text=True)
    assert CACHE_MARKER in text, "cached replay must keep the metadata frame"
    assert hit.mimetype == "text/plain"


def test_diagnostic_and_explanation_do_not_share_cache(cache_app):
    client = cache_app.app.test_client()
    for query in ("explain BERT", "teach me BERT", "teach me BERT"):
        client.post("/api/chat", json={"query": query}).get_data()
    assert cache_app.engine.calls == 3


def test_personal_state_and_login_bypass_shared_cache(cache_app):
    client = cache_app.app.test_client()
    for _ in range(2):
        client.post("/api/chat", json={"query": "explain BERT", "session_id": "private"}).get_data()
        client.post("/api/chat", json={"query": "explain BERT"}, headers={"Authorization": "Bearer test"}).get_data()
    assert cache_app.engine.calls == 4
    assert not cache_app.ctx.cache_service._mem_response
