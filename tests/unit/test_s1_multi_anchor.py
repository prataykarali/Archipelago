"""S1 coverage for bounded multi-anchor reasoning in both chat engines."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from archipelago.core.intent import IntentCategory
from archipelago.core.intent import classify_query_intent as classify_main_intent
from archipelago.inference import multi_anchor, state
from archipelago.inference.routes.chat import part05_graph_path, part08_paper_lookup

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from engine.answer import Engine as HostedEngine  # noqa: E402
from engine.intent import classify_query_intent as classify_host_intent  # noqa: E402
from engine.multi_hop import extract_concept_mentions, multi_hop_reasoning  # noqa: E402

pytestmark = pytest.mark.unit


class Graph:
    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.out = {}
        self.inn = {}
        for source, relation, target in edges:
            self.out.setdefault(source, []).append((relation, target))
            self.inn.setdefault(target, []).append((relation, source))

    def label(self, cid):
        return self.nodes[cid]["label"]

    def phrase_hits(self, text):
        return [
            cid for cid, node in self.nodes.items() if node["label"].casefold() == text.casefold()
        ]

    def rank(self, _text, top_k=1):
        return []

    def cite_record(self, cid, _query, source_override=None):
        source = source_override or (self.nodes[cid].get("sources") or [{}])[0]
        return {
            "doc_id": source.get("doc_id", ""),
            "label": f"[S1: {cid}]",
            "text_passage": source.get("text_passage", ""),
        }

    def citation(self, cid):
        return f"[{cid}]"


class Engine:
    def __init__(self, graph):
        self.graph = graph

    def pearson_line(self, _cid):
        return ""


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_host_covers_every_requested_anchor(count):
    labels = ["Alpha", "Beta", "Gamma", "Delta"][:count]
    nodes = {
        label.casefold(): {
            "label": label,
            "summary": f"{label} mechanism summary",
            "sources": [{"doc_id": f"{label}.pdf", "text_passage": f"{label} mechanism summary"}],
        }
        for label in labels
    }
    edges = [
        (labels[i].casefold(), "RELATED", labels[i + 1].casefold()) for i in range(len(labels) - 1)
    ]
    graph = Graph(nodes, edges)
    answer = multi_hop_reasoning(Engine(graph), "Compare " + ", ".join(labels), labels)
    assert len(answer["resolved_concepts"]) == count
    assert all(label in answer["text"] for label in labels)
    assert len(answer["citations"]) == count
    if count > 1:
        assert any(path.is_connected for path in answer["paths"].values())
        assert "dependency path" not in answer["text"]


def test_host_partial_coverage_does_not_fabricate_edge():
    graph = Graph(
        {"alpha": {"label": "Alpha", "summary": "A", "sources": [{"doc_id": "a.pdf"}]}}, []
    )
    answer = multi_hop_reasoning(Engine(graph), "Compare Alpha and Missing", ["Alpha", "Missing"])
    assert answer["is_partial"]
    assert "Missing" in answer["text"]
    assert not answer["paths"]


def test_host_reports_opposing_paper_claims_without_choosing_winner():
    sources = [
        {"doc_id": "papers/positive.pdf", "text_passage": "The method increases accuracy."},
        {"doc_id": "papers/negative.pdf", "text_passage": "The method decreases accuracy."},
    ]
    graph = Graph(
        {"alpha": {"label": "Alpha", "summary": "Method accuracy", "sources": sources}}, []
    )
    answer = multi_hop_reasoning(Engine(graph), "Research on Alpha", ["Alpha"])
    assert "Conflicting papers" in answer["text"]
    assert "do not establish which result generalizes" in answer["text"]
    assert {item["doc_id"] for item in answer["citations"]} == {
        "papers/positive.pdf",
        "papers/negative.pdf",
    }


def test_local_multi_anchor_uses_exported_edges_and_reports_missing(tmp_path, monkeypatch):
    nodes = {
        name: {"id": name, "label": name.title(), "summary": name}
        for name in ("alpha", "beta", "gamma")
    }
    data = {
        "edges": [
            {"from_id": "alpha", "to_id": "beta", "edge_type": "RELATED"},
            {"from_id": "beta", "to_id": "gamma", "edge_type": "RELATED"},
        ]
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(state, "CONCEPTS_DATA", nodes)
    monkeypatch.setattr(state, "DATA_FILE", path)
    monkeypatch.setattr(multi_anchor, "build_concept_citation_map", lambda _first, _pre, _peers: {})
    monkeypatch.setattr(
        multi_anchor, "build_citation_payloads", lambda _first, _pre, _peers, _map: []
    )
    answer = multi_anchor.build_multi_anchor_answer(
        "How are Alpha, Beta, Gamma and Missing related?"
    )
    assert answer is not None
    assert len(answer["concepts"]) == 4
    assert answer["partial"]
    assert len(answer["paths"]) >= 1
    assert "Missing" in answer["text"]
    assert answer["citations"] == []


def test_local_four_anchor_answer_cites_each_supported_concept(tmp_path, monkeypatch):
    labels = ("alpha", "beta", "gamma", "delta")
    nodes = {
        label: {"id": label, "label": label.title(), "summary": f"{label} concept mechanism"}
        for label in labels
    }
    path = tmp_path / "graph.json"
    path.write_text('{"edges": []}', encoding="utf-8")
    monkeypatch.setattr(state, "CONCEPTS_DATA", nodes)
    monkeypatch.setattr(state, "DATA_FILE", path)
    monkeypatch.setattr(
        multi_anchor,
        "build_concept_citation_map",
        lambda node, _pre, _unlocks: {
            node["id"]: [{"doc_id": f"papers/{node['id']}.pdf", "text": node["summary"]}]
        },
    )
    monkeypatch.setattr(
        multi_anchor,
        "build_citation_payloads",
        lambda _first, _pre, _peers, citation_map: [
            {"evidence_id": evidence["evidence_id"], "doc_id": evidence["doc_id"]}
            for rows in citation_map.values()
            for evidence in rows
        ],
    )
    answer = multi_anchor.build_multi_anchor_answer("How are Alpha, Beta, Gamma and Delta related?")
    assert answer is not None
    assert len(answer["concepts"]) == 4
    assert len(answer["citations"]) == 4
    assert all(f"[S{index}]" in answer["text"] for index in range(1, 5))


def test_extraction_keeps_four_concepts():
    assert extract_concept_mentions("How are Alpha, Beta, Gamma and Delta related?") == [
        "Alpha",
        "Beta",
        "Gamma",
        "Delta",
    ]


def test_exact_concept_beats_a_broader_nodes_alias():
    nodes = {
        "transformer": {"id": "transformer", "label": "Transformer"},
        "transformer_layer": {
            "id": "transformer_layer",
            "label": "Transformer Layer",
            "aliases": ["transformer"],
        },
    }
    assert multi_anchor._resolve("transformers", nodes) == "transformer"


def test_main_followup_resolves_prior_concept(monkeypatch):
    monkeypatch.setattr(
        state,
        "CONCEPTS_DATA",
        {"bert": {"id": "bert", "label": "BERT", "aliases": ["bert"]}},
    )
    history = [{"role": "user", "content": "Explain BERT"}]
    resolved = multi_anchor.resolve_followup_query(
        "How does it relate to Self-Attention and RAG?", history
    )
    assert resolved == "How does BERT relate to Self-Attention and RAG?"


@pytest.mark.parametrize("classifier", [classify_main_intent, classify_host_intent])
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("What is backpropagation?", "CONCEPT_LEARNING"),
        ("How are transformers, RAG and knowledge graphs related?", "MULTI_CONCEPT"),
        ("Recent studies on RAG", "RESEARCH_TOPIC"),
        ("Which paper introduced RAG?", "PAPER_LOOKUP"),
        ("What books are in the library?", "LIBRARY_LOOKUP"),
        ("What are the library hours?", "ACADEMIC_INFO"),
        ("Quiz me on BERT", "PERSONALIZED_LEARNING"),
        ("Run a bibliometric analysis of RAG", "RESEARCH_INTELLIGENCE"),
        ("What is the weather?", "UNSUPPORTED"),
    ],
)
def test_intent_categories_in_both_engines(classifier, query, expected):
    concepts = extract_concept_mentions(query)
    assert classifier(query, extracted_concepts=concepts).value == expected


def test_hosted_lookup_and_research_payloads_suppress_learning_graph():
    engine = HostedEngine()
    for query, route in (
        ("Which paper introduced RAG?", "PAPER_LOOKUP"),
        ("What books are in the library?", "LIBRARY_LOOKUP"),
        ("Recent studies on RAG", "RESEARCH_TOPIC"),
    ):
        result = engine.answer(query)
        assert result["route"] == route
        assert not result["payload"]["render_graph"]
        assert result["payload"]["diagnostic_mcqs"] == []


def test_main_chat_multi_anchor_payload_suppresses_learning_graph(monkeypatch):
    monkeypatch.setattr(
        part05_graph_path, "extract_concept_mentions", lambda _query: ["Alpha", "Beta", "Gamma"]
    )
    monkeypatch.setattr(
        part05_graph_path,
        "classify_query_intent",
        lambda _query, extracted_concepts: IntentCategory.MULTI_CONCEPT,
    )
    monkeypatch.setattr(
        multi_anchor,
        "build_multi_anchor_answer",
        lambda _query: {
            "text": "Three concept answer",
            "citations": [],
            "concepts": ["Alpha", "Beta", "Gamma"],
            "paths": [],
            "partial": False,
        },
    )
    with state.app.app_context():
        response = part05_graph_path.handle_graph_path(
            "How are Alpha, Beta and Gamma related?", [], {"route": "graph_strong"}, False
        )
        payload_text, answer = response.get_data(as_text=True).split("\n[STREAM_START]\n", 1)
    payload = json.loads(payload_text)
    assert answer == "Three concept answer"
    assert payload["subgraph"] is None
    assert payload["diagnostic_mcqs"] == []
    assert len(payload["multi_hop"]["concepts"]) == 3


def test_main_paper_lookup_has_no_graph_or_quiz(monkeypatch):
    monkeypatch.setattr(state, "CONCEPTS_DATA", {"rag": {"id": "rag", "label": "RAG"}})
    monkeypatch.setattr(part08_paper_lookup, "build_concept_citation_map", lambda *_args: {})
    monkeypatch.setattr(
        part08_paper_lookup,
        "build_citation_payloads",
        lambda *_args: [
            {"doc_id": "papers/Lewis2020_RAG.pdf", "title": "RAG", "evidence_id": "S1"}
        ],
    )
    with state.app.app_context():
        response = part08_paper_lookup.handle_paper_lookup(
            "Which paper introduced RAG?", {"anchor_id": "rag"}
        )
        payload_text, answer = response.get_data(as_text=True).split("\n[STREAM_START]\n", 1)
    payload = json.loads(payload_text)
    assert payload["anchor_concept"] is None
    assert payload["subgraph"] is None
    assert payload["diagnostic_mcqs"] == []
    assert "does not establish which paper introduced" in answer


def test_main_paper_lookup_rejects_a_passing_mention(monkeypatch):
    monkeypatch.setattr(state, "CONCEPTS_DATA", {"bert": {"id": "bert", "label": "BERT"}})
    monkeypatch.setattr(part08_paper_lookup, "build_concept_citation_map", lambda *_args: {})
    monkeypatch.setattr(
        part08_paper_lookup,
        "build_citation_payloads",
        lambda *_args: [
            {"doc_id": "papers/Dettmers2023_QLoRA.pdf", "title": "QLoRA", "evidence_id": "S1"},
            {"doc_id": "papers/Devlin2018_BERT.pdf", "title": "BERT", "evidence_id": "S2"},
        ],
    )
    with state.app.app_context():
        response = part08_paper_lookup.handle_paper_lookup(
            "Who wrote BERT paper?", {"anchor_id": "bert"}
        )
        metadata, text = response.get_data(as_text=True).split("\n[STREAM_START]\n", 1)
    assert "BERT" in text
    assert "QLoRA" not in text
    assert json.loads(metadata)["citations"][0]["doc_id"] == "papers/Devlin2018_BERT.pdf"


def test_research_intelligence_delegates_without_claiming_metrics():
    hosted = HostedEngine().answer("Run a bibliometric analysis of RAG")
    assert hosted["route"] == "RESEARCH_INTELLIGENCE"
    assert not hosted["payload"]["render_graph"]
    assert hosted["payload"]["diagnostic_mcqs"] == []
    assert "has not calculated metrics" in hosted["text"]

    from archipelago.inference.bootstrap import app

    response = app.test_client().post(
        "/api/chat", json={"query": "Run a bibliometric analysis of RAG"}
    )
    metadata, text = response.get_data(as_text=True).split("\n[STREAM_START]\n", 1)
    payload = json.loads(metadata)
    assert payload["routing"]["route"] == "research_intelligence"
    assert payload["subgraph"] is None
    assert payload["diagnostic_mcqs"] == []
    assert "has not calculated metrics" in text
