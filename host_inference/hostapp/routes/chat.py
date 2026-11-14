"""Chat, diagnostics, roadmap and quiz routes.

One concern: the student-facing query pipeline, grounded streaming synthesis,
the adaptive diagnostic QnA flow, and the roadmap/quiz builders.
"""

from __future__ import annotations

import json
import re
from uuid import UUID

from engine.answer import POLISHABLE_ROUTES
from engine.llm import provider_config
from engine.reply_templates import list_reply_templates, valid_reply_template_id
from flask import Flask, current_app, jsonify, request
from host_roadmap import build_quiz, build_roadmap

from ..context import AppContext
from ..conversation import contextual_query
from ..research_chat import enrich_with_research
from ..research_run_chat import research_chat_reply

# Query hygiene: strip null bytes and ASCII control characters, keep whitespace.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_QUERY_CHARS = 500
MAX_PREVIOUS_ANSWER_CHARS = 800
STREAM_MIME = "text/plain; charset=utf-8"
STREAM_MARKER = "\n[STREAM_START]\n"
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


def _research_run_reply(body: dict, query: str, history: object) -> str | None:
    """Answer paper-collection questions from the caller's stored S5 run, or defer."""
    principal = getattr(request, "archipelago_principal", None)
    if not principal or not principal.get("id"):
        return None
    try:
        from archipelago.scholarly.intelligence.storage import hosted_store

        reply = research_chat_reply(
            query,
            history if isinstance(history, list) else None,
            str(principal["id"]),
            hosted_store(),
            str(body.get("research_run_id") or body.get("run_id") or "") or None,
        )
    except (ImportError, OSError, RuntimeError):
        current_app.logger.exception("Research run chat unavailable")
        return None
    if reply is None:
        return None
    run_id = reply.get("run_id")
    links = [
        {"evidence_id": f"R{i}", "title": p["title"], "url": url}
        for i, p in enumerate((reply.get("run") or {}).get("papers", []), 1)
        if (url := (f"https://doi.org/{p['doi']}" if p.get("doi") else p.get("url")))
    ]
    payload = {
        "route": "RESEARCH_EVIDENCE",
        "contract": "RESEARCH_EVIDENCE",
        "routing": {"route": "RESEARCH_EVIDENCE", "reason": "research_run_snapshot"},
        "render_rule": "source_evidence",
        "hide_graph": True,
        "research_run_id": run_id,
        "citations": links,
    }
    return json.dumps(payload) + STREAM_MARKER + reply["text"]


