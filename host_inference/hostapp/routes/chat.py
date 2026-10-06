"""Chat, diagnostics, roadmap and quiz routes.

One concern: the student-facing query pipeline, grounded streaming synthesis,
the adaptive diagnostic QnA flow, and the roadmap/quiz builders.
"""

from __future__ import annotations

import json
import re
import secrets

from engine.patterns import DIAG_RE, INGEST_RE
from flask import Flask, current_app, jsonify, request, stream_with_context
from host_roadmap import build_quiz, build_roadmap

from ..context import AppContext

# Query hygiene: strip null bytes and ASCII control characters, keep whitespace.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_QUERY_CHARS = 500
STREAM_MIME = "text/plain; charset=utf-8"
STREAM_MARKER = "\n[STREAM_START]\n"
TOKENS_SAVED_PER_HIT = 350
TELEMETRY_NO_CONTENT = 204


def _metadata_frame(chunks: list[str]) -> dict:
    """Parse the metadata frame that precedes the stream marker."""
    if not chunks or STREAM_MARKER not in chunks[0]:
        return {}
    try:
        return json.loads(chunks[0].split(STREAM_MARKER, 1)[0].strip())
    except ValueError:
        return {}


def _withdrawn_notice(sources: list) -> str:
    """First withdrawal notice among ``sources``, or "" when all are live.

    Re-derived on every cache replay rather than trusted from the cached
    payload, because a source can be withdrawn *after* the answer was cached.
    """
    for source in sources:
        if isinstance(source, dict) and source.get("withdrawn"):
            notice = str(source.get("notice") or "").strip()
            if notice:
                return notice
    return ""


def register(app: Flask, ctx: AppContext) -> None:
    """Register chat-family routes on ``app``."""

    @app.post("/api/chat")
    def api_chat():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(
                {"error": "invalid_payload", "detail": "Request body must be a JSON object"}
            ), 400
        raw_query = str(body.get("query") or "")
        query = CONTROL_CHARS.sub("", raw_query).strip()
        if len(query) > MAX_QUERY_CHARS:
            return jsonify({"error": "Query exceeds maximum limit of 500 characters"}), 400
        if not query:
            return jsonify({"error": "Query cannot be empty"}), 400

        ctx.cache_metrics.record_request()
        # Never share query results carrying a login or learner state.
        personal = bool(
            request.headers.get("Authorization") or request.cookies.get("archipelago_token")
            or any(body.get(key) for key in ("session_id", "mastery", "learning_state", "preference"))
        )
        cacheable = not personal and not DIAG_RE.search(query) and not INGEST_RE.search(query)
        norm_query = ctx.cache_service.normalize_query(query) if cacheable else secrets.token_urlsafe(24)

        # Only simultaneous requests share work. Completed answers are regenerated.
        if ctx.request_dedup.is_in_flight(norm_query):
            wait_result = ctx.request_dedup.wait(norm_query)
            if wait_result is not None:
                ctx.cache_metrics.record_dedup(tokens_saved=TOKENS_SAVED_PER_HIT)

                def generate_dedup():
                    if isinstance(wait_result, list):
                        yield from wait_result
                    else:
                        yield str(wait_result)

                return current_app.response_class(generate_dedup(), mimetype=STREAM_MIME)

        # Fresh retrieval and inference for each request.
        ctx.cache_metrics.record_miss()
        is_leader = ctx.request_dedup.start_flight(norm_query)

        def generate():
            collected_chunks = []
            try:
                for chunk in ctx.engine.stream_chat(query):
                    collected_chunks.append(chunk)
                    yield chunk

                if collected_chunks and is_leader:
                    ctx.request_dedup.complete(norm_query, collected_chunks)
            except Exception as exc:
                current_app.logger.error("Chat stream error: %s", exc)
                yield "\n\nAn unexpected error occurred during synthesis. Please retry your question."
            finally:
                if is_leader:
                    ctx.request_dedup.cleanup(norm_query)

        return current_app.response_class(stream_with_context(generate()), mimetype=STREAM_MIME)

    @app.post("/api/chat/telemetry")
    def telemetry():
        return ("", TELEMETRY_NO_CONTENT)

    @app.route("/api/roadmap", methods=["GET", "POST", "OPTIONS"])
    def api_roadmap():
        """Build a staged learning roadmap from the concept graph."""
        body = request.get_json(silent=True) if request.method == "POST" else None
        topic = str((body or {}).get("topic") or request.args.get("topic") or "").strip()
        if not topic:
            return jsonify({"error": "A topic is required to build a roadmap."}), 400
        result = build_roadmap(ctx.engine.graph, topic)
        if result.get("error"):
            return jsonify(result), 404
        return jsonify(result)

    @app.route("/api/quiz", methods=["GET", "POST", "OPTIONS"])
    def api_quiz():
        """Build a short practice quiz from the concept graph."""
        body = request.get_json(silent=True) if request.method == "POST" else None
        topic = str((body or {}).get("topic") or request.args.get("topic") or "").strip()
        if not topic:
            return jsonify({"error": "A topic is required to build a quiz."}), 400
        result = build_quiz(ctx.engine, topic)
        if result.get("error"):
            return jsonify(result), 404
        return jsonify(result)
