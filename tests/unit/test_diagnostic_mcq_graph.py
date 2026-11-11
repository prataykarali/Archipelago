"""Graph sequencing cases for the diagnostic MCQ layer."""


def test_dag_cycle_prevention():
    """Verify build_personalized_graph_dag creates a valid cycle-free directed acyclic graph."""
    from archipelago.inference.diagnostic_mcq import build_personalized_graph_dag

    eval_details = [
        {
            "concept_id": "linear_algebra",
            "concept_name": "Linear Algebra",
            "is_correct": True,
            "citation": "Ref 1",
        },
        {
            "concept_id": "vector_space",
            "concept_name": "Vector Spaces",
            "is_correct": False,
            "citation": "Ref 2",
        },
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
    step1 = execute_adaptive_step(
        {
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
            },
        }
    )
    assert step1["is_tick"] is True
    assert step1["consecutive_ticks"] == 1
    assert step1["completed"] is False
    assert step1["stride_action"] == "advance"

    # 2. Incorrect answer triggers leap back
    step2 = execute_adaptive_step(
        {
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
            },
        }
    )
    assert step2["is_tick"] is False
    assert step2["consecutive_ticks"] == 0
    assert step2["completed"] is False
    assert step2["stride_action"] == "leap_back"

    # 3. Three consecutive ticks completes session
    hist = list(step1["history"])
    step3 = execute_adaptive_step(
        {
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
            },
        }
    )
    assert step3["is_tick"] is True
    assert step3["consecutive_ticks"] == 3
    assert step3["completed"] is True
    assert "personalized_graph" in step3
    assert "evaluation" in step3
