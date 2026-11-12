from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from library_inventory import inventory_stats, parse_inventory_csv  # noqa: E402


def test_hosted_package_imports_without_repository_package():
    """Vercel uploads only host_inference, including its copied S5 runtime."""
    result = subprocess.run(
        [sys.executable, "-c", "from hostapp.factory import create_app; print('ready')"],
        cwd=HOST,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ready"


def test_hosted_research_permissions_match_pipeline_roles():
    from hostapp.research_access import ResearchCapability, allowed

    from archipelago.scholarly.access import ResearchCapability as PipelineCapability
    from archipelago.scholarly.access import allowed as pipeline_allowed

    for role in (None, "student", "faculty", "librarian", "administrator"):
        for capability in ResearchCapability:
            assert allowed(role, capability) == pipeline_allowed(
                role, PipelineCapability(capability.value)
            )


def test_hosted_research_path_permissions_cover_privileged_actions(hosted_app, monkeypatch):
    from hostapp.research_access import ResearchCapability

    context = hosted_app.app.extensions["archipelago"]
    role = {"value": "student"}
    monkeypatch.setattr(
        context.auth,
        "principal",
        lambda: ({"id": "role-test", "role": role["value"]}, None),
    )
    cases = (
        ("post", "/api/research/jobs", ResearchCapability.JOB_CREATE),
        ("get", "/api/research/jobs/one/sources", ResearchCapability.SOURCE_HEALTH),
        ("get", "/api/research/jobs/one/papers/two/features", ResearchCapability.FEATURE_READ),
        ("get", "/api/research/jobs/one/papers/two/evidence", ResearchCapability.EVIDENCE_READ),
        (
            "post",
            "/api/research/jobs/one/papers/two/evidence/hash/review",
            ResearchCapability.REVIEW,
        ),
        ("post", "/api/research/topics", ResearchCapability.TOPIC_TRACK),
        ("patch", "/api/research/topics/one/refresh", ResearchCapability.REFRESH_CONTROL),
        ("patch", "/api/research/connectors/one", ResearchCapability.CONNECTOR_CONFIG),
    )
    client = hosted_app.app.test_client()
    for method, path, _capability in cases:
        assert getattr(client, method)(path).status_code == 403
    role["value"] = "faculty"
    assert client.patch("/api/research/topics/one/refresh").status_code == 403
    assert client.post("/api/research/jobs/one/papers/two/evidence/hash/review").status_code == 403
    role["value"] = "librarian"
    assert client.patch("/api/research/connectors/one").status_code == 403
    role["value"] = "administrator"
    assert client.patch("/api/research/connectors/one").status_code == 405


def test_inventory_csv_validates_counts_and_computes_stats():
    rows = parse_inventory_csv(
        b"book_id,title,total_copies,available_copies,location\n"
        b"bk-1,Graph Systems,5,3,Central Library\n"
        b"bk-2,Data Mining,2,2,Block B\n"
    )

    assert rows[0]["available_ratio"] == "3 / 5"
    assert rows[0]["location"] == "Central Library"
    assert inventory_stats(rows) == {
        "total_records": 2,
        "total_copies": 7,
        "available_copies": 5,
    }


@pytest.mark.parametrize(
    "payload",
    [
        b"title,total_copies,available_copies\nBook,1,1\n",
        b"book_id,title,total_copies,available_copies\nbk,Book,2,3\n",
        b"book_id,title,total_copies,available_copies\nbk,Book,nope,0\n",
        b"book_id,title,total_copies,available_copies\nbk,Book,1,1\nbk,Duplicate,1,1\n",
    ],
)
def test_inventory_csv_rejects_invalid_rows(payload):
    with pytest.raises(ValueError):
        parse_inventory_csv(payload)


@pytest.fixture
def hosted_app(monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    import engine as hosted_engine

    class Graph:
        nodes = {  # noqa: RUF012
            "graph_retrieval": {"summary": "Retrieval over a graph."},
            "embeddings": {"summary": "Vector representations."},
            "indexing": {"summary": "Organizing searchable data."},
        }
        out = {"graph_retrieval": [("REQUIRES", "indexing")]}  # noqa: RUF012
        inn = {"graph_retrieval": [("UNLOCKS", "embeddings")]}  # noqa: RUF012

        def rank(self, query, top_k=1):
            return [(0.9, "graph_retrieval")]

        def label(self, node_id):
            return node_id.replace("_", " ").title()

    fake_engine = SimpleNamespace(graph=Graph(), books=[], cache_info={"source": "test"})
    monkeypatch.setattr(hosted_engine, "Engine", lambda: fake_engine)
    sys.modules.pop("server", None)
    server = importlib.import_module("server")
    yield server
    sys.modules.pop("server", None)


def test_graph_page_and_bounded_graph_api_work(hosted_app):
    client = hosted_app.app.test_client()

    page = client.get("/graph")
    response = client.get("/api/graph/subgraph?q=graph+retrieval&max_nodes=10")

    assert page.status_code == 302
    assert page.headers["Location"] == "https://archipelago-librarian.vercel.app/academic/graph"
    assert "https://archipelago-librarian.vercel.app" in page.headers["Content-Security-Policy"]
    assert client.get("/academic_koha.js").status_code == 200
    assert response.status_code == 200
    data = response.get_json()
    assert data["target_id"] == "graph_retrieval"
    assert len(data["nodes"]) == 3
    assert all("data" in edge for edge in data["edges"])


def test_research_page_replaces_redirect_and_keeps_staff_graph_private(hosted_app, monkeypatch):
    context = hosted_app.app.extensions["archipelago"]
    client = hosted_app.app.test_client()
    role = {"value": "student"}
    monkeypatch.setattr(
        context.auth,
        "principal",
        lambda: ({"id": "staff-test", "role": role["value"]}, None),
    )

    page = client.get("/research")
    assert page.status_code == 200
    assert b"Research intelligence" in page.data
    assert client.get("/research.html").status_code == 404
    assert client.get("/api/research/graph/subgraph?q=graph").status_code == 403
    role["value"] = "faculty"
    page = client.get("/research/progress")
    assert page.status_code == 302
    assert page.headers["Location"] == (
        "https://archipelago-librarian.vercel.app/research/progress"
    )
    assert client.get("/api/research/graph/subgraph?q=graph").status_code == 200


def test_student_metadata_access_does_not_open_staff_research(hosted_app, monkeypatch, tmp_path):
    context = hosted_app.app.extensions["archipelago"]
    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_DB", str(tmp_path / "research.sqlite3"))
    monkeypatch.setattr(
        context.auth,
        "principal",
        lambda: ({"id": "student-one", "role": "student"}, None),
    )
    client = hosted_app.app.test_client()
    assert client.get("/api/research/intelligence/runs").status_code == 200
    assert (
        client.post("/api/research/intelligence/monitors", json={"topic": "graphs"}).status_code
        == 403
    )
    assert client.get("/api/research/intake/records").status_code == 403
    monkeypatch.setattr(context.auth, "principal", lambda: (None, "expired"))
    assert client.get("/api/research/intelligence/runs").status_code == 401


def test_s5_run_export_graph_and_monitor_are_owner_scoped(hosted_app, monkeypatch, tmp_path):
    from archipelago.scholarly.intelligence.storage import ResearchStore

    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_DB", str(tmp_path / "research.sqlite3"))
    context = hosted_app.app.extensions["archipelago"]
    owner = {"id": "user-a"}
    monkeypatch.setattr(
        context.auth,
        "principal",
        lambda: ({"id": owner["id"], "role": "faculty"}, None),
    )
    client = hosted_app.app.test_client()
    run_id = ResearchStore(tmp_path / "research.sqlite3").save_run(
        "user-a",
        {
            "schema": "archipelago.research_intelligence.v1",
            "options": {"topic": "graphs"},
            "retrieved_at": "2026-11-12T00:00:00+00:00",
            "sources": [],
            "candidate_count": 0,
            "filtered_count": 0,
            "papers": [],
        },
    )
    monitor_id = client.post(
        "/api/research/intelligence/monitors", json={"topic": "graph neural networks"}
    ).json["monitor_id"]
    assert client.get(f"/api/research/intelligence/runs/{run_id}").status_code == 200
    assert client.get(f"/api/research/intelligence/runs/{run_id}/graph").status_code == 200
    assert client.get(f"/api/research/intelligence/runs/{run_id}/xlsx").status_code == 200
    owner["id"] = "user-b"
    assert client.get(f"/api/research/intelligence/runs/{run_id}").status_code == 404
    assert client.get(f"/api/research/intelligence/runs/{run_id}/graph").status_code == 404
    assert client.get(f"/api/research/intelligence/runs/{run_id}/xlsx").status_code == 404
    assert (
        client.patch(
            f"/api/research/intelligence/monitors/{monitor_id}", json={"enabled": True}
        ).status_code
        == 404
    )


def test_library_details_stay_on_library_without_session(hosted_app, monkeypatch):
    context = hosted_app.app.extensions["archipelago"]
    monkeypatch.setattr(context.auth, "required", lambda: True)
    monkeypatch.setattr(context.auth, "principal", lambda: (None, "missing"))
    response = hosted_app.app.test_client().get("/library")
    assert response.status_code == 200
    assert b"Library" in response.data
    assert b'id="library-graph-links"' in response.data
    assert b'href="/graph"' in response.data
    assert b'href="/research"' in response.data
    assert b'id="sec-research-pipeline"' not in response.data


def test_full_research_graph_returns_every_node_for_staff(hosted_app, monkeypatch):
    context = hosted_app.app.extensions["archipelago"]
    role = {"value": "student"}
    monkeypatch.setattr(
        context.auth, "principal", lambda: ({"id": "staff-test", "role": role["value"]}, None)
    )
    client = hosted_app.app.test_client()
    assert client.get("/api/research/graph/full").status_code == 403
    role["value"] = "faculty"
    response = client.get("/api/research/graph/full")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["counts"]["concepts"] == len(context.engine.graph.nodes)
    assert {node["data"]["id"] for node in payload["nodes"]} == set(context.engine.graph.nodes)


def test_research_intake_roles_and_persistence(hosted_app, monkeypatch):
    from hostapp.routes import research_intake

    context = hosted_app.app.extensions["archipelago"]
    role = {"value": "student"}
    monkeypatch.setattr(
        context.auth, "principal", lambda: ({"id": "staff-test", "role": role["value"]}, None)
    )
    monkeypatch.setattr(context.limiter, "check_api", lambda: (False, 0))
    monkeypatch.setattr(
        research_intake,
        "discover_papers",
        lambda topic, user_id: (
            [
                {
                    "kind": "paper",
                    "title": "Example",
                    "record_key": "a" * 64,
                    "source_name": "OpenAlex",
                    "source_url": "https://openalex.org/W1",
                    "metadata": {"source_timestamp": "2026-10-21T00:00:00Z"},
                }
            ],
            {"OpenAlex": "ok"},
        ),
    )
    monkeypatch.setattr(research_intake, "save_records", lambda records: len(records))
    monkeypatch.setattr(
        research_intake,
        "get_record",
        lambda _key: {
            "kind": "paper",
            "record_key": "a" * 64,
            "title": "Example",
            "source_name": "OpenAlex",
            "source_url": "https://openalex.org/W1",
            "metadata": {"source_timestamp": "2026-10-21T00:00:00Z"},
        },
    )
    monkeypatch.setattr(
        research_intake,
        "list_records",
        lambda kind=None: [
            {
                "title": "Flood adaptation",
                "topic": "urban flood",
                "content": "Green infrastructure reduces urban flood exposure.",
                "source_url": "https://example.org/paper",
                "source_name": "OpenAlex",
            }
        ],
    )
    monkeypatch.setattr(
        research_intake, "search_records", lambda _query, kind=None: research_intake.list_records()
    )
    client = hosted_app.app.test_client()
    assert client.get("/api/research/intake/records").status_code == 403
    role["value"] = "faculty"
    assert client.get("/api/research/intake/records").get_json()["count"] == 1
    assert (
        client.get("/api/research/intake/paper-okf/" + "a" * 64).get_json()["okf_version"]
        == "2.1.0"
    )
    headers = {"Authorization": "Bearer test"}
    assert (
        client.post(
            "/api/research/intake/papers", json={"topic": "ecology"}, headers=headers
        ).get_json()["saved"]
        == 1
    )
    reply = client.post(
        "/api/research/intake/reply", json={"query": "urban flood"}, headers=headers
    )
    assert reply.status_code == 200
    assert len(reply.get_json()["sources"]) == 1
    assert (
        client.post(
            "/api/research/intake/college", json={"url": "https://uem.edu.in/"}, headers=headers
        ).status_code
        == 403
    )


def test_research_annotations_are_viewable_by_faculty_and_editable_by_staff(
    hosted_app, monkeypatch
):
    from hostapp.routes import research_graph

    context = hosted_app.app.extensions["archipelago"]
    monkeypatch.setattr(context.limiter, "check_api", lambda: (False, 0))
    role = {"value": "faculty"}
    monkeypatch.setattr(
        context.auth,
        "principal",
        lambda: ({"id": "9d775615-0362-4498-b888-0d44ed0441ad", "role": role["value"]}, None),
    )
    monkeypatch.setattr(
        research_graph, "_store_config", lambda: ("https://example.supabase.co", "test-key")
    )

    class StoreResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"concept_id": "graph_retrieval", "summary": "Curated detail", "source_url": None}
            ]

    calls = []
    monkeypatch.setattr(research_graph.requests, "get", lambda *args, **kwargs: StoreResponse())
    monkeypatch.setattr(
        research_graph.requests,
        "post",
        lambda *args, **kwargs: (calls.append(kwargs["json"]), StoreResponse())[1],
    )
    client = hosted_app.app.test_client()
    path = "/api/research/graph/annotation"
    payload = {"concept_id": "graph_retrieval", "summary": "Curated detail"}

    assert (
        client.get(path + "?concept_id=graph_retrieval").get_json()["annotation"]["summary"]
        == "Curated detail"
    )
    assert (
        client.post(path, json=payload, headers={"Authorization": "Bearer test"}).status_code == 403
    )
    role["value"] = "librarian"
    assert (
        client.post(path, json=payload, headers={"Authorization": "Bearer test"}).status_code == 200
    )
    assert calls[-1]["updated_by"] == "9d775615-0362-4498-b888-0d44ed0441ad"
    assert client.post(path, json=payload).status_code == 401
    role["value"] = "administrator"
    assert (
        client.post(path, json=payload, headers={"Authorization": "Bearer test"}).status_code == 200
    )


def test_librarian_inventory_import_persists_and_reports_actual_totals(hosted_app, monkeypatch):
    client = hosted_app.app.test_client()
    saved = {}
    # Routes read collaborators from the injected context, not module globals.
    ctx = hosted_app.app.extensions["archipelago"]
    monkeypatch.setattr(ctx.auth, "principal", lambda: ({"role": "librarian"}, None))
    monkeypatch.setattr(ctx.inventory, "save", lambda rows: saved.update(rows=rows))

    response = client.post(
        "/api/library/import",
        data={
            "file": (
                __import__("io").BytesIO(
                    b"book_id,title,total_copies,available_copies\nbk,Graph Book,4,2\n"
                ),
                "inventory.csv",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["holdings_stats"] == {
        "total_records": 1,
        "total_copies": 4,
        "available_copies": 2,
    }
    assert saved["rows"][0]["title"] == "Graph Book"