def register(app: Flask, ctx: AppContext) -> None:
    """Register chat-family routes on ``app``."""

    @app.get("/api/chat/quota")
    def chat_quota():
        principal = getattr(request, "archipelago_principal", None)
        if principal is None:
            return jsonify({"error": "unauthorized"}), 401
        if principal["role"] != "student":
            return jsonify({"unrestricted": True, "role": principal["role"]})
        try:
            return jsonify(ctx.limiter.quota_status(principal["id"]))
        except Exception:
            current_app.logger.exception("Unable to read account quota")
            return jsonify({"error": "quota_unavailable"}), 503

    @app.get("/api/reply-templates")
    def chat_reply_templates():
        """List the packaged response formats for the chat UI."""
        return jsonify({"templates": list_reply_templates()})

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

        template_id = str(body.get("reply_template_id") or "").strip()
        if template_id and not valid_reply_template_id(template_id):
            return jsonify({"error": "invalid_reply_template_id"}), 400
        reply_detail = body.get("reply_detail")
        if reply_detail not in (None, "standard", "expanded"):
            return jsonify({"error": "invalid_reply_detail"}), 400

        history = body.get("history")
        research = _research_run_reply(body, query, history)
        if research is not None:
            response = current_app.response_class(research, mimetype=STREAM_MIME)
            response.headers["Cache-Control"] = "no-store"
            return response
        resolved_query = contextual_query(query, history)
        try:
            prepared = ctx.engine.answer(resolved_query)
            prepared = enrich_with_research(prepared, resolved_query)
        except Exception:
            current_app.logger.exception("Unable to prepare chat response")
            return jsonify({"error": "chat_unavailable"}), 503
        principal = getattr(request, "archipelago_principal", None)
        custom_reply = reply_detail == "expanded" or bool(template_id)
        uses_ai = provider_config() is not None and (
            (prepared["route"] in POLISHABLE_ROUTES and not prepared.get("research_overlay"))
            or (prepared.get("research_overlay") and custom_reply)
        )
        if uses_ai and principal and principal.get("id") and principal["role"] == "student":
            request_id = body.get("request_id") or ""
            if request_id:
                try:
                    request_id = str(UUID(str(request_id)))
                except ValueError:
                    return jsonify({"error": "invalid_request_id"}), 400
            try:
                limited, quota = ctx.limiter.check_daily_chat(principal["id"], request_id)
            except Exception:
                current_app.logger.exception("Unable to update account quota")
                return jsonify({"error": "quota_unavailable"}), 503
            if limited:
                if quota.get("limit_reason") == "duplicate":
                    return jsonify(
                        {
                            "error": "duplicate_request",
                            "detail": "This AI request was already submitted.",
                        }
                    ), 409
                response = jsonify(
                    {
                        "error": "query_limit",
                        "detail": "AI queries are paused. Your saved conversations remain available.",
                        "remaining": quota["remaining"],
                        "retry_after": quota["retry_after"],
                    }
                )
                response.status_code = 429
                response.headers["Retry-After"] = str(quota["retry_after"])
                return response
            request.archipelago_quota = quota  # type: ignore[attr-defined]

        previous_answer = ""
        if isinstance(history, list) and len(history) >= 2:
            previous_user, previous_assistant = history[-2:]
            if (
                isinstance(previous_user, dict)
                and isinstance(previous_assistant, dict)
                and previous_user.get("role") == "user"
                and previous_assistant.get("role") == "assistant"
                and str(previous_user.get("content", "")).strip().casefold() == query.casefold()
            ):
                previous_answer = str(previous_assistant.get("content", ""))[
                    :MAX_PREVIOUS_ANSWER_CHARS
                ]

        ctx.cache_metrics.record_request()
        # Every chat request gets its own retrieval and provider stream, even
        # when an identical question is submitted at the same time.
        ctx.cache_metrics.record_miss()

        def generate():
            try:
                if prepared.get("research_overlay") and not custom_reply:
                    yield json.dumps(prepared["payload"]) + STREAM_MARKER
                    yield prepared["text"]
                else:
                    options = {"previous_answer": previous_answer, "prepared": prepared}
                    if template_id:
                        options["reply_template_id"] = template_id
                    if reply_detail == "expanded":
                        options["reply_detail"] = "expanded"
                    yield from ctx.engine.stream_chat(resolved_query, **options)
            except Exception as exc:
                current_app.logger.error("Chat stream error: %s", exc)
                yield "\n\nAn unexpected error occurred during synthesis. Please retry your question."

        response = current_app.response_class(generate(), mimetype=STREAM_MIME)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/chat/diagnostic-mcqs")
    def diagnostic_mcqs():
        concept = request.args.get("concept") or ""
        principal = getattr(request, "archipelago_principal", None)
        if principal:
            saved = ctx.limiter.completed_quiz(principal["id"], concept)
            if saved:
                return jsonify(
                    {
                        "success": True,
                        "completed": True,
                        "evaluation": saved.get("evaluation"),
                        "target_concept": concept,
                    }
                )
        return jsonify(ctx.engine.diagnostic_payload(concept))

    @app.post("/api/chat/adaptive-step")
    def adaptive_step():
        body = request.get_json(silent=True) or {}
        principal = getattr(request, "archipelago_principal", None)
        target = str(body.get("target_concept") or "")
        if principal and target:
            saved = ctx.limiter.completed_quiz(principal["id"], target)
            if saved:
                return jsonify(saved)
        result = ctx.engine.adaptive_step(body)
        if principal and target and result.get("completed"):
            ctx.limiter.save_completed_quiz(principal["id"], target, result)
        return jsonify(result)

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
