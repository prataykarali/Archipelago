"""Research intake is usable as a persisted graph and chat evidence."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask, request
import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.research_chat import enrich_with_research  # noqa: E402
from hostapp.research_projection import project_research_graph  # noqa: E402


def test_every_research_area_is_a_separate_page() -> None:
    from hostapp.research_pages import PAGE_DETAILS, render_research_page

    assert set(PAGE_DETAILS) == {"papers", "progress", "topics", "topic", "paper"}
    for page in PAGE_DETAILS:
        html = render_research_page(page).get_data(as_text=True)
        assert html.count('class="research-page-heading"') == 1
        assert 'class="section-nav"' not in html


def test_saved_source_projects_to_topic_provider_and_institutional_concept() -> None:
    row = {
        "record_key": "doi-1",
        "kind": "paper",
        "title": "Graph Retrieval in Libraries",
        "source_name": "OpenAlex",
        "source_url": "https://doi.org/example",
        "topic": "graph retrieval",
        "content": "A source abstract.",
    }
    graph = project_research_graph([row], {"graph_retrieval": {"label": "Graph Retrieval"}})
    ids = {node["data"]["id"] for node in graph["nodes"]}
    relations = {edge["data"]["rel_label"] for edge in graph["edges"]}
    assert {"record:doi-1", "provider:openalex", "concept:graph_retrieval"} <= ids
    assert {"IN_TOPIC", "FROM_SOURCE", "MENTIONS"} <= relations
    assert graph["counts"]["sources"] == 1
    assert graph["schema"] == "archipelago.research_graph.v1"


def test_research_graph_links_only_saved_citations() -> None:
    rows = [
        {
            "record_key": "a",
            "kind": "paper",
            "title": "A",
            "topic": "vision",
            "metadata": {
                "openalex_id": "https://openalex.org/W1",
                "referenced_works": ["https://openalex.org/W2", "https://openalex.org/W999"],
            },
        },
        {
            "record_key": "b",
            "kind": "paper",
            "title": "B",
            "topic": "vision",
            "metadata": {"openalex_id": "https://openalex.org/W2"},
        },
    ]
    graph = project_research_graph(rows, {})
    citations = [edge["data"] for edge in graph["edges"] if edge["data"]["rel_label"] == "CITES"]
    assert citations == [
        {
            "id": "citation:record:a:record:b",
            "source": "record:a",
            "target": "record:b",
            "rel_label": "CITES",
        }
    ]


def test_paper_graph_route_excludes_institutional_and_academic_nodes(monkeypatch) -> None:
    from hostapp.routes import research_projection

    monkeypatch.setattr(
        research_projection,
        "list_graph_records",
        lambda: (
            [
                {
                    "record_key": "paper-1",
                    "kind": "paper",
                    "title": "Paper",
                    "topic": "biology",
                    "metadata": {"ingestion_pipeline": "local_indra_v3"},
                },
                {"record_key": "old-1", "kind": "paper", "title": "Legacy", "topic": "biology"},
                {"record_key": "campus-1", "kind": "institutional_page", "title": "Campus"},
            ],
            False,
        ),
    )
    app = Flask(__name__)
    research_projection.register(app, SimpleNamespace())
    response = app.test_client().get("/api/research/graph/papers")
    ids = {node["data"]["id"] for node in response.json["nodes"]}
    assert response.status_code == 200
    assert "record:paper-1" in ids
    assert "record:campus-1" not in ids
    assert "record:old-1" not in ids
    assert all(not node_id.startswith("concept:") for node_id in ids)


def test_discovery_previews_without_persisting(monkeypatch) -> None:
    from hostapp.routes import research_intake

    app = Flask(__name__)

    @app.before_request
    def attach_principal() -> None:
        request.archipelago_principal = {"id": "faculty-one", "role": "faculty"}  # type: ignore[attr-defined]

    monkeypatch.setattr(
        research_intake,
        "discover_papers",
        lambda topic, _user: (
            [
                {
                    "title": "Relevant Paper",
                    "source_url": "https://doi.org/example",
                    "source_name": "OpenAlex",
                    "content": topic,
                }
            ],
            {"OpenAlex": "ok"},
        ),
    )
    monkeypatch.setattr(
        research_intake, "save_records", lambda _records: pytest.fail("Preview persisted records")
    )
    research_intake.register(app, SimpleNamespace())
    response = app.test_client().post("/api/research/discover", json={"topic": "biology"})
    assert response.status_code == 200
    assert response.json["papers"][0]["title"] == "Relevant Paper"


def test_chat_keeps_institutional_answer_and_adds_matching_saved_source(monkeypatch) -> None:
    from hostapp import research_chat

    monkeypatch.setattr(
        research_chat,
        "search_records",
        lambda query, kind=None: [
            {
                "record_key": "doi-1",
                "kind": "paper",
                "title": "Graph Retrieval in Libraries",
                "source_name": "OpenAlex",
                "source_url": "https://doi.org/example",
                "topic": "graph retrieval",
                "content": "Graph retrieval helps combine indexed sources.",
            }
        ],
    )
    prepared = {
        "route": "GRAPH_SYNTHESIS",
        "text": "Institutional graph answer.",
        "payload": {"route": "GRAPH_SYNTHESIS"},
    }
    result = enrich_with_research(prepared, "How does graph retrieval work?")
    assert result["text"].startswith("Institutional graph answer.")
    assert "https://doi.org/example" in result["text"]
    assert result["research_overlay"] is True
    assert result["payload"]["research_graph"]["edges"]
    assert prepared["text"] == "Institutional graph answer."


def test_paper_request_adds_research_link_even_when_catalogue_route_wins(monkeypatch) -> None:
    from hostapp import research_chat

    monkeypatch.setattr(
        research_chat,
        "search_records",
        lambda query, kind=None: [
            {
                "record_key": "lora-paper",
                "kind": "paper",
                "title": "LoRA: Low-Rank Adaptation of Large Language Models",
                "source_name": "arxiv",
                "source_url": "https://arxiv.org/abs/2106.09685",
                "topic": "LoRA research",
                "content": "LoRA research freezes pretrained weights.",
            }
        ],
    )
    prepared = {"route": "BOOK_PAGE", "text": "Academic book citation.", "payload": {}}
    result = enrich_with_research(prepared, "Give me LoRA research paper links")
    assert result["text"].startswith("Academic book citation.")
    assert "https://arxiv.org/abs/2106.09685" in result["text"]
    assert result["research_overlay"] is True


def test_chat_inventory_links_papers_from_distinct_recent_topics(monkeypatch) -> None:
    from hostapp import research_chat

    monkeypatch.setattr(
        research_chat,
        "list_topic_inventory",
        lambda: [
            {"topic": "climate adaptation", "paper_count": 2},
            {"topic": "quantum error correction", "paper_count": 1},
        ],
    )
    monkeypatch.setattr(
        research_chat,
        "recent_papers",
        lambda limit: [
            {
                "topic": "climate adaptation",
                "title": "Crop A",
                "source_url": "https://example.org/a",
            },
            {
                "topic": "climate adaptation",
                "title": "Crop B",
                "source_url": "https://example.org/b",
            },
            {
                "topic": "quantum error correction",
                "title": "Code C",
                "source_url": "https://example.org/c",
            },
        ],
    )
    result = enrich_with_research(
        {"route": "GUARDRAIL_INTERCEPT", "text": "No answer", "payload": {}},
        "List all ingested research topics",
    )
    assert "https://example.org/a" in result["text"]
    assert "https://example.org/c" in result["text"]
    assert "https://example.org/b" not in result["text"]


def test_out_of_institutional_corpus_uses_saved_sources_only_when_relevant(monkeypatch) -> None:
    from hostapp import research_chat

    monkeypatch.setattr(
        research_chat,
        "search_records",
        lambda query, kind=None: [
            {
                "record_key": "doi-2",
                "kind": "paper",
                "title": "Distributed Database Transactions",
                "source_url": "https://doi.org/database",
                "topic": "distributed database transactions",
                "content": "Transactions require distributed coordination.",
            }
        ],
    )
    prepared = {
        "route": "GUARDRAIL_INTERCEPT",
        "text": "Outside scope.",
        "payload": {"routing": {"reason": "cosine_below_0.75"}},
    }
    result = enrich_with_research(prepared, "Explain distributed database transactions")
    assert result["route"] == "RESEARCH_EVIDENCE"
    assert "Outside scope." not in result["text"]
    assert "https://doi.org/database" in result["text"]
    refusal = {**prepared, "payload": {"routing": {"reason": "safety_refusal"}}}
    assert enrich_with_research(refusal, "Explain distributed database transactions") == refusal
