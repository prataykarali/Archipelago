"""Regression tests for W1-W6 academic correctness, OPAC fallback, scholarly snapshot, and Graphify XSS."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
import requests

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "host_inference"))
sys.path.insert(0, str(REPO / "host_research"))


class _DummyGraph:
    def __init__(self) -> None:
        self.nodes = {
            "translation": {
                "label": "Translation",
                "summary": "A systematic process converting one language's natural language into another.",
                "tags": ["nlp"],
            },
            "transformer": {
                "label": "Transformer",
                "summary": "Sequence transduction model based on self-attention.",
                "tags": ["dl"],
            },
            "kv_cache": {
                "label": "KV Cache",
                "summary": "Stores key and value tensors across autoregressive decoding steps.",
                "tags": ["llm"],
            },
            "address_translation": {
                "label": "Address Translation",
                "summary": "Mapping virtual addresses to physical memory addresses.",
                "tags": ["os"],
            },
        }
        self.out = {}
        self.inn = {}

    def label(self, cid: str) -> str:
        return str((self.nodes.get(cid) or {}).get("label") or cid)

    def citation(self, cid: str):
        return None

    def summary(self, cid: str) -> str:
        return str((self.nodes.get(cid) or {}).get("summary") or "")

    def formula(self, cid: str) -> str:
        return ""

    def rank(self, query: str, top_k: int = 5):
        q = query.lower()
        scored = []
        for cid, node in self.nodes.items():
            lbl = node["label"].lower()
            score = 0.88 if lbl in q else 0.1
            scored.append((score, cid))
        scored.sort(reverse=True)
        return scored[:top_k]

    def phrase_hits(self, query: str) -> list[str]:
        q = query.lower()
        return [cid for cid, node in self.nodes.items() if node["label"].lower() in q]

    def prereqs(self, cid: str, depth: int = 1) -> list[str]:
        return []

    def unlocks(self, cid: str, depth: int = 1) -> list[str]:
        return []

    def related(self, cid: str) -> list[str]:
        return []

    def shortest(self, a: str, b: str, limit: int = 4):
        return None


class _DummyCatalog:
    def reply(self, _query: str):
        return None


class _DummyEngine:
    def __init__(self) -> None:
        self.graph = _DummyGraph()
        self.catalog = _DummyCatalog()

    def pearson_line(self, cid: str) -> str:
        return ""


def test_w1_os_tlb_does_not_match_nlp_translation() -> None:
    from engine.route_logic import route

    eng = _DummyEngine()
    rt, text, anchor, _extra = route(
        eng,
        "Explain how a Translation Lookaside Buffer (TLB) speeds up virtual-to-physical address translation and what happens on a TLB miss.",
    )
    assert anchor != "translation"
    assert "natural language" not in text.lower()


def test_w2_dijkstra_routes_to_general_explanation_without_fabricated_cites() -> None:
    from engine.route_logic import route

    eng = _DummyEngine()
    rt, text, anchor, _extra = route(
        eng,
        "Why does Dijkstra's shortest-path algorithm fail when a graph contains negative-weight edges, and which algorithm handles them?",
    )
    assert rt == "GENERAL_EXPLANATION"
    assert anchor is None
    assert "general foundational knowledge" in text.lower()


def test_w3_tcp_congestion_does_not_leak_prompt_template() -> None:
    from engine.route_logic import route

    eng = _DummyEngine()
    rt, text, _anchor, _extra = route(
        eng,
        "Compare TCP Slow Start and Congestion Avoidance (AIMD) in terms of how cwnd grows per RTT.",
    )
    assert rt == "GENERAL_EXPLANATION"
    assert "clearly, include a concrete worked example, and label general foundational knowledge" not in text.lower()


def test_w4_kv_caching_resolves_kv_cache() -> None:
    from engine.multi_hop_concepts import resolve_concept

    eng = _DummyEngine()
    resolved = resolve_concept(eng, "KV caching")
    assert resolved.cid == "kv_cache"
    assert resolved.is_indexed is True


def test_w5_unsupported_scope_guardrail() -> None:
    from engine.route_logic import route

    eng = _DummyEngine()
    rt, _text, _anchor, _extra = route(
        eng, "Give a detailed biochemical mechanism of photosynthesis in C4 plants."
    )
    assert rt == "GUARDRAIL_INTERCEPT"


def test_w6_followup_page_table_ignores_earlier_nlp_translation() -> None:
    from engine.route_logic import route

    eng = _DummyEngine()
    rt, _text, anchor, _extra = route(
        eng,
        "And how does a multi-level page table reduce memory overhead compared to a single-level one? (Earlier user topics: Explain TLB address translation)",
    )
    assert rt != "CROSS_DOMAIN"
    assert anchor != "translation"


def test_research_chat_blocks_medical_papers_for_os_queries() -> None:
    from hostapp.research_chat import _score

    row = {
        "title": "ABR-DeepLabV3+: Adaptive Boundary-Refined Multi-Backbone DeepLabV3+ for MRI Brain Tumor Segmentation",
        "topic": "Medical imaging",
        "content": "multi level single memory page table segmentation",
    }
    assert _score(row, {"multi", "level", "memory", "page", "table"}, ["page table"], query="multi-level page table memory") == 0


def test_graphify_tooltip_uses_safe_text_rendering() -> None:
    src = (REPO / "host_inference/ui/graphify.js").read_text(encoding="utf-8")
    assert "tooltip.innerHTML" not in src
    assert "titleEl.textContent" in src


def test_host_research_opac_live_falls_back_to_snapshot_for_query(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("hr_app", REPO / "host_research/app.py")
    assert spec and spec.loader
    hr_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hr_app)

    def _boom(_q: str):
        raise requests.Timeout("upstream timeout")

    monkeypatch.setattr(hr_app, "search_books", _boom)
    monkeypatch.setattr(
        hr_app,
        "load_snapshot",
        lambda: {
            "source_updated_at": "2026-11-10T03:30:00Z",
            "stale": True,
            "holdings": [{"biblionumber": "1910", "Title": "Introduction to Algorithms", "Author": "Cormen"}],
        },
    )
    import flask

    with hr_app.app.test_request_context("/api/library/opac/live?q=algorithms"):
        flask.g.principal = {"id": "lib-1", "role": "librarian"}
        resp, code = hr_app.library_opac_live()
        assert code == 200
        data = resp.get_json()
        assert data["is_live"] is False
        assert data["source_kind"] == "dated_koha_export"
        assert len(data["results"]) == 1
        assert data["results"][0]["biblionumber"] == "1910"
