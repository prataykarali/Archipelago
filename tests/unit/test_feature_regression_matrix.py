"""Consolidated feature regression gate.

W2 acceptance: *every* shipped feature has a dedicated, deterministic regression
suite, and the user-facing contracts those suites protect actually hold end to
end.  This module is the single entry point CI can run to prove that.

Two halves:

1. **Coverage gate** — a registry mapping each feature to the suite that owns it.
   Fails if a suite disappears, so a feature can never silently lose its guard.
2. **Contract gate** — boots the hosted app around deterministic fakes and
   exercises each surface: graph subgraph, chat stream + citations, roadmap/quiz,
   cache metrics, auth boundary, rate-limit 429 and request validation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST = REPO_ROOT / "host_inference"
UNIT = Path(__file__).resolve().parent

for _path in (str(HOST), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from host_roadmap import build_quiz, build_roadmap  # noqa: E402

pytestmark = pytest.mark.unit

CACHE_MARKER = "\n[STREAM_START]\n"

# feature name -> regression suites that must exist
FEATURE_SUITES: dict[str, tuple[str, ...]] = {
    "graph retrieval + subgraph": (
        "test_bounded_subgraph.py",
        "test_graph_edge_cases.py",
        "test_retrieval_engine.py",
    ),
    "supabase login + session": (
        "test_supabase_auth.py",
        "test_auth.py",
        "test_auth_boundary.py",
    ),
    "answer cache + dedup + metrics": ("test_answer_cache.py",),
    "rate limiting": ("test_rate_limit.py", "test_rate_limit_tiers.py"),
    "citations + page links": (
        "test_citations.py",
        "test_production_citation_hygiene.py",
        "test_source_links.py",
    ),
    "roadmap + quiz": ("test_host_roadmap.py",),
    "chat stream contract": ("test_stream_contract.py",),
    "library routing + render": ("test_library_routing_render.py",),
    "ingestion": (
        "test_ingestion_edge_cases.py",
        "test_pdf_chunking.py",
        "test_librarian_pipeline.py",
    ),
    "institutional catalog": ("test_catalog_search.py",),
    "security / log redaction": ("test_log_redaction.py",),
}


@pytest.mark.parametrize("feature, suites", sorted(FEATURE_SUITES.items()))
def test_every_feature_has_a_regression_suite(feature, suites):
    missing = [name for name in suites if not (UNIT / name).is_file()]
    assert not missing, f"{feature} lost its regression suite(s): {missing}"


@pytest.mark.parametrize("suite", sorted({s for v in FEATURE_SUITES.values() for s in v}))
def test_regression_suites_actually_contain_tests(suite):
    text = (UNIT / suite).read_text(encoding="utf-8")
    assert "def test_" in text, f"{suite} declares no tests"


# ─── Deterministic fakes ─────────────────────────────────────────────────────


class FakeGraph:
    nodes = {
        "graph_retrieval": {"summary": "Retrieval over a graph."},
        "embeddings": {"summary": "Vector representations."},
        "indexing": {"summary": "Organising searchable data."},
    }
    out = {"graph_retrieval": [("REQUIRES", "indexing")]}
    inn = {"graph_retrieval": [("UNLOCKS", "embeddings")]}

    def rank(self, query, top_k=1):
        return [(0.9, "graph_retrieval")]

    def label(self, node_id):
        return node_id.replace("_", " ").title()

    def phrase_hits(self, query):
        return ["graph_retrieval"] if "graph" in query.lower() else []

    def prereqs(self, cid, k=1):
        return {"graph_retrieval": ["indexing"], "indexing": [], "embeddings": []}[cid]

    def cite_record(self, cid, query="", index=1):
        return {
            "doc_id": f"papers/{cid}.pdf",
            "page_number": 7,
            "url": f"/read?doc=papers/{cid}.pdf&page=7",
        }

    def subgraph(self, node_id, max_nodes=25):
        return {
            "target_id": node_id,
            "nodes": [{"id": n, "label": self.label(n)} for n in self.nodes],
            "edges": [{"source": "graph_retrieval", "target": "indexing", "data": {}}],
        }


class FakeEngine:
    def __init__(self):
        self.graph = FakeGraph()
        self.books = []
        self.cache_info = {"source": "test"}

    def stream_chat(self, query):
        meta = {
            "target_id": "graph_retrieval",
            "citations": [{"doc_id": "papers/graph_retrieval.pdf", "page_number": 7}],
            "roadmap": [],
        }
        yield json.dumps(meta) + CACHE_MARKER
        yield "Retrieval over a graph is answered from the corpus."

    def mcq_for(self, concept_id, slot=0):
        return {
            "concept_id": concept_id,
            "options": {"A": "Correct", "B": "W1", "C": "W2", "D": "W3"},
            "correct_option": "A",
            "question": f"Which matches {concept_id}?",
            "explanation": "Matches the catalogue.",
            "citation": "[S1: graph_retrieval.pdf, #page=7]",
        }


class PermissiveLimiter:
    def check_chat(self):
        return (False, 0)

    def check_api(self):
        return (False, 0)


def _build_app(auth_required: bool, limiter=None):
    from hostapp.context import AppContext
    from hostapp.factory import create_app
    from hostapp.security import AuthGuard

    if auth_required:
        import os

        os.environ["ARCHIPELAGO_AUTH_REQUIRED"] = "1"
    else:
        import os

        os.environ["ARCHIPELAGO_AUTH_REQUIRED"] = "0"

    engine = FakeEngine()
    ctx = AppContext(
        engine=engine,
        auth=AuthGuard(),
        limiter=limiter or PermissiveLimiter(),
        inventory=SimpleNamespace(),
        cache_service=SimpleNamespace(
            normalize_query=lambda q: q.lower(),
            get_cached_response=lambda q: None,
            cache_response=lambda **kw: None,
        ),
        cache_metrics=SimpleNamespace(
            record_request=lambda: None,
            record_hit=lambda **kw: None,
            record_miss=lambda: None,
            record_dedup=lambda **kw: None,
            stats=lambda: {"ai_cache_hits": 0, "cache_hit_ratio": 0.0},
        ),
        request_dedup=SimpleNamespace(
            is_in_flight=lambda k: False,
            start_flight=lambda k: True,
            complete=lambda k, v: None,
            cleanup=lambda k: None,
        ),
    )
    return create_app(ctx), engine


@pytest.fixture
def public_app():
    app, _ = _build_app(auth_required=False)
    return app


@pytest.fixture
def guarded_app():
    app, _ = _build_app(auth_required=True)
    return app


# ─── Contract gate ───────────────────────────────────────────────────────────


def test_graph_subgraph_contract(public_app):
    data = public_app.test_client().get("/api/graph/subgraph?q=graph+retrieval").get_json()
    assert data["target_id"] == "graph_retrieval"
    node = data["nodes"][0]["data"]
    assert {"id", "name", "summary", "kind"} <= set(node)
    edge = data["edges"][0]["data"]
    assert {"id", "source", "target", "rel_label"} <= set(edge)


def test_chat_stream_contract_carries_metadata_and_citations(public_app):
    body = public_app.test_client().post("/api/chat", json={"query": "explain graph retrieval"}).get_data(as_text=True)
    assert CACHE_MARKER in body
    meta = json.loads(body.split(CACHE_MARKER, 1)[0].strip())
    assert meta["target_id"] == "graph_retrieval"
    assert meta["citations"][0]["page_number"] == 7
    assert "Retrieval over a graph" in body


@pytest.mark.parametrize("bad", [{}, {"query": ""}, {"query": "  "}])
def test_chat_rejects_empty_queries(public_app, bad):
    assert public_app.test_client().post("/api/chat", json=bad).status_code == 400


def test_chat_rejects_oversized_query(public_app):
    response = public_app.test_client().post("/api/chat", json={"query": "x" * 501})
    assert response.status_code == 400


def test_roadmap_contract(public_app):
    client = public_app.test_client()
    assert client.post("/api/roadmap", json={}).status_code == 400
    body = client.post("/api/roadmap", json={"topic": "graph retrieval"}).get_json()
    assert body["target_id"] == "graph_retrieval"
    assert body["stages"][0]["items"][0]["id"]


def test_quiz_contract(public_app):
    client = public_app.test_client()
    assert client.post("/api/quiz", json={}).status_code == 400
    body = client.post("/api/quiz", json={"topic": "graph retrieval"}).get_json()
    questions = body["quiz"]["questions"]
    assert questions[0]["options"] == ["Correct", "W1", "W2", "W3"]
    assert questions[0]["answer"] == "Correct"


def test_roadmap_and_quiz_builders_are_reachable():
    assert "error" not in build_roadmap(FakeGraph(), "graph retrieval")
    assert "error" not in build_quiz(FakeEngine(), "graph retrieval")


def test_cache_metrics_surface_is_public_and_shaped(public_app):
    stats = public_app.test_client().get("/api/metrics/cache").get_json()
    assert "cache_hit_ratio" in stats


def test_protected_api_is_unauthorised_when_auth_required(guarded_app):
    client = guarded_app.test_client()
    assert client.get("/api/metrics/cache").status_code == 401
    assert client.post("/api/library/import").status_code == 401


def test_public_api_stays_open_when_auth_required(guarded_app):
    client = guarded_app.test_client()
    assert client.get("/api/readiness").status_code == 200
    assert client.post("/api/chat", json={"query": "explain graph retrieval"}).status_code == 200


def test_chat_rate_limit_returns_429_with_retry_after():
    from hostapp.security import RateLimiter

    app, _ = _build_app(auth_required=False, limiter=RateLimiter())
    client = app.test_client()
    assert client.post("/api/chat", json={"query": "first"}).status_code == 200
    # CHAT_RATE_MIN_GAP_SEC is 1.0s, so an immediate second state-changing call
    # is throttled.
    blocked = client.post("/api/chat", json={"query": "second"})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_parallel_reads_are_never_blocked_on_timing():
    """A page firing several GETs at once must not be throttled.

    Regression: the burst min-gap used to reject the second idempotent request
    within 50 ms, so two exact book links (or a page's parallel API calls)
    returned 429 despite the documented "never blocked" guarantee.
    """
    from hostapp.security import RateLimiter

    app, _ = _build_app(auth_required=False, limiter=RateLimiter())
    client = app.test_client()
    for _ in range(5):
        assert client.get("/api/readiness").status_code == 200


def test_reader_redirect_is_not_burst_blocked():
    """Two consecutive /open reader redirects must both resolve."""
    from hostapp.security import RateLimiter

    app, engine = _build_app(auth_required=False, limiter=RateLimiter())
    client = app.test_client()
    statuses = [client.get("/open/book/abc?page=1").status_code for _ in range(3)]
    assert 429 not in statuses
