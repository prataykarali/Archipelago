"""Preserve only the private-learning cookie across the local UI/inference proxy."""
from __future__ import annotations

import re

from flask import Response, request

COOKIE = "archipelago_learning"
NONCE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def learning_headers(auth_headers: dict) -> dict:
    """Forward one validated opaque cookie, not the browser's unrelated credentials."""
    headers = dict(auth_headers)
    nonce = request.cookies.get(COOKIE, "")
    if NONCE.fullmatch(nonce):
        headers["Cookie"] = f"{COOKIE}={nonce}"
    return headers


def learning_response(upstream) -> Response:
    """Keep the owner's HttpOnly cookie and no-store policy across the proxy."""
    response = Response(
        upstream.content, status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )
    cookie = upstream.headers.get("Set-Cookie", "")
    if cookie.startswith(f"{COOKIE}="):
        response.headers["Set-Cookie"] = cookie
    response.headers["Cache-Control"] = "no-store, private"
    return response
