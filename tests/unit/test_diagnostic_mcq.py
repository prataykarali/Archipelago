"""Unit tests for Interactive Diagnostic MCQ Layer."""

import pytest

from archipelago.inference.diagnostic_mcq import (
    DiagnosticMCQ,
    evaluate_diagnostic_mcqs,
    generate_diagnostic_mcqs,
)


def test_mcq_structure_strict_4_options():
    mcqs = generate_diagnostic_mcqs("low_rank_adaptation", num_questions=3)
    assert len(mcqs) == 3

    for mcq in mcqs:
        assert isinstance(mcq, dict)
        assert "id" in mcq
        assert "concept_id" in mcq
        assert "concept_name" in mcq
        assert "question" in mcq
        assert "options" in mcq
        assert "correct_option" in mcq
        assert "explanation" in mcq
        assert "citation" in mcq

        # Strict 4 options constraint
        options = mcq["options"]
        assert len(options) == 4, f"MCQ {mcq['id']} options count {len(options)} != 4"
        assert set(options.keys()) == {"A", "B", "C", "D"}, f"Invalid option keys {options.keys()}"
        assert mcq["correct_option"] in {"A", "B", "C", "D"}

        # Real literature citation
        assert len(mcq["citation"].strip()) > 5, f"MCQ {mcq['id']} lacks a valid citation"


def test_mcq_question_count_bounds():
    # Min bound 3
    mcqs_min = generate_diagnostic_mcqs("transformer", num_questions=1)
    assert len(mcqs_min) == 3

    # Max bound 5
    mcqs_max = generate_diagnostic_mcqs("transformer", num_questions=10)
    assert len(mcqs_max) == 5


def test_mcq_evaluation_pass_threshold():
    mcqs = generate_diagnostic_mcqs("transformer", num_questions=5)

    # 1. All correct -> 100% -> passed=True
    all_correct = {q["id"]: q["correct_option"] for q in mcqs}
    res_all = evaluate_diagnostic_mcqs(mcqs, all_correct, target_concept_id="transformer")
    assert res_all["success"] is True
    assert res_all["score"] == "5/5"
    assert res_all["score_pct"] == 100.0
    assert res_all["passed"] is True
    assert len(res_all["mastered_concepts"]) == 5
    assert len(res_all["gap_concepts"]) == 0

    # 2. 4 out of 5 correct -> 80% -> passed=True
    four_correct = dict(all_correct)
    wrong_choice = "A" if mcqs[0]["correct_option"] != "A" else "B"
    four_correct[mcqs[0]["id"]] = wrong_choice
    res_four = evaluate_diagnostic_mcqs(mcqs, four_correct, target_concept_id="transformer")
    assert res_four["score"] == "4/5"
    assert res_four["score_pct"] == 80.0
    assert res_four["passed"] is True

    # 3. 3 out of 5 correct -> 60% -> passed=False (< 80%)
    three_correct = dict(four_correct)
    wrong_choice2 = "A" if mcqs[1]["correct_option"] != "A" else "B"
    three_correct[mcqs[1]["id"]] = wrong_choice2
    res_three = evaluate_diagnostic_mcqs(mcqs, three_correct, target_concept_id="transformer")
    assert res_three["score"] == "3/5"
    assert res_three["score_pct"] == 60.0
    assert res_three["passed"] is False
    assert len(res_three["gap_concepts"]) == 2
    assert res_three["baseline_concept"] is not None


