"""Supabase session routes.

One concern: telling the browser how to authenticate, issuing the session
cookie, and reporting the current principal.  Secrets never reach the client —
only the publishable key.
"""

from __future__ import annotations

import hmac
import os

from flask import Flask, jsonify, request
import requests
from supabase_service_headers import service_headers

from ..config import SESSION_COOKIE_MAX_AGE, SESSION_COOKIE_NAME
from ..context import AppContext

PRODUCTION_ENVS = {"production", "prod"}
MIN_NEW_PASSWORD_LENGTH = 12
ADMIN_TIMEOUT_SECONDS = 15


def _service_key() -> str:
    return (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )


def register(app: Flask, ctx: AppContext) -> None:
    """Register auth routes on ``app``."""

    @app.get("/api/auth/config")
    def auth_config():
        url, key = ctx.auth.supabase()
        configured = bool(url and key)
        return jsonify(
            {
                "configured": configured,
                "required": ctx.auth.required(),
                "url": url if configured else None,
                "publishableKey": key if configured else None,
                "chatUrl": None,
                "graphUrl": None,
            }
        )

    @app.route("/api/auth/session", methods=["POST", "DELETE", "OPTIONS"])
    def auth_session():
        if request.method == "DELETE":
            response = jsonify({"authenticated": False})
            response.delete_cookie(SESSION_COOKIE_NAME, path="/")
            return response
        principal, error = ctx.auth.principal()
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": error}), 401
        response = jsonify(
            {
                "authenticated": True,
                "role": principal["role"],
                "must_change_password": principal.get("must_change_password", False),
            }
        )
        response.set_cookie(
            SESSION_COOKIE_NAME,
            principal["token"],
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            secure=os.getenv("ARCHIPELAGO_ENV", "production").lower() in PRODUCTION_ENVS,
            samesite="Lax",
            path="/",
        )
        return response

    @app.get("/api/auth/me")
    def auth_me():
        if not ctx.auth.required():
            return jsonify({"authenticated": False, "role": "student", "open": True})
        principal, error = ctx.auth.principal()
        if principal is None:
            return jsonify({"authenticated": False, "detail": error}), 401
        return jsonify(
            {
                "authenticated": True,
                "role": principal["role"],
                "username": principal["username"],
                "user_id": principal.get("user_id"),
                "must_change_password": principal.get("must_change_password", False),
            }
        )

    @app.post("/api/auth/change-password")
    def change_password():
        """Replace a bootstrap password and clear its server-owned first-login flag."""
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            return jsonify(
                {"error": "unauthorized", "detail": "A bearer session is required."}
            ), 401
        principal, error = ctx.auth.principal()
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": error}), 401
        payload = request.get_json(silent=True) or {}
        password = payload.get("new_password") if isinstance(payload, dict) else None
        if not isinstance(password, str) or len(password) < MIN_NEW_PASSWORD_LENGTH:
            return jsonify(
                {"error": "invalid_password", "detail": "Choose at least 12 characters."}
            ), 400
        bootstrap = os.getenv("ARCHIPELAGO_BOOTSTRAP_PASSWORD", "")
        if bootstrap and hmac.compare_digest(password, bootstrap):
            return jsonify(
                {
                    "error": "invalid_password",
                    "detail": "Choose a password different from the initial password.",
                }
            ), 400
        url, _key = ctx.auth.supabase()
        secret = _service_key()
        if not url or not secret:
            return jsonify(
                {"error": "unavailable", "detail": "Password change is unavailable."}
            ), 503
        headers = service_headers(secret, json_body=True)
        user_id = principal.get("user_id")
        if not isinstance(user_id, str) or not user_id:
            return jsonify({"error": "unauthorized"}), 401
        metadata = principal.get("app_metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        try:
            response = requests.put(
                f"{url}/auth/v1/admin/users/{user_id}",
                headers=headers,
                json={
                    "password": password,
                    "app_metadata": {**metadata, "must_change_password": False},
                },
                timeout=ADMIN_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            return jsonify(
                {"error": "unavailable", "detail": "Password change is unavailable."}
            ), 503
        if response.status_code not in {200, 204}:
            return jsonify({"error": "unavailable", "detail": "Password change failed."}), 503
        return jsonify({"ok": True})
