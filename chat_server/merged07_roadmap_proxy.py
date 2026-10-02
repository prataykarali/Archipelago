"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
from flask.typing import ResponseReturnValue
import requests as _requests
from .merged01_repo_root import _inference_auth_headers, app  # noqa: F401
from .merged06_chat_proxy import _inference_base  # noqa: F401


@app.route("/api/roadmap", methods=["GET", "POST", "OPTIONS"])
def roadmap_proxy() -> ResponseReturnValue:
    """Proxy learning roadmap to inference engine."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/roadmap"
    try:
        if request.method == "GET":
            upstream = _requests.get(target, params=request.args, headers=_inference_auth_headers(), timeout=10)
        else:
            upstream = _requests.post(
                target,
                json=request.get_json(silent=True) or {},
                headers=_inference_auth_headers(),
                timeout=30,
            )
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/auth/config", methods=["GET"])
@app.route("/api/auth/me", methods=["GET"])
def auth_proxy_or_local():
    """Return browser-safe auth configuration or the verified current principal."""
    from archipelago import supabase_auth
    if request.path == "/api/auth/config":
        return jsonify(supabase_auth.public_config())

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


@app.route("/api/users", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/users/<user_id>", methods=["PUT", "DELETE", "OPTIONS"])
def manage_users_api(user_id=None):
    """User management endpoints for librarian and administrator."""
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-User-Role,X-User-Name,X-User-Id"
        return resp

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
