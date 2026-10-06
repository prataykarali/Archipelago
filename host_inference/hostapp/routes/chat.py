"""Chat, diagnostics, roadmap and quiz routes.

One concern: the student-facing query pipeline — cache lookup, request
deduplication, grounded streaming synthesis, the adaptive diagnostic QnA flow,
and the roadmap/quiz builders.  AI calls are minimised per doc 03: a cache hit
or an in-flight duplicate never reaches the model.
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
PRIVATE_QUERY = re.compile(
    r"\b(?:my|mine|me|our|ours|i|we|student\s+id|password|token|account|"
    r"grades?|marks?|enrolment|enrollment)\b|@|\b\d{8,}\b",
    re.IGNORECASE,
)
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
        # A login proves access but does not make a public concept question
        # personal. Never share answers that depend on learner state or carry
        # identifiers, credentials, or first-person context in the query.
        personal = bool(
            any(body.get(key) for key in ("session_id", "mastery", "learning_state", "preference"))
            or PRIVATE_QUERY.search(query)
        )
        cacheable = not personal and not DIAG_RE.search(query) and not INGEST_RE.search(query)
        norm_query = (
            ctx.cache_service.normalize_query(query) if cacheable else secrets.token_urlsafe(24)
        )

        # 1. Response cache (Doc 03 Section 3: Cache HIT) — no AI call.
        cached_entry = ctx.cache_service.get_cached_response(query) if cacheable else None
        if cached_entry:
            ctx.cache_metrics.record_hit(tokens_saved=TOKENS_SAVED_PER_HIT)
            cached_response_text = str(cached_entry.get("response") or "")

            def generate_cached():
                # A cached stream already carries its metadata frame, so replay
                # it verbatim and the in-chat graph survives the cache.
                if (
                    cached_response_text.startswith("{")
                    and STREAM_MARKER.strip() in cached_response_text
                ):
                    prefix, answer = cached_response_text.split(STREAM_MARKER, 1)
                    try:
                        frame = json.loads(prefix)
                        from engine.withdrawal import NEUTRAL_NOTICE, withdrawn_documents

                        retired = withdrawn_documents()
                        if any(c.get("doc_id") in retired for c in frame.get("citations", [])):
                            frame["withdrawn_notice"] = NEUTRAL_NOTICE
                            frame["text_override"] = NEUTRAL_NOTICE
                            frame["citations"] = [
                                c
                                for c in frame.get("citations", [])
                                if c.get("doc_id") not in retired
                            ]
                            answer = NEUTRAL_NOTICE
                        frame["cache"] = {"hit": True, "shared": True}
                        yield json.dumps(frame) + STREAM_MARKER + answer
                    except (ValueError, TypeError):
                        yield cached_response_text
                    return
                sources = cached_entry.get("sources") or []
                payload = {
                    "anchor_concept": (cached_entry.get("graph_data") or {}).get("target_id"),
                    "prerequisites": [],
                    "unlocks": [],
                    "related_concepts": [],
                    "citations": sources,
                    "graph_data": cached_entry.get("graph_data"),
                    "roadmap": cached_entry.get("roadmap_data"),
                    "model": {"provider": "cache", "model": "ai_response_cache"},
                    "logs": [
                        {
                            "step": "Supabase Cache",
                            "status": "Hit",
                            "details": f"Returned from cache (hit #{cached_entry.get('hit_count', 1)}). Zero LLM calls made.",
                        }
                    ],
                }
                # A cache entry written before a source was withdrawn still
                # carries that source's citation. Without this, replaying it
                # would resurrect an unciteable reference with no warning —
                # the exact failure the lifecycle ledger exists to prevent.
                notice = _withdrawn_notice(sources)
                if notice:
                    payload["withdrawn_notice"] = notice
                    payload["text_override"] = notice
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
                        yield from wait_result
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

                if collected_chunks and cacheable:
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
