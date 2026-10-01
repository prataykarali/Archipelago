"""Supabase session routes.

One concern: telling the browser how to authenticate, issuing the session
cookie, and reporting the current principal.  Secrets never reach the client —
only the publishable key.
"""
from __future__ import annotations

import os

from flask import Flask, jsonify, request

from ..config import SESSION_COOKIE_MAX_AGE, SESSION_COOKIE_NAME
from ..context import AppContext

PRODUCTION_ENVS = {"production", "prod"}


def register(app: Flask, ctx: AppContext) -> None:
    """Register auth routes on ``app``."""

    @app.get("/api/auth/config")
    def auth_config():
        url, key = ctx.auth.supabase()
        configured = bool(url and key)
        return jsonify({
            "configured": configured,
            "required": ctx.auth.required(),
            "url": url if configured else None,
            "publishableKey": key if configured else None,
            "chatUrl": None,
            "graphUrl": None,
        })

    @app.route("/api/auth/session", methods=["POST", "DELETE", "OPTIONS"])
    def auth_session():
        if request.method == "DELETE":
            response = jsonify({"authenticated": False})
            response.delete_cookie(SESSION_COOKIE_NAME, path="/")
            return response
        principal, error = ctx.auth.principal()
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": error}), 401
        response = jsonify({"authenticated": True, "role": principal["role"]})
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
        return jsonify({"authenticated": True, "role": principal["role"], "username": principal["username"]})
