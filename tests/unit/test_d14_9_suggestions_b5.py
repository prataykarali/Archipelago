"""D14.9 Step 1 / B5 regression tests: 12-domain suggestions & coverage consistency."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[2]
_HOST = _REPO / "host_inference"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_HOST) not in sys.path:
    sys.path.append(str(_HOST))

from engine.access_profile import load_d14_source_registry  # noqa: E402
from engine.graph import LibraryGraph  # noqa: E402
from engine.suggestions import (  # noqa: E402
    _KNOWLEDGE_AREA_SPECS,
    build_suggestions_payload,
    discover_domain_coverage,
    discover_knowledge_areas,
)

pytestmark = pytest.mark.unit

EXPECTED_DOMAIN_COUNT = 12
GRAPH_PATH = _HOST / "fixtures" / "okf_graph_v2_d14.json"
MANIFEST_PATH = _REPO / "docs" / "reports" / "d14" / "D14_GRAPH_V2_MANIFEST.json"


class _StubGraph:
    def __init__(
        self,
        nodes: dict[str, dict[str, Any]],
        *,
        graph_artifact_version: str = "graph_v2_d14",
        graph_sha256: str = "abc123",
    ) -> None:
        self.nodes = nodes
        self.graph_artifact_version = graph_artifact_version
        self.graph_sha256 = graph_sha256


def test_b5_all_12_domains_populated_including_architecture_and_fixed_keys() -> None:
    """B5: All 12 registered domains (incl. architecture, math_computing, automata, security) are full_text."""
    graph = LibraryGraph(GRAPH_PATH, allow_env_override=False)
    cov = discover_domain_coverage(graph)
    assert len(cov["full_text"]) == EXPECTED_DOMAIN_COUNT
    assert cov["graph_only"] == []
    assert cov["unavailable"] == []

    keys = {entry["key"] for entry in cov["full_text"]}
    expected_keys = {key for key, _label, _pat in _KNOWLEDGE_AREA_SPECS}
    assert keys == expected_keys
    assert "architecture" in keys
    for entry in cov["full_text"]:
        assert entry["doc_count"] > 0, f"{entry['key']} has 0 docs"
        assert entry["concept_count"] > 0, f"{entry['key']} has 0 concepts"


def test_b5_payload_versions_and_sha256_match_manifest() -> None:
    """B5: build_suggestions_payload exposes exact corpus_version, graph_version, and graph_sha256."""
    graph = LibraryGraph(GRAPH_PATH, allow_env_override=False)
    expected_sha = sha256(GRAPH_PATH.read_bytes()).hexdigest()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["graph_sha256"] == expected_sha

    payload = build_suggestions_payload(graph, seed=42)
    assert payload["corpus_version"] == "corpus_v3_d14"
    assert payload["graph_version"] == "graph_v2_d14"
    assert payload["graph_sha256"] == expected_sha
    assert payload["total_concepts"] == len(graph.nodes)
    reg_approved = {
        str(v.get("doc_id") or v.get("source_id") or "").strip()
        for v in load_d14_source_registry().values()
        if v.get("is_approved_oa")
    }
    assert payload["total_open_docs"] == len(reg_approved)
    assert len(payload["knowledge_areas"]) == EXPECTED_DOMAIN_COUNT
    assert 4 <= len(payload["suggested_questions"]) <= 5


def test_b5_graph_only_and_unavailable_classifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """B5: Domains without approved OA docs classify as graph_only or unavailable cleanly."""
    monkeypatch.setattr("engine.suggestions._d14_corpus_domain_docs", lambda: {
        key: ({"d14_oa/os/ostep_paging.pdf"} if key == "os" else set())
        for key, _lbl, _pat in _KNOWLEDGE_AREA_SPECS
    })
    monkeypatch.setattr("engine.suggestions.load_hf_paths", lambda: [])
    stub = _StubGraph({
        "paging": {
            "label": "Paging",
            "summary": "Virtual memory paging.",
            "sources": [{"doc_id": "d14_oa/os/ostep_paging.pdf"}],
        },
        "pipeline_hazards": {
            "label": "Pipeline Hazards",
            "summary": "CPU pipelining data hazards and control hazards.",
            "sources": [{"doc_id": "papers/cpu_pipeline.pdf"}],
        },
    })
    cov = discover_domain_coverage(stub)
    full_keys = {e["key"] for e in cov["full_text"]}
    graph_only_keys = {e["key"] for e in cov["graph_only"]}
    unavail_keys = {e["key"] for e in cov["unavailable"]}

    assert full_keys == {"os"}
    assert "architecture" in graph_only_keys
    assert "dbms" in unavail_keys
    areas = discover_knowledge_areas(stub)
    assert {a["key"] for a in areas} == full_keys | graph_only_keys


def test_b5_institutional_vs_open_access_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """B5: Institutional mode keeps commercial-only nodes while open_access_only gates them."""
    monkeypatch.setattr("engine.suggestions._d14_corpus_domain_docs", lambda: {
        key: set() for key, _lbl, _pat in _KNOWLEDGE_AREA_SPECS
    })
    monkeypatch.setattr("engine.suggestions.load_hf_paths", lambda: [])
    stub = _StubGraph({
        "pearson_only_topic": {
            "label": "Database Normalization",
            "summary": "3NF and BCNF in relational databases.",
            "sources": [{"doc_id": "pearson/dbms_book.pdf"}],
        },
    })
    monkeypatch.setattr("engine.suggestions.is_open_access_profile", lambda: True)
    oa_areas = discover_knowledge_areas(stub)
    assert oa_areas == []

    monkeypatch.setattr("engine.suggestions.is_open_access_profile", lambda: False)
    inst_areas = discover_knowledge_areas(stub)
    assert len(inst_areas) == 1
    assert inst_areas[0]["key"] == "dbms"
    assert inst_areas[0]["coverage_tier"] == "graph_only"
