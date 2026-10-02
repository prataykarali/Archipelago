"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from flask import jsonify, send_from_directory, request, redirect
from archipelago.inference import state as st
from archipelago import supabase_auth


@st.app.route("/api/auth/config", methods=["GET"])
def api_auth_config():
    """Return browser-safe Supabase configuration."""
    try:
        from archipelago import supabase_auth
        return jsonify(supabase_auth.public_config())
    except Exception as exc:
        return jsonify({"configured": False, "error": str(exc)}), 500


@st.app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    """Return the authenticated user's Archipelago role."""
    try:
        from archipelago import supabase_auth
        if not supabase_auth.is_auth_required():
            return jsonify({"authenticated": False, "auth_required": False})
        principal, error = supabase_auth.authenticate_request(request)
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": error}), 401
        return jsonify({
            "authenticated": True,
            "user_id": principal.user_id,
            "username": principal.username,
            "role": principal.role,
        })
    except Exception as exc:
        return jsonify({"error": "unauthorized", "detail": str(exc)}), 500


@st.app.route("/api/users", methods=["GET", "POST", "OPTIONS"])
@st.app.route("/api/users/<user_id>", methods=["PUT", "DELETE", "OPTIONS"])
def manage_users_api_backend(user_id=None):
    """User management endpoints for librarian and administrator."""
    if request.method == "OPTIONS":
        return ("", 204)

    from archipelago import supabase_auth
    principal, auth_err = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": auth_err or "Authentication required"}), 401

    if request.method == "GET":
        users, err = supabase_auth.list_managed_users(principal)
        if err:
            return jsonify({"error": "forbidden", "detail": err}), 403
        return jsonify({"users": users, "requester": {"role": principal.role, "user_id": principal.user_id}})

    elif request.method == "POST":
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.create_managed_user(principal, data)
        if err:
            return jsonify({"error": "bad_request", "detail": err}), 400
        return jsonify({"success": True, "user": user}), 201

    elif request.method == "PUT":
        if not user_id:
            return jsonify({"error": "missing_user_id"}), 400
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.update_managed_user(principal, user_id, data)
        if err:
            return jsonify({"error": "update_failed", "detail": err}), 400
        return jsonify({"success": True, "user": user})

    elif request.method == "DELETE":
        if not user_id:
            return jsonify({"error": "missing_user_id"}), 400
        ok, err = supabase_auth.delete_managed_user(principal, user_id)
        if err:
            return jsonify({"error": "delete_failed", "detail": err}), 400
        return jsonify({"success": True})

    return jsonify({"error": "method_not_allowed"}), 405
