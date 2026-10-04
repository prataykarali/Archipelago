"""Topic discovery, roadmap, and diagnostic MCQ routes."""

from __future__ import annotations

import logging

from flask import Response, jsonify, request

from archipelago.api import engine_state as state
from archipelago.api.engine_state import (
    DEFAULT_MCQ_CORRECT,
    DEFAULT_MCQ_SCORE,
    DEFAULT_MCQ_TOTAL,
    TOPIC_SUGGEST_LIMIT,
    app,
    ensure_engine,
)

logger = logging.getLogger("archipelago.api")

SUCCESS_STATUS = 200
BAD_REQUEST_STATUS = 400
QUESTION_COUNT = 3
ROADMAP_MASTERY_THRESHOLD = 0.66
ROADMAP_STEP_COUNT = 3
ROADMAP_DEFAULT_CONCEPT = "Deep Learning"


def _requested_concept(data: dict) -> str:
    """Resolve the target concept id from args or JSON body."""
    return (
        request.args.get("concept")
        or request.args.get("target_concept")
        or data.get("target_concept")
        or data.get("concept")
        or ""
    ).strip()


@app.route("/api/topics/suggest", methods=["GET"])
def api_topic_suggest() -> Response:
    """Fuzzy concept discovery returning top candidates with prerequisite roadmap."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), BAD_REQUEST_STATUS

    ensure_engine()
    candidates = state._retriever.suggest_topics(query, top_k=TOPIC_SUGGEST_LIMIT)
    return jsonify(state._synthesis.generate_topic_suggestions(query, candidates)), SUCCESS_STATUS


@app.route("/api/roadmap/quiz", methods=["POST"])
def api_roadmap_quiz() -> Response:
    """Evaluate diagnostic MCQ answers and produce a custom learning roadmap."""
    data = request.get_json(silent=True) or {}
    concept = data.get("concept", ROADMAP_DEFAULT_CONCEPT)
    answers = data.get("answers", {})

    total = len(answers) if answers else DEFAULT_MCQ_TOTAL
    correct = (
        sum(1 for v in answers.values() if str(v).upper() == "A")
        if answers
        else DEFAULT_MCQ_CORRECT
    )
    score = (correct / total) if total > 0 else DEFAULT_MCQ_SCORE

    roadmap = [
        {
            "step": 1,
            "concept": "Mathematical Foundations",
            "status": "Mastered" if score > 0.6 else "Review Required",
        },
        {
            "step": 2,
            "concept": "Linear Algebra & SVD",
            "status": "Mastered" if score > 0.8 else "In Progress",
        },
        {"step": ROADMAP_STEP_COUNT, "concept": concept, "status": "Unlocked Ready for Study"},
    ]

    return jsonify(
        {
            "concept": concept,
            "score": round(score, 2),
            "mastery": "Sufficient" if score >= ROADMAP_MASTERY_THRESHOLD else "Needs Remediation",
            "custom_roadmap": roadmap,
        }
    ), SUCCESS_STATUS


@app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST"])
def api_chat_diagnostic_mcqs() -> Response:
    """Use private server-authoritative learning sessions across local and hosted apps."""
    from archipelago.personalization_bridge import diagnostic_response

    return diagnostic_response(state._concepts_data, start=True)


@app.route("/api/chat/verify-mcq", methods=["POST"])
def api_chat_verify_mcq() -> Response:
    """Validate user answers for diagnostic MCQs and calculate prerequisite mastery."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    from archipelago.inference.diagnostic_mcq import (
        evaluate_diagnostic_mcqs,
        generate_diagnostic_mcqs,
    )

    mcqs = data.get("mcqs") or []
    answers = data.get("answers") or {}
    target_id = data.get("target_concept") or ""
    if not mcqs and target_id:
        mcqs = generate_diagnostic_mcqs(
            target_id,
            num_questions=QUESTION_COUNT,
            concepts_data=state._concepts_data,
        )

    result = evaluate_diagnostic_mcqs(
        mcqs,
        answers,
        target_concept_id=target_id,
        concepts_data=state._concepts_data,
    )
    return jsonify(result), SUCCESS_STATUS


@app.route("/api/chat/adaptive-step", methods=["POST"])
def api_chat_adaptive_step() -> Response:
    """Use private server-authoritative learning sessions across local and hosted apps."""
    from archipelago.personalization_bridge import diagnostic_response

    return diagnostic_response(state._concepts_data, start=False)


@app.route("/api/chat/telemetry", methods=["POST"])
def api_chat_telemetry() -> Response:
    """Track choice analytics (Personalized vs Normal graph selections)."""
    try:
        data = request.get_json(silent=True) or {}
        event = data.get("event", "graph_choice")
        mode = data.get("mode", "unknown")
        concept_id = data.get("concept_id", "")
        logger.info("[TELEMETRY] event=%s mode=%s concept=%s", event, mode, concept_id)
        return jsonify({"logged": True, "event": event, "mode": mode}), SUCCESS_STATUS
    except Exception as exc:
        return jsonify({"logged": False, "error": str(exc)}), SUCCESS_STATUS
