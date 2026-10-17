"""CORS and Supabase session enforcement for the production REST API."""

from __future__ import annotations

from flask import Response, g, jsonify, request
from flask.typing import ResponseReturnValue

from archipelago import supabase_auth
from archipelago.api.engine_state import (
    _LIBRARIAN_OR_ADMIN_PATHS,
    _LIBRARIAN_OR_ADMIN_ROLES,
    _PUBLIC_AUTH_PATHS,
    app,
)
from archipelago.auth import load_user
from archipelago.scholarly.access import ResearchCapability, allowed, audit_action

CORS_ALLOWED_HEADERS = "Content-Type,Authorization"
CORS_ALLOWED_METHODS = "GET,POST,PATCH,PUT,DELETE,OPTIONS"
UNAUTHORIZED_BODY_KEY = "unauthorized"
FORBIDDEN_BODY_KEY = "forbidden"
LIBRARIAN_REQUIRED_DETAIL = "Librarian or administrator role required."


@app.after_request
def add_cors(response: Response) -> Response:
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", CORS_ALLOWED_HEADERS)
    response.headers.add("Access-Control-Allow-Methods", CORS_ALLOWED_METHODS)
    return response


app.before_request(load_user)


@app.before_request
def require_supabase_session() -> ResponseReturnValue | None:
    """Protect deployed API routes with a Supabase session and role checks."""
    if request.method == "OPTIONS" or request.path in _PUBLIC_AUTH_PATHS:
        return None
    if request.path.startswith("/api/research/") or request.path == "/api/scholarly/discover":
        principal, _error = supabase_auth.authenticate_request(request)
        if principal is None:
            audit_action(user_id=None, role=None, action="research_access", result="unauthorized")
            return jsonify({"error": UNAUTHORIZED_BODY_KEY}), 401
        capability = (
            ResearchCapability.JOB_CREATE if request.method == "POST" else ResearchCapability.SEARCH
        )
        if not allowed(principal.role, capability):
            audit_action(
                user_id=principal.user_id,
                role=principal.role,
                action=capability.value,
                result="forbidden",
            )
            return jsonify({"error": FORBIDDEN_BODY_KEY}), 403
        g.archipelago_principal = principal
        return None
    if not supabase_auth.is_auth_required():
        return None

    principal, error = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": UNAUTHORIZED_BODY_KEY, "detail": error}), 401
    if (
        request.path in _LIBRARIAN_OR_ADMIN_PATHS or request.path.startswith("/api/users")
    ) and principal.role not in _LIBRARIAN_OR_ADMIN_ROLES:
        return jsonify({"error": FORBIDDEN_BODY_KEY, "detail": LIBRARIAN_REQUIRED_DETAIL}), 403
    g.archipelago_principal = principal
    return None
