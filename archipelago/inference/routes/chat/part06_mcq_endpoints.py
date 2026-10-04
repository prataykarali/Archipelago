"""Diagnostic MCQ endpoints: fetch, adaptive step, telemetry, verify."""

from __future__ import annotations

from flask import jsonify, request

from archipelago.inference import state as st


@st.app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST"])
def api_diagnostic_mcqs():
    """Use private server-authoritative learning sessions across local and hosted apps."""
    from archipelago.personalization_bridge import diagnostic_response

    return diagnostic_response(st.CONCEPTS_DATA, start=True)


@st.app.route("/api/chat/adaptive-step", methods=["POST"])
def api_adaptive_step():
    """Use private server-authoritative learning sessions across local and hosted apps."""
    from archipelago.personalization_bridge import diagnostic_response

    return diagnostic_response(st.CONCEPTS_DATA, start=False)


@st.app.route("/api/chat/telemetry", methods=["POST"])
def api_chat_telemetry():
    """Track choice analytics (Personalized vs Normal graph selections)."""
    try:
        data = request.get_json(silent=True) or {}
        event = data.get("event", "graph_choice")
        mode = data.get("mode", "unknown")
        concept_id = data.get("concept_id", "")
        print(f"[TELEMETRY] event={event} mode={mode} concept={concept_id}")
        return jsonify({"logged": True, "event": event, "mode": mode})
    except Exception as exc:
        return jsonify({"logged": False, "error": str(exc)}), 200


@st.app.route("/api/chat/verify-mcq", methods=["POST"])
def api_verify_mcq():
    """Validate user answers for diagnostic MCQs and calculate prerequisite mastery."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    mcqs = data.get("mcqs") or []
    answers = data.get("answers") or {}
    target_id = data.get("target_concept") or ""

    if not mcqs and target_id:
        from archipelago.inference.diagnostic_mcq import generate_diagnostic_mcqs

        mcqs = generate_diagnostic_mcqs(target_id, num_questions=3)

    from archipelago.inference.diagnostic_mcq import evaluate_diagnostic_mcqs

    result = evaluate_diagnostic_mcqs(mcqs, answers, target_concept_id=target_id)
    return jsonify(result)


@st.app.route("/api/chat/learning-memory", methods=["GET", "DELETE"])
def api_learning_memory():
    """Inspect or forget only the current browser's opted-in mastery."""
    from archipelago.personalization_bridge import memory_response
    return memory_response()