def test_verify_mcq_flask_endpoint():
    import os
    os.environ["ARCHIPELAGO_DB_READ_ONLY"] = "1"
    from archipelago.inference import state as st
    from archipelago.inference.routes_chat import init_concepts_data
    init_concepts_data()

    with st.app.test_client() as client:
        # Test valid submission
        resp = client.post(
            "/api/chat/verify-mcq",
            json={
                "target_concept": "low_rank_adaptation",
                "answers": {
                    "mcq_transformer_1": "B",
                    "mcq_attention_mechanism_2": "B",
                    "mcq_neural_network_3": "B",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "score" in data
        assert "score_pct" in data
        assert data["passed"] is True
        assert "details" in data


def test_chat_server_verify_mcq_proxy(monkeypatch):
    import chat_server
    from archipelago import supabase_auth
    principal = supabase_auth.AuthPrincipal("test-user", "student", "student", "test-token")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setattr(supabase_auth, "authenticate_request", lambda _request: (principal, None))

    class MockResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        content = b'{"success": true, "score": "3/3", "passed": true}'

    def mock_post(url, json=None, headers=None, timeout=None):
        assert "verify-mcq" in url
        assert json.get("target_concept") == "low_rank_adaptation"
        return MockResponse()

    monkeypatch.setattr(chat_server._requests, "post", mock_post)

    with chat_server.app.test_client() as client:
        resp = client.post(
            "/api/chat/verify-mcq",
            json={"target_concept": "low_rank_adaptation", "answers": {"mcq_1": "B"}},
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"success": True, "score": "3/3", "passed": True}


def test_zero_score_remediation_scenario():
    """Edge Case 1: 0/3 correct must construct foundational remediation bridge without failure."""
    mcqs = generate_diagnostic_mcqs("transformer", num_questions=3)
    # Intentionally select wrong options for all questions
    wrong_answers = {
        q["id"]: ("A" if q["correct_option"] != "A" else "C")
        for q in mcqs
    }
    result = evaluate_diagnostic_mcqs(mcqs, wrong_answers, target_concept_id="transformer")
    assert result["success"] is True
    assert result["score"] == "0/3"
    assert result["score_pct"] == 0.0
    assert result["passed"] is False
    assert result["zero_score"] is True
    assert result["full_score"] is False
    assert len(result["gap_concepts"]) == 3
    assert len(result["mastered_concepts"]) == 0
    assert "personalized_graph" in result
    p_graph = result["personalized_graph"]
    assert "nodes" in p_graph and len(p_graph["nodes"]) >= 3
    # Ensure gap nodes have review_gap status
    gap_statuses = [n["status"] for n in p_graph["nodes"] if n["role"] == "prereq"]
    assert all(s == "review_gap" for s in gap_statuses)
    assert "remediation_message" in result


def test_full_score_unlocked_scenario():
    """Edge Case 2: 3/3 correct must mark target unlocked and suggest downstream topics."""
    mcqs = generate_diagnostic_mcqs("transformer", num_questions=3)
    perfect_answers = {q["id"]: q["correct_option"] for q in mcqs}
    result = evaluate_diagnostic_mcqs(mcqs, perfect_answers, target_concept_id="transformer")
    assert result["success"] is True
    assert result["score"] == "3/3"
    assert result["score_pct"] == 100.0
    assert result["passed"] is True
    assert result["full_score"] is True
    assert result["zero_score"] is False
    assert len(result["mastered_concepts"]) == 3
    assert len(result["gap_concepts"]) == 0
    p_graph = result["personalized_graph"]
    target_node = next((n for n in p_graph["nodes"] if n["id"] == "transformer"), None)
    assert target_node is not None
    assert target_node["status"] == "unlocked"


def test_anti_tamper_input_validation():
    """Anti-tamper: Reject malformed payload, unbounded submissions, and foreign question IDs."""
    from archipelago.inference.diagnostic_mcq import validate_mcq_submission
    mcqs = generate_diagnostic_mcqs("transformer", num_questions=3)

    # 1. Reject empty target
    valid, err, _ = validate_mcq_submission(mcqs, {"1": "A"}, "")
    assert not valid
    assert "Target concept ID" in err

    # 2. Reject excessive answers (>10)
    huge_answers = {f"q_{i}": "A" for i in range(15)}
    valid, err, _ = validate_mcq_submission(mcqs, huge_answers, "transformer")
    assert not valid
    assert "limit exceeded" in err

    # 3. Strip invalid choices (only A, B, C, D allowed)
    dirty_answers = {mcqs[0]["id"]: "MALICIOUS_INJECTION", mcqs[1]["id"]: "B"}
    valid, err, sanitized = validate_mcq_submission(mcqs, dirty_answers, "transformer")
    assert valid
    assert mcqs[0]["id"] not in sanitized
    assert sanitized[mcqs[1]["id"]] == "B"


def test_diagnostic_mcqs_endpoint_latency_and_contract():
    """Verify /api/chat/diagnostic-mcqs endpoint response structure and fast fallback."""
    import time
    from archipelago.inference import state as st
    from archipelago.inference.routes_chat import init_concepts_data
    init_concepts_data()

    with st.app.test_client() as client:
        start_t = time.time()
        resp = client.get("/api/chat/diagnostic-mcqs?concept=retrieval_augmented_generation")
        duration = time.time() - start_t
        assert resp.status_code == 200
        # Production objective: guarantees <= 200ms
        assert duration < 0.25, f"Response time {duration}s exceeded SLA limit"
        data = resp.get_json()
        assert data["success"] is True
        assert data["available"] is True
        # Adaptive protocol issues one question at a time; never expose future keys.
        assert len(data["mcqs"]) == 1
        assert data["session_id"]
        assert data["initial_questions"] == 3
        assert data["max_questions"] == 10
        assert "correct_option" not in data["initial_question"]
        for mcq in data["mcqs"]:
            assert set(mcq["options"].keys()) == {"A", "B", "C", "D"}


def test_telemetry_endpoint():
    """Verify /api/chat/telemetry records user choice correctly."""
    from archipelago.inference import state as st
    with st.app.test_client() as client:
        resp = client.post(
            "/api/chat/telemetry",
            json={"event": "graph_choice", "mode": "personalized", "concept_id": "retrieval_augmented_generation"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["logged"] is True
        assert data["mode"] == "personalized"


def test_chat_server_telemetry_and_mcq_proxies(monkeypatch):
    """Verify chat_server forwards telemetry and diagnostic-mcqs endpoints."""
    import chat_server
    from archipelago import supabase_auth
    principal = supabase_auth.AuthPrincipal("test-user", "student", "student", "test-token")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setattr(supabase_auth, "authenticate_request", lambda _request: (principal, None))

    class MockResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        content = b'{"success": true, "mcqs": []}'

    def mock_get(url, params=None, headers=None, timeout=None):
        assert "diagnostic-mcqs" in url
        return MockResponse()

    def mock_post(url, json=None, headers=None, timeout=None):
        assert "telemetry" in url
        return MockResponse()

    monkeypatch.setattr(chat_server._requests, "get", mock_get)
    monkeypatch.setattr(chat_server._requests, "post", mock_post)

    with chat_server.app.test_client() as client:
        resp_mcq = client.get("/api/chat/diagnostic-mcqs?concept=transformer")
        assert resp_mcq.status_code == 200

        resp_tel = client.post("/api/chat/telemetry", json={"event": "graph_choice", "mode": "normal"})
        assert resp_tel.status_code == 200


def test_dag_cycle_prevention():
    """Verify build_personalized_graph_dag creates a valid cycle-free directed acyclic graph."""
    from archipelago.inference.diagnostic_mcq import build_personalized_graph_dag

    eval_details = [
        {"concept_id": "linear_algebra", "concept_name": "Linear Algebra", "is_correct": True, "citation": "Ref 1"},
        {"concept_id": "vector_space", "concept_name": "Vector Spaces", "is_correct": False, "citation": "Ref 2"},
    ]
    graph = build_personalized_graph_dag(
        target_concept_id="embeddings",
        mastered_concepts=["linear_algebra"],
        gap_concepts=["vector_space"],
        eval_details=eval_details,
    )
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert "embeddings" in nodes
    assert "linear_algebra" in nodes
    assert "vector_space" in nodes

    # Status check
    assert nodes["linear_algebra"]["status"] == "mastered"
    assert nodes["vector_space"]["status"] == "review_gap"
    assert nodes["embeddings"]["status"] == "target"

    # Cycle check: verify all edges flow prereq -> target, no self-loops, no back edges
    assert len(graph["edges"]) >= 2
    for edge in graph["edges"]:
        assert edge["source"] in nodes
        assert edge["target"] in nodes
        assert edge["source"] != edge["target"]
    assert graph["is_dag"] is True


def test_adaptive_step_leap_back_and_completion():
    """Verify adaptive leap-back on gap and 3-tick early completion."""
    from archipelago.inference.diagnostic_mcq import execute_adaptive_step

    # 1. Correct answer increments consecutive ticks
    step1 = execute_adaptive_step({
        "target_concept": "low_rank_adaptation",
        "current_concept": "fine_tuning",
        "user_choice": "A",
        "history": [],
        "consecutive_ticks": 0,
        "current_mcq": {
            "id": "mcq_fine_tuning_1",
            "concept_id": "fine_tuning",
            "question": "PEFT definition",
            "options": {"A": "Correct", "B": "W1", "C": "W2", "D": "W3"},
            "correct_option": "A",
            "explanation": "Exp",
            "citation": "Cit",
        }
    })
    assert step1["is_tick"] is True
    assert step1["consecutive_ticks"] == 1
    assert step1["completed"] is False
    assert step1["stride_action"] == "advance"

    # 2. Incorrect answer triggers leap back
    step2 = execute_adaptive_step({
        "target_concept": "low_rank_adaptation",
        "current_concept": "transformer",
        "user_choice": "C",  # Wrong answer
        "history": step1["history"],
        "consecutive_ticks": 1,
        "current_mcq": {
            "id": "mcq_transformer_2",
            "concept_id": "transformer",
            "question": "Transformer question",
            "options": {"A": "W1", "B": "Correct", "C": "W2", "D": "W3"},
            "correct_option": "B",
            "explanation": "Exp",
            "citation": "Cit",
        }
    })
    assert step2["is_tick"] is False
    assert step2["consecutive_ticks"] == 0
    assert step2["completed"] is False
    assert step2["stride_action"] == "leap_back"

    # 3. Three consecutive ticks completes session
    hist = list(step1["history"])
    step3 = execute_adaptive_step({
        "target_concept": "low_rank_adaptation",
        "current_concept": "matrix_multiplication",
        "user_choice": "A",
        "history": hist,
        "consecutive_ticks": 2,  # Already at 2 ticks, this makes 3!
        "current_mcq": {
            "id": "mcq_matrix_multiplication_3",
            "concept_id": "matrix_multiplication",
            "question": "Matrix dims",
            "options": {"A": "Correct", "B": "W1", "C": "W2", "D": "W3"},
            "correct_option": "A",
            "explanation": "Exp",
            "citation": "Cit",
        }
    })
    assert step3["is_tick"] is True
    assert step3["consecutive_ticks"] == 3
    assert step3["completed"] is True
    assert "personalized_graph" in step3
    assert "evaluation" in step3



def test_local_proxy_preserves_private_diagnostic_cookie(monkeypatch):
    """A browser must keep its owner binding across the separate local UI service."""
    import chat_server
    from archipelago import supabase_auth

    principal = supabase_auth.AuthPrincipal("test-user", "student", "student", "test-token")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setattr(supabase_auth, "authenticate_request", lambda _request: (principal, None))
    nonce = "a" * 43

    class Reply:
        status_code = 200
        content = b'{"success": true}'
        headers = {
            "Content-Type": "application/json",
            "Set-Cookie": f"archipelago_learning={nonce}; HttpOnly; SameSite=Strict; Path=/",
        }

    def get(*args, **kwargs):
        assert kwargs["headers"]["Cookie"] == f"archipelago_learning={nonce}"
        return Reply()

    monkeypatch.setattr(chat_server._requests, "get", get)
    with chat_server.app.test_client() as client:
        client.set_cookie("archipelago_learning", nonce)
        response = client.get("/api/chat/diagnostic-mcqs?concept=n0")
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["Set-Cookie"]
        assert response.headers["Cache-Control"] == "no-store, private"
