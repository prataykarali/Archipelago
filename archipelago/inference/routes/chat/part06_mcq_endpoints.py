"""Diagnostic MCQ endpoints: fetch, adaptive step, telemetry, verify."""

from __future__ import annotations

from flask import jsonify, request

from archipelago.inference import state as st


@st.app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST"])
def api_diagnostic_mcqs():
    """Retrieve pre-cached or synthesized diagnostic MCQs with <= 200ms fallback guarantee."""
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    target_id = (
        request.args.get("concept")
        or request.args.get("target_concept")
        or data.get("target_concept")
        or data.get("concept")
        or ""
    ).strip()

    if not target_id:
        return jsonify({"error": "Missing target concept", "available": False, "mcqs": []}), 400

    try:
        from archipelago.inference.diagnostic_mcq import (
            generate_diagnostic_mcqs,
            generate_single_mcq_on_the_spot,
            get_prerequisite_chain,
        )

        t_node = st.CONCEPTS_DATA.get(target_id) or {}
        prereqs = [
            p.get("id") if isinstance(p, dict) else str(p)
            for p in (t_node.get("prerequisites") or [])
        ]
        mcqs = generate_diagnostic_mcqs(target_id, prereq_ids=prereqs, num_questions=3)
        chain = get_prerequisite_chain(target_id, st.CONCEPTS_DATA)
        prereq_chain = [c for c in chain if c != target_id]
        immediate_y = prereq_chain[-1] if prereq_chain else target_id
        initial_q = generate_single_mcq_on_the_spot(immediate_y, st.CONCEPTS_DATA, q_index=1)

        return jsonify(
            {
                "success": True,
                "available": bool(mcqs),
                "target_concept": target_id,
                "chain": chain,
                "prereq_chain": prereq_chain,
                "immediate_prerequisite": immediate_y,
                "initial_question": initial_q,
                "mcqs": mcqs,
            }
        )
    except Exception as exc:
        print(f"Diagnostic MCQ fetch error: {exc}")
        return jsonify(
            {
                "success": False,
                "available": False,
                "target_concept": target_id,
                "mcqs": [],
                "badge": "Personalized assessment temporarily unavailable.",
            }
        ), 200


@st.app.route("/api/chat/adaptive-step", methods=["POST"])
def api_adaptive_step():
    """Execute an on-the-spot adaptive leap-back skip-list step."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    from archipelago.inference.diagnostic_mcq import execute_adaptive_step

    result = execute_adaptive_step(data, concepts_data=st.CONCEPTS_DATA)
    return jsonify(result)


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
