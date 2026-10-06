"""Private, ephemeral adaptive diagnostic endpoints; no shared response cache."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import secrets

from engine import adaptive_session
from flask import Flask, current_app, jsonify, request
from runtime_paths import runtime_cache_dir

from ..context import AppContext
from ..learning_memory import RETENTION_SECONDS, LearningMemory
from ..quiz_store import SESSION_TTL_SECONDS, QuizStore

OWNER_COOKIE = "archipelago_learning"


def _owner(nonce: str) -> str:
    """Bind sessions to the browser and current login, without retaining credentials."""
    identity = request.headers.get("Authorization", "") or request.cookies.get(
        "archipelago_token", ""
    )
    return hashlib.sha256((nonce + "\0" + identity).encode()).hexdigest()


def register(app: Flask, ctx: AppContext) -> None:
    """Register owner-isolated routes around the existing graph and presentation contract."""
    store = QuizStore(
        Path(os.getenv("ARCHIPELAGO_QUIZ_DB", str(runtime_cache_dir() / "quiz_sessions.sqlite3")))
    )

    memory = LearningMemory(store.path.with_name("learning_memory.sqlite3"))
    app.extensions["learning_memory"] = memory
    from .learning_settings import settings_response

    app.add_url_rule(
        "/api/chat/learning-memory",
        endpoint="learning_memory",
        view_func=lambda: settings_response(memory),
        methods=["GET", "DELETE"],
    )
    app.add_url_rule(
        "/api/chat/diagnostic-mcqs",
        endpoint="diagnostic_mcqs",
        view_func=lambda: start_response(ctx.engine.graph, store),
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/chat/adaptive-step",
        endpoint="adaptive_step",
        view_func=lambda: step_response(ctx.engine.graph, store),
        methods=["POST"],
    )


def start_response(graph, store):
    """Issue the first question within the calling Flask context."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    target = request.args.get("concept") or body.get("target_concept") or body.get("concept", "")
    preference = request.args.get("preference") or body.get("preference", "conceptual")
    nonce = request.cookies.get(OWNER_COOKIE) or secrets.token_urlsafe(32)
    owner = _owner(nonce)
    memory = _memory(store)
    saved = memory.load(owner)
    remember = request.args.get("remember") == "1" or bool(saved)
    try:
        state, payload = adaptive_session.start(
            graph,
            target,
            preference,
            remembered=saved.get("mastery", {}),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    if remember:
        memory.enable(owner)
    payload["session_id"] = store.create(owner, state)
    payload["memory_enabled"] = remember
    response = jsonify(payload)
    response.set_cookie(
        OWNER_COOKIE,
        nonce,
        max_age=RETENTION_SECONDS if remember else SESSION_TTL_SECONDS,
        httponly=True,
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
        return jsonify(
            {"error": "Start a diagnostic and submit its session and question IDs."}
        ), 400
    nonce = request.cookies.get(OWNER_COOKIE)
    if not nonce:
        return jsonify({"error": "Start a diagnostic in this browser first."}), 403
    try:
        payload = store.advance(
            str(body.get("session_id", "")),
            _owner(nonce),
            lambda state: _advance(graph, state, body, _memory(store), _owner(nonce)),
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store, private"
    return response


def _memory(store):
    memory = current_app.extensions.get("learning_memory")
    if memory is None:
        memory = LearningMemory(store.path.with_name("learning_memory.sqlite3"))
        current_app.extensions["learning_memory"] = memory
    return memory


def _advance(graph, state, body, memory, owner):
    payload = adaptive_session.advance(graph, state, body)
    memory.save(owner, state)
    # Inventory stays local and is joined by explicit source IDs, not sent to inference.
    from engine.gap_resources import gap_resources
    from library_inventory import load_inventory

    payload["gap_resources"] = gap_resources(graph, payload["gaps"], load_inventory() or [])
    return payload
