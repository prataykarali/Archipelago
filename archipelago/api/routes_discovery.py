"""Topic discovery, roadmap, and diagnostic MCQ routes."""

from __future__ import annotations

import logging
from typing import Any

from flask import jsonify, request
from flask.typing import ResponseReturnValue

from archipelago.api import engine_state as state
from archipelago.api.engine_state import (
    DEFAULT_MCQ_CORRECT,
    DEFAULT_MCQ_SCORE,
    DEFAULT_MCQ_TOTAL,
    TOPIC_SUGGEST_LIMIT,
    app,
    concept_node,
    ensure_engine,
)
from archipelago.scholarly.access import ResearchCapability, require_research
from archipelago.scholarly.discovery.orchestrator import DiscoveryOrchestrator
from archipelago.scholarly.pipeline.routes import _store

logger = logging.getLogger("archipelago.api")

SUCCESS_STATUS = 200
BAD_REQUEST_STATUS = 400
QUESTION_COUNT = 3
ROADMAP_MASTERY_THRESHOLD = 0.66
ROADMAP_STEP_COUNT = 3
ROADMAP_DEFAULT_CONCEPT = "Deep Learning"
MAX_SCHOLARLY_QUERY_CHARS = 200
SCHOLARLY_RESULTS_PER_SOURCE = 5


def _requested_concept(data: dict[str, Any]) -> str:
    """Resolve the target concept id from args or JSON body."""
    return (
        request.args.get("concept")
        or request.args.get("target_concept")
        or data.get("target_concept")
        or data.get("concept")
        or ""
    ).strip()


@app.route("/api/topics/suggest", methods=["GET"])
def api_topic_suggest() -> ResponseReturnValue:
    """Fuzzy concept discovery returning top candidates with prerequisite roadmap."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), BAD_REQUEST_STATUS

    ensure_engine()
    assert state._retriever is not None and state._synthesis is not None
    candidates = state._retriever.suggest_topics(query, top_k=TOPIC_SUGGEST_LIMIT)
    return jsonify(state._synthesis.generate_topic_suggestions(query, candidates)), SUCCESS_STATUS


@app.get("/api/scholarly/discover")
@require_research(ResearchCapability.SEARCH)
def api_scholarly_discover() -> ResponseReturnValue:
    """Return staff-only scholarly metadata with honest live source status."""
    query = request.args.get("q", "").strip()
    if not query or len(query) > MAX_SCHOLARLY_QUERY_CHARS:
        return jsonify({"error": "q must contain 1 to 200 characters"}), BAD_REQUEST_STATUS
    if _store() is None:
        return jsonify({"error": "research_disabled"}), 503
    candidates, sources = DiscoveryOrchestrator().discover_with_status(
        query, limit_per_source=SCHOLARLY_RESULTS_PER_SOURCE
    )
    return jsonify(
        {
            "query": query,
            "source_status": sources,
            "candidates": [
                {"paper": item["paper"].model_dump(mode="json"), "source": item.get("source")}
                for item in candidates
            ],
        }
    ), SUCCESS_STATUS


@app.route("/api/roadmap/quiz", methods=["POST"])
def api_roadmap_quiz() -> ResponseReturnValue:
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
def api_chat_diagnostic_mcqs() -> ResponseReturnValue:
    """Retrieve diagnostic MCQs and prerequisite sequence for target concept."""
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    target_id = _requested_concept(data)
    if not target_id:
        return jsonify(
            {
                "error": "Missing target concept",
                "available": False,
                "mcqs": [],
            }
        ), BAD_REQUEST_STATUS

    try:
        from archipelago.inference.diagnostic_mcq import (
            generate_diagnostic_mcqs,
            generate_single_mcq_on_the_spot,
            get_prerequisite_chain,
        )

        t_node = concept_node(target_id)
        prereqs: list[str] = []
        for prerequisite in t_node.get("prerequisites") or []:
            value = prerequisite.get("id") if isinstance(prerequisite, dict) else prerequisite
            if value:
                prereqs.append(str(value))
        mcqs = generate_diagnostic_mcqs(
            target_id,
            prereq_ids=prereqs,
            num_questions=QUESTION_COUNT,
            concepts_data=state._concepts_data,
        )
        chain = get_prerequisite_chain(target_id, state._concepts_data)
        prereq_chain = [c for c in chain if c != target_id]
        immediate_prereq = prereq_chain[-1] if prereq_chain else target_id
        initial_q = generate_single_mcq_on_the_spot(
            immediate_prereq, state._concepts_data, q_index=1
        )

        return jsonify(
            {
                "success": True,
                "available": bool(mcqs),
                "target_concept": target_id,
                "chain": chain,
                "prereq_chain": prereq_chain,
                "immediate_prerequisite": immediate_prereq,
                "initial_question": initial_q,
                "mcqs": mcqs,
            }
        ), SUCCESS_STATUS
    except Exception as exc:
        logger.warning("Diagnostic MCQ API error: %s", exc)
        return jsonify(
            {
                "success": False,
                "available": False,
                "target_concept": target_id,
                "mcqs": [],
                "badge": "Personalized assessment temporarily unavailable.",
            }
        ), SUCCESS_STATUS


@app.route("/api/chat/verify-mcq", methods=["POST"])
def api_chat_verify_mcq() -> ResponseReturnValue:
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
def api_chat_adaptive_step() -> ResponseReturnValue:
    """Execute an on-the-spot adaptive leap-back skip-list step."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    from archipelago.inference.diagnostic_mcq import execute_adaptive_step

    result = execute_adaptive_step(data, concepts_data=state._concepts_data)
    return jsonify(result), SUCCESS_STATUS


@app.route("/api/chat/telemetry", methods=["POST"])
def api_chat_telemetry() -> ResponseReturnValue:
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
