"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from collections.abc import Iterator
from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
from flask.typing import ResponseReturnValue
import requests as _requests
from .learning_proxy import learning_headers, learning_response
from .merged01_repo_root import INFERENCE_CHAT_URL, _STREAM_CHUNK_BYTES, _inference_auth_headers, app  # noqa: F401


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat_proxy() -> ResponseReturnValue:
    """Proxy chat prompts to the upstream inference server, streaming the reply."""
    if request.method == "OPTIONS":
        return ("", 204)

    payload = request.get_json(silent=True) or {}
    try:
        upstream = _requests.post(
            INFERENCE_CHAT_URL,
            json=payload,
            headers=_inference_auth_headers(),
            stream=True,
            timeout=(5, 300),
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502

    def stream_upstream() -> Iterator[bytes]:
        for chunk in upstream.iter_content(chunk_size=_STREAM_CHUNK_BYTES):
            yield chunk

    return Response(
        stream_upstream(),
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/octet-stream"),
    )


@app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST", "OPTIONS"])
def chat_diagnostic_mcqs_proxy() -> ResponseReturnValue:
    """Proxy diagnostic MCQs requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/diagnostic-mcqs"
    try:
        if request.method == "GET":
            upstream = _requests.get(target, params=request.args, headers=learning_headers(_inference_auth_headers()), timeout=5)
        else:
            upstream = _requests.post(
                target,
                json=request.get_json(silent=True) or {},
                headers=learning_headers(_inference_auth_headers()),
                timeout=5,
            )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for diagnostic-mcqs: %s", exc)
        return {
            "success": False,
            "available": False,
            "badge": "Personalized assessment temporarily unavailable.",
            "error": str(exc),
        }, 200
    return learning_response(upstream)


@app.route("/api/chat/telemetry", methods=["POST", "OPTIONS"])
def chat_telemetry_proxy() -> ResponseReturnValue:
    """Proxy telemetry tracking events to upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/telemetry"
    try:
        upstream = _requests.post(
            target,
            json=request.get_json(silent=True) or {},
            headers=learning_headers(_inference_auth_headers()),
            timeout=5,
        )
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        return {"logged": False, "error": str(exc)}, 200


@app.route("/api/chat/verify-mcq", methods=["POST", "OPTIONS"])
def chat_verify_mcq_proxy() -> ResponseReturnValue:
    """Proxy diagnostic MCQ verification requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/verify-mcq"
    try:
        upstream = _requests.post(
            target,
            json=request.get_json(silent=True) or {},
            headers=learning_headers(_inference_auth_headers()),
            timeout=30,
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for verify-mcq: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return learning_response(upstream)


@app.route("/api/chat/adaptive-step", methods=["POST", "OPTIONS"])
def chat_adaptive_step_proxy() -> ResponseReturnValue:
    """Proxy diagnostic adaptive-step requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/adaptive-step"
    try:
        upstream = _requests.post(
            target,
                json=request.get_json(silent=True) or {},
                headers=learning_headers(_inference_auth_headers()),
                timeout=30,
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for adaptive-step: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return learning_response(upstream)


def _inference_base() -> str:
    """Derive inference origin from ARCHIPELAGO_INFERENCE_URL (…/api/chat)."""
    url = INFERENCE_CHAT_URL.rstrip("/")
    if url.endswith("/api/chat"):
        return url[: -len("/api/chat")]
    if url.endswith("/api/chat/"):
        return url[: -len("/api/chat/")]
    return url


@app.route("/api/dashboards/<path:subpath>", methods=["GET", "POST", "OPTIONS"])
def dashboards_proxy(subpath: str) -> ResponseReturnValue:
    """Proxy performance/safety dashboard APIs to the inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/dashboards/{subpath}"
    try:
        if request.method == "GET":
            upstream = _requests.get(target, params=request.args, headers=_inference_auth_headers(), timeout=15)
        else:
            upstream = _requests.post(
                target,
                json=request.get_json(silent=True) or {},
                headers=_inference_auth_headers(),
                timeout=30,
            )
    except Exception as exc:
        app.logger.warning("Dashboard upstream unreachable: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.route("/api/readiness", methods=["GET", "OPTIONS"])
@app.route("/api/health", methods=["GET", "OPTIONS"])
def readiness_proxy() -> ResponseReturnValue:
    """Proxy readiness/health check to inference engine."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/readiness"
    try:
        upstream = _requests.get(target, timeout=5)
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        return jsonify({"ready": False, "error": str(exc)}), 503
