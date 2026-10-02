"""Authentication and user-management routes."""

from __future__ import annotations

from flask import Response, g, jsonify, request

from archipelago import supabase_auth
from archipelago.api.engine_state import app

METHOD_NOT_ALLOWED_STATUS = 405
NO_CONTENT_STATUS = 204
UNAUTHORIZED_STATUS = 401
FORBIDDEN_STATUS = 403
BAD_REQUEST_STATUS = 400
CREATED_STATUS = 201
MISSING_USER_ID = "missing_user_id"
METHOD_NOT_ALLOWED = "method_not_allowed"
UNAUTHORIZED_BODY_KEY = "unauthorized"
FORBIDDEN_BODY_KEY = "forbidden"
BAD_REQUEST_BODY_KEY = "bad_request"
AUTH_REQUIRED_DETAIL = "Authentication required"


@app.route("/api/auth/config", methods=["GET"])
def api_auth_config() -> Response:
    """Return only browser-safe Supabase Auth settings."""
    return jsonify(supabase_auth.public_config())


@app.route("/api/auth/me", methods=["GET"])
def api_auth_me() -> Response:
    """Return the authenticated user's Archipelago role."""
    if not supabase_auth.is_auth_required():
        return jsonify({"authenticated": False, "auth_required": False})
    principal = getattr(g, "archipelago_principal", None)
    if principal is None:
        return jsonify({"error": UNAUTHORIZED_BODY_KEY}), 401
    return jsonify(
        {
            "authenticated": True,
            "user_id": principal.user_id,
            "username": principal.username,
            "role": principal.role,
        }
    )


def _current_principal():
    """Return the session principal, authenticating directly when absent."""
    principal = getattr(g, "archipelago_principal", None)
    if principal is not None:
        return principal, None
    return supabase_auth.authenticate_request(request)


@app.route("/api/users", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/users/<user_id>", methods=["PUT", "DELETE", "OPTIONS"])
def api_manage_users(user_id=None) -> Response:
    """Manage users with role-based access for librarian and administrator."""
    if request.method == "OPTIONS":
        return Response("", NO_CONTENT_STATUS)

    principal, auth_err = _current_principal()
    if principal is None:
        return jsonify(
            {
                "error": UNAUTHORIZED_BODY_KEY,
                "detail": auth_err or AUTH_REQUIRED_DETAIL,
            }
        ), UNAUTHORIZED_STATUS

    if request.method == "GET":
        users, err = supabase_auth.list_managed_users(principal)
        if err:
            return jsonify({"error": FORBIDDEN_BODY_KEY, "detail": err}), FORBIDDEN_STATUS
        return jsonify(
            {
                "users": users,
                "requester": {"role": principal.role, "user_id": principal.user_id},
            }
        )

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.create_managed_user(principal, data)
        if err:
            return jsonify({"error": BAD_REQUEST_BODY_KEY, "detail": err}), BAD_REQUEST_STATUS
        return jsonify({"success": True, "user": user}), CREATED_STATUS

    if request.method == "PUT":
        if not user_id:
            return jsonify({"error": MISSING_USER_ID}), BAD_REQUEST_STATUS
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.update_managed_user(principal, user_id, data)
        if err:
            return jsonify({"error": "update_failed", "detail": err}), BAD_REQUEST_STATUS
        return jsonify({"success": True, "user": user})

    if request.method == "DELETE":
        if not user_id:
            return jsonify({"error": MISSING_USER_ID}), BAD_REQUEST_STATUS
        ok, err = supabase_auth.delete_managed_user(principal, user_id)
        if err:
            return jsonify({"error": "delete_failed", "detail": err}), BAD_REQUEST_STATUS
        return jsonify({"success": True})

    return jsonify({"error": METHOD_NOT_ALLOWED}), METHOD_NOT_ALLOWED_STATUS
