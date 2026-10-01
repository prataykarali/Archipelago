"""Chat, diagnostics, roadmap and quiz routes.

One concern: the student-facing query pipeline — cache lookup, request
deduplication, grounded streaming synthesis, the adaptive diagnostic QnA flow,
and the roadmap/quiz builders.  AI calls are minimised per doc 03: a cache hit
or an in-flight duplicate never reaches the model.
"""
from __future__ import annotations

import json
import re

from flask import Flask, current_app, jsonify, request

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


def register(app: Flask, ctx: AppContext) -> None:
    """Register chat-family routes on ``app``."""

    @app.post("/api/chat")
    def api_chat():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "invalid_payload", "detail": "Request body must be a JSON object"}), 400
        raw_query = str(body.get("query") or "")
        query = CONTROL_CHARS.sub("", raw_query).strip()
        if len(query) > MAX_QUERY_CHARS:
            return jsonify({"error": "Query exceeds maximum limit of 500 characters"}), 400
        if not query:
            return jsonify({"error": "Query cannot be empty"}), 400

        ctx.cache_metrics.record_request()
        norm_query = ctx.cache_service.normalize_query(query)

        # 1. Response cache (Doc 03 Section 3: Cache HIT) — no AI call.
        cached_entry = ctx.cache_service.get_cached_response(query)
        if cached_entry:
            ctx.cache_metrics.record_hit(tokens_saved=TOKENS_SAVED_PER_HIT)
            cached_response_text = str(cached_entry.get("response") or "")

            def generate_cached():
                # A cached stream already carries its metadata frame, so replay
                # it verbatim and the in-chat graph survives the cache.
                if cached_response_text.startswith("{") and STREAM_MARKER.strip() in cached_response_text:
                    yield cached_response_text
                    return
                payload = {
                    "anchor_concept": (cached_entry.get("graph_data") or {}).get("target_id"),
                    "prerequisites": [],
                    "unlocks": [],
                    "related_concepts": [],
                    "citations": cached_entry.get("sources") or [],
                    "graph_data": cached_entry.get("graph_data"),
                    "roadmap": cached_entry.get("roadmap_data"),
                    "model": {"provider": "cache", "model": "ai_response_cache"},
                    "logs": [{
                        "step": "Supabase Cache",
                        "status": "Hit",
                        "details": f"Returned from cache (hit #{cached_entry.get('hit_count', 1)}). Zero LLM calls made.",
                    }],
                }
                yield json.dumps(payload) + STREAM_MARKER
                yield cached_response_text

            return current_app.response_class(generate_cached(), mimetype=STREAM_MIME)

        # 2. De-duplicate concurrent identical queries (Doc 03 Section 8).
        if ctx.request_dedup.is_in_flight(norm_query):
            wait_result = ctx.request_dedup.wait(norm_query)
            if wait_result is not None:
                ctx.cache_metrics.record_dedup(tokens_saved=TOKENS_SAVED_PER_HIT)

                def generate_dedup():
                    if isinstance(wait_result, list):
                        for chunk in wait_result:
                            yield chunk
                    else:
                        yield str(wait_result)

                return current_app.response_class(generate_dedup(), mimetype=STREAM_MIME)

        # 3. Cache MISS — real retrieval + inference (Doc 03 Section 4).
        ctx.cache_metrics.record_miss()
        is_leader = ctx.request_dedup.start_flight(norm_query)

        def generate():
            collected_chunks = []
            try:
                for chunk in ctx.engine.stream_chat(query):
                    collected_chunks.append(chunk)
                    yield chunk

                if collected_chunks:
                    meta = _metadata_frame(collected_chunks)
                    ctx.cache_service.cache_response(
                        query=query,
                        response_text="".join(collected_chunks),
                        sources=meta.get("citations", []),
                        graph_data=meta,
                        roadmap_data=meta.get("roadmap", []),
                    )
                    if is_leader:
                        ctx.request_dedup.complete(norm_query, collected_chunks)
            except Exception as exc:
                current_app.logger.error("Chat stream error: %s", exc)
                yield "\n\nAn unexpected error occurred during synthesis. Please retry your question."
            finally:
                if is_leader:
                    ctx.request_dedup.cleanup(norm_query)

        return current_app.response_class(generate(), mimetype=STREAM_MIME)

    @app.get("/api/chat/diagnostic-mcqs")
    def diagnostic_mcqs():
        concept = request.args.get("concept") or ""
        return jsonify(ctx.engine.diagnostic_payload(concept))

    @app.post("/api/chat/adaptive-step")
    def adaptive_step():
        body = request.get_json(silent=True) or {}
        return jsonify(ctx.engine.adaptive_step(body))

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
