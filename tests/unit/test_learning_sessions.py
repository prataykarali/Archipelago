"""Regression coverage for private, server-authoritative diagnostic sessions."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask
import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
sys.path.insert(0, str(HOST))

from engine import adaptive_session  # noqa: E402
from engine.graph import LibraryGraph  # noqa: E402
from engine.learning_state import effective_mastery, update_mastery  # noqa: E402
from engine.privacy import inference_context, safe_text  # noqa: E402
from hostapp.quiz_store import QuizStore  # noqa: E402
from hostapp.routes.diagnostics import register  # noqa: E402

pytestmark = pytest.mark.unit


def graph_fixture(tmp_path, count=3):
    """Build cited synthetic evidence, never depending on private production data."""
    nodes = [
        {
            "id": f"n{i}", "label": f"Concept {i}", "summary": f"Definition of concept {i}.",
            "sources": [{"doc_id": "synthetic.pdf", "page_number": i + 1, "text_passage": f"Definition {i}"}],
        }
        for i in range(count + 1)
    ]
    edges = [
        {"from_id": "n0" if i > 3 else f"n{i-1}", "to_id": f"n{i}", "edge_type": "REQUIRES"}
        for i in range(1, count + 1)
    ]
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"nodes": nodes, "edges": edges}))
    return LibraryGraph(path)


def submit(graph, state, confidence="high", correct=True):
    question = state["question"]
    choice = question["correct_option"]
    if not correct:
        choice = next(key for key in question["options"] if key != choice)
    return adaptive_session.advance(graph, state, {
        "question_id": question["question_id"], "user_choice": choice, "confidence": confidence,
        "history": [{"concept_id": "forged", "is_correct": True}],
        "current_mcq": {"correct_option": "forged"},
    })


def test_question_key_and_explanation_stay_on_server(tmp_path):
    graph = graph_fixture(tmp_path)
    state, payload = adaptive_session.start(graph, "n0")
    assert state["question"]["correct_option"] in "ABCD"
    encoded = json.dumps(payload)
    assert "correct_option" not in encoded
    assert "option_nodes" not in encoded
    assert "explanation" not in encoded


def test_three_questions_stop_when_neighborhood_is_covered(tmp_path):
    graph = graph_fixture(tmp_path)
    state, _ = adaptive_session.start(graph, "n0")
    results = [submit(graph, state) for _ in range(3)]
    assert [result["completed"] for result in results] == [False, False, True]
    assert results[-1]["evaluation"]["passed"]
    assert len(state["history"]) == 3
    assert all(row["concept_id"] != "forged" for row in state["history"])


def test_budget_is_hard_ceiling_and_unassessed_nodes_stay_missing(tmp_path):
    graph = graph_fixture(tmp_path, count=14)
    state, _ = adaptive_session.start(graph, "n0")
    for _ in range(10):
        result = submit(graph, state, correct=False)
    assert result["completed"] and result["completion_reason"] == "question_budget"
    assert result["total_asked"] == 10
    assert any(node["status"] == "missing" for node in result["personalized_graph"]["nodes"])
    assert not result["evaluation"]["passed"]


def test_hop_coverage_and_edges_are_real(tmp_path):
    graph = graph_fixture(tmp_path, count=9)
    state, _ = adaptive_session.start(graph, "n0")
    asked = []
    for _ in range(3):
        asked.append(state["depths"][state["question"]["concept_id"]])
        result = submit(graph, state)
    assert set(asked) == {1, 2, 3}
    assert result["completed"], "three confident hop checks need not exhaust the neighborhood"
    assert not result["evaluation"]["passed"], "unassessed prerequisites cannot be called mastered"
    for edge in result["personalized_graph"]["edges"]:
        assert (edge["relation"], edge["target"]) in graph.out[edge["source"]]


@pytest.mark.parametrize("correct,confidence,expected", [
    (True, "high", "mastered"), (True, "medium", "mastered"),
    (True, "low", "review_gap"), (False, "high", "review_gap"),
    (False, "low", "review_gap"),
])
def test_confidence_calibration(correct, confidence, expected):
    assert update_mastery("n1", correct, confidence)["mastery_state"] == expected


def test_fading_and_one_micro_verification():
    record = update_mastery("n1", True, "high", now=0)
    assert effective_mastery(record, now=24 * 86400) == "fading"
    refreshed = update_mastery("n1", True, "high", record, now=24 * 86400)
    assert effective_mastery(refreshed, now=24 * 86400) == "mastered"
    assert refreshed["verification_count"] == 2


def test_misconception_requires_explicit_graph_evidence(tmp_path):
    graph = graph_fixture(tmp_path)
    state, _ = adaptive_session.start(graph, "n0")
    assert submit(graph, state, correct=False)["misconception"] is None
    state, _ = adaptive_session.start(graph, "n0")
    q = state["question"]
    wrong = next(key for key in q["options"] if key != q["correct_option"])
    graph.out.setdefault(q["concept_id"], []).append(("contrasts_with", q["option_nodes"][wrong]))
    result = submit(graph, state, correct=False)
    assert result["misconception"]["possible"]
    assert result["misconception"]["relation"] == "contrasts_with"


def test_preferences_validated_and_can_change(tmp_path):
    graph = graph_fixture(tmp_path)
    state, _ = adaptive_session.start(graph, "n0", "mathematical")
    question = state["question"]
    adaptive_session.advance(graph, state, {
        "question_id": question["question_id"], "user_choice": question["correct_option"],
        "confidence": "high", "preference": "code",
    })
    assert state["preference"] == "code"
    with pytest.raises(ValueError):
        adaptive_session.start(graph, "n0", "unknown")


def test_question_replay_and_invalid_target_rejected(tmp_path):
    graph = graph_fixture(tmp_path)
    state, payload = adaptive_session.start(graph, "n0")
    old_id = payload["initial_question"]["question_id"]
    submit(graph, state)
    with pytest.raises(ValueError):
        adaptive_session.advance(graph, state, {"question_id": old_id, "user_choice": "A"})
    with pytest.raises(ValueError):
        adaptive_session.start(graph, "not-indexed")


def test_no_empty_graph_crash(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text('{"nodes": [], "edges": []}')
    graph = LibraryGraph(path)
    with pytest.raises(ValueError):
        adaptive_session.start(graph, "n0")


def test_store_owner_isolation_expiry_and_concurrent_replay(tmp_path):
    graph = graph_fixture(tmp_path)
    state, _ = adaptive_session.start(graph, "n0")
    store = QuizStore(tmp_path / "sessions.db")
    sid = store.create("owner-a", state)
    with pytest.raises(LookupError):
        store.advance(sid, "owner-b", lambda state: {})
    question = state["question"]
    body = {"question_id": question["question_id"], "user_choice": question["correct_option"]}

    def run():
        try:
            store.advance(sid, "owner-a", lambda current: adaptive_session.advance(graph, current, body))
            return "ok"
        except ValueError:
            return "replay"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: run(), range(2))) == ["ok", "replay"]
    with store._connect() as connection:
        connection.execute("UPDATE quiz_session SET expires = 0")
    with pytest.raises(LookupError):
        store.advance(sid, "owner-a", lambda state: {})


def test_http_sessions_are_private_and_answer_forgery_fails(tmp_path, monkeypatch):
    graph = graph_fixture(tmp_path)
    monkeypatch.setenv("ARCHIPELAGO_QUIZ_DB", str(tmp_path / "sessions.db"))
    app = Flask(__name__)
    register(app, SimpleNamespace(engine=SimpleNamespace(graph=graph)))
    first, second = app.test_client(), app.test_client()
    response = first.get("/api/chat/diagnostic-mcqs?concept=n0")
    data = response.get_json()
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, private"
    assert "HttpOnly" in response.headers["Set-Cookie"]
    body = {"session_id": data["session_id"], "question_id": data["initial_question"]["question_id"], "user_choice": "A"}
    assert second.post("/api/chat/adaptive-step", json=body).status_code == 403
    second.get("/api/chat/diagnostic-mcqs?concept=n0")
    assert second.post("/api/chat/adaptive-step", json=body).status_code == 404
    body["question_id"] = "forged"
    assert first.post("/api/chat/adaptive-step", json=body).status_code == 409
    assert first.post("/api/chat/adaptive-step", json=[]).status_code == 400


def test_outbound_context_allowlist_and_redaction(tmp_path):
    graph = graph_fixture(tmp_path)
    graph.nodes["n1"]["summary"] = "secret=abcdef\nEmail student@example.com\nGood definition."
    graph.nodes["n2"]["private"] = True
    payload = {
        "anchor_concept": {"id": "n1"}, "prerequisites": [{"id": "n2"}],
        "student_history": "never send this", "inventory": {"barcode": "private inventory"},
    }
    context = inference_context(graph, payload)
    assert "abcdef" not in context and "student@example.com" not in context
    assert "Concept 2" not in context
    assert "never send" not in context and "private inventory" not in context
    assert "Good definition" in context
    assert len(safe_text("a" * 9000)) == 6000


def test_graph_query_state_is_request_local(tmp_path):
    graph = graph_fixture(tmp_path)
    graph._query = "main"
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(lambda: graph._query).result() == ""
    assert graph._query == "main"


def test_local_bridge_uses_same_private_protocol(tmp_path, monkeypatch):
    from archipelago.personalization_bridge import diagnostic_response

    graph = graph_fixture(tmp_path)
    for i in range(3):
        graph.nodes[f"n{i}"]["prerequisites"] = [{"id": f"n{i+1}"}]
    monkeypatch.setenv("ARCHIPELAGO_QUIZ_DB", str(tmp_path / "bridge.db"))
    app = Flask(__name__)
    app.add_url_rule("/start", endpoint="start", view_func=lambda: diagnostic_response(graph.nodes, start=True))
    app.add_url_rule("/step", endpoint="step", view_func=lambda: diagnostic_response(graph.nodes, start=False), methods=["POST"])
    client = app.test_client()
    response = client.get("/start?concept=n0")
    payload = response.get_json()
    assert response.status_code == 200
    assert "correct_option" not in payload["initial_question"]
    assert client.post("/step", json={
        "session_id": payload["session_id"],
        "question_id": payload["initial_question"]["question_id"],
        "user_choice": "A", "confidence": "low",
    }).status_code == 200


def test_preference_affects_node_choice_without_inventing_edges(tmp_path):
    from engine.learning_state import next_node

    graph = graph_fixture(tmp_path)
    graph.nodes["n1"]["concept_type"] = "method"
    graph.nodes["n2"]["concept_type"] = "metric"
    state = {"depths": {"n1": 1, "n2": 1}, "history": [], "mastery": {}, "preference": "code"}
    assert next_node(graph, state) == "n1"
    state["preference"] = "mathematical"
    assert next_node(graph, state) == "n2"
