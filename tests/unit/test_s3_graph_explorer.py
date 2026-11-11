"""Read-only global graph reconciliation against the actual persisted baseline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archipelago.graph.explorer import graph_neighborhood, graph_page, graph_snapshot

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def persisted_graph() -> dict:
    database = ROOT / "okf_graph.db"
    if not database.exists():
        pytest.skip("local persisted graph is unavailable")
    return graph_snapshot(database)


def test_global_pages_reach_every_persisted_node(persisted_graph: dict) -> None:
    seen = []
    offset = 0
    while True:
        page = graph_page(persisted_graph, offset=offset)
        seen.extend(item["id"] for item in page["items"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert len(seen) == persisted_graph["counts"]["nodes"]
    assert len(seen) == len(set(seen))
    assert set(seen) == {node["id"] for node in persisted_graph["nodes"]}


def test_every_visible_edge_has_valid_endpoints(persisted_graph: dict) -> None:
    ids = {node["id"] for node in persisted_graph["nodes"]}
    assert all(edge["source"] in ids and edge["target"] in ids for edge in persisted_graph["edges"])
    page = graph_page(persisted_graph, limit=100)
    visible = {node["id"] for node in page["items"]}
    assert all(
        edge["source"] in visible and edge["target"] in visible for edge in page["visible_edges"]
    )


def test_filters_preserve_snapshot_and_typed_relations(persisted_graph: dict) -> None:
    before = (len(persisted_graph["nodes"]), len(persisted_graph["edges"]))
    concept_page = graph_page(persisted_graph, node_type="Concept")
    related_page = graph_page(persisted_graph, kind="edges", relation="RELATED")
    assert concept_page["total"] == persisted_graph["counts"]["node_types"]["Concept"]
    assert related_page["total"] == persisted_graph["counts"]["relation_types"]["RELATED"]
    assert (len(persisted_graph["nodes"]), len(persisted_graph["edges"])) == before


def test_every_legacy_relation_survives_json_round_trip(persisted_graph: dict) -> None:
    restored = json.loads(json.dumps(persisted_graph))
    before = {
        (edge["id"], edge["source"], edge["target"], edge["relation"])
        for edge in persisted_graph["edges"]
    }
    after = {
        (edge["id"], edge["source"], edge["target"], edge["relation"]) for edge in restored["edges"]
    }
    assert before == after
    assert restored["counts"]["relation_types"] == persisted_graph["counts"]["relation_types"]


def test_exported_concepts_and_relations_match_storage(persisted_graph: dict) -> None:
    exported = json.loads((ROOT / "okf_graph.json").read_text(encoding="utf-8"))
    concepts = {node["id"] for node in persisted_graph["nodes"] if node["kind"] == "Concept"}
    assert concepts == set(exported["concepts"])
    exported_edges = {(e["from_id"], e["to_id"], e["edge_type"]) for e in exported["edges"]}
    persisted_edges = {
        (e["source"], e["target"], e["relation"])
        for e in persisted_graph["edges"]
        if e["relation"] in {"REQUIRES", "UNLOCKS", "RELATED"}
    }
    assert exported_edges == persisted_edges


def test_neighborhood_stays_bounded_with_source_types(persisted_graph: dict) -> None:
    node_id = next(node["id"] for node in persisted_graph["nodes"] if node["kind"] == "Concept")
    result = graph_neighborhood(persisted_graph, node_id)
    ids = {node["id"] for node in result["nodes"]}
    assert node_id in ids
    assert all(edge["source"] in ids and edge["target"] in ids for edge in result["edges"])
    assert all(
        edge["relation"] in persisted_graph["counts"]["relation_types"] for edge in result["edges"]
    )


def test_search_by_indexed_author_and_title(persisted_graph: dict) -> None:
    record = next(
        node
        for node in persisted_graph["nodes"]
        if node["kind"] == "Resource" and node.get("author") and node.get("name")
    )
    by_title = graph_page(persisted_graph, search=record["name"])
    by_author = graph_page(persisted_graph, search=record["author"])
    assert any(node["id"] == record["id"] for node in by_title["items"])
    assert by_author["total"] > 0


def test_staff_graph_api_pages_and_neighborhood(monkeypatch: pytest.MonkeyPatch) -> None:
    import graph_server

    monkeypatch.setattr(graph_server.supabase_auth, "is_auth_required", lambda: False)
    client = graph_server.app.test_client()
    first = client.get("/api/graph/global?limit=20").get_json()
    second = client.get("/api/graph/global?limit=20&offset=20").get_json()
    assert first["next_offset"] == 20
    assert not ({item["id"] for item in first["items"]} & {item["id"] for item in second["items"]})
    concept = client.get("/api/graph/global?node_type=Concept&limit=1").get_json()["items"][0]
    focused = client.get(f"/api/graph/neighborhood?id={concept['id']}&hops=2").get_json()
    assert focused["target_id"] == concept["id"]
    assert focused["edges"]
    assert client.get("/api/graph/global?kind=invalid").status_code == 400


def test_legacy_api_retains_source_bearing_concepts(monkeypatch: pytest.MonkeyPatch) -> None:
    import graph_server

    monkeypatch.setattr(graph_server.supabase_auth, "is_auth_required", lambda: False)
    result = graph_server.app.test_client().get("/api/graph").get_json()
    assert any(node.get("sources") for node in result["nodes"])
