"""Private, ephemeral adaptive diagnostic endpoints; no shared response cache."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import secrets

from engine import adaptive_session
from flask import Flask, jsonify, request

from ..config import ROOT
from ..context import AppContext
from ..quiz_store import SESSION_TTL_SECONDS, QuizStore

OWNER_COOKIE = "archipelago_learning"


def _owner(nonce: str) -> str:
    """Bind sessions to the browser and current login, without retaining credentials."""
    identity = request.headers.get("Authorization", "") or request.cookies.get("archipelago_token", "")
    return hashlib.sha256((nonce + "\0" + identity).encode()).hexdigest()


def register(app: Flask, ctx: AppContext) -> None:
    """Register owner-isolated routes around the existing graph and presentation contract."""
    store = QuizStore(Path(os.getenv("ARCHIPELAGO_QUIZ_DB", str(ROOT / "cache" / "quiz_sessions.sqlite3"))))

    app.add_url_rule(
        "/api/chat/diagnostic-mcqs", endpoint="diagnostic_mcqs",
        view_func=lambda: start_response(ctx.engine.graph, store), methods=["GET"],
    )
    app.add_url_rule(
        "/api/chat/adaptive-step", endpoint="adaptive_step",
        view_func=lambda: step_response(ctx.engine.graph, store), methods=["POST"],
    )


def start_response(graph, store):
    """Issue the first question within the calling Flask context."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    target = request.args.get("concept") or body.get("target_concept") or body.get("concept", "")
    preference = request.args.get("preference") or body.get("preference", "conceptual")
    try:
        state, payload = adaptive_session.start(graph, target, preference)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    nonce = request.cookies.get(OWNER_COOKIE) or secrets.token_urlsafe(32)
    payload["session_id"] = store.create(_owner(nonce), state)
    response = jsonify(payload)
    response.set_cookie(
        OWNER_COOKIE, nonce, max_age=SESSION_TTL_SECONDS, httponly=True,
        secure=request.is_secure or os.getenv("ARCHIPELAGO_ENV") == "production",
        samesite="Strict",
    )
    response.headers["Cache-Control"] = "no-store, private"
    return response

def step_response(graph, store):
    """Grade one issued question within the calling Flask context."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    if not body.get("session_id") or not body.get("question_id"):
        return jsonify({"error": "Start a diagnostic and submit its session and question IDs."}), 400
    nonce = request.cookies.get(OWNER_COOKIE)
    if not nonce:
        return jsonify({"error": "Start a diagnostic in this browser first."}), 403
    try:
        payload = store.advance(
            str(body.get("session_id", "")), _owner(nonce),
            lambda state: adaptive_session.advance(graph, state, body),
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store, private"
    return response
