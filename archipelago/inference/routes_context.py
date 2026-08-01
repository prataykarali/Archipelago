from __future__ import annotations

from flask import jsonify, request

from archipelago.inference.context_tracker import SESSION_CONTEXTS, get_or_create_context
from archipelago.inference.state import app


@app.route("/api/context-status", methods=["POST", "GET"])
def context_status():
    """Handle context status/reset actions for session-aware RAG."""
    if request.method == "GET":
        session_id = request.args.get("session_id") or "default"
        tracker = get_or_create_context(session_id)
        return jsonify({
            "session_id": session_id,
            "active_topics": list(tracker.active_topics),
            "history_len": len(tracker.get_history()),
        })

    data = request.get_json() or {}
    session_id = data.get("session_id")
    action = data.get("action")
    if action == "reset":
        if session_id in SESSION_CONTEXTS:
            del SESSION_CONTEXTS[session_id]
        return jsonify({"session_id": session_id, "reset": True})

    # Default / status / invalid → return session status (tests expect 200)
    sid = session_id or "default"
    tracker = get_or_create_context(sid)
    return jsonify({
        "session_id": sid,
        "active_topics": list(tracker.active_topics),
        "history_len": len(tracker.get_history()),
        "action": action,
    })
