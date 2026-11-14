"""Chat, diagnostics, roadmap and quiz routes.

One concern: the student-facing query pipeline, grounded streaming synthesis,
the adaptive diagnostic QnA flow, and the roadmap/quiz builders.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import re
import time
from uuid import UUID

from engine.reply_templates import list_reply_templates, valid_reply_template_id
from flask import Flask, current_app, jsonify, request
from host_roadmap import build_quiz, build_roadmap

from ..context import AppContext
from ..conversation import contextual_query
from ..research_chat import enrich_with_research
from ..research_run_chat import is_research_request, research_chat_reply

# Query hygiene: strip null bytes and ASCII control characters, keep whitespace.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_QUERY_CHARS = 500
MAX_PREVIOUS_ANSWER_CHARS = 800
STREAM_MIME = "text/plain; charset=utf-8"
STREAM_MARKER = "\n[STREAM_START]\n"
TELEMETRY_NO_CONTENT = 204


def _format_reset_time(reset_at: object, retry_after: int) -> str:
    """Format the rolling-window reset timestamp as ``HH:MM UTC``."""
    if reset_at:
        try:
            dt = datetime.fromisoformat(str(reset_at).replace("Z", "+00:00"))
            return dt.astimezone(UTC).strftime("%H:%M UTC")
        except ValueError:
            pass
    fallback_dt = datetime.now(UTC) + timedelta(seconds=max(1, retry_after))
    return fallback_dt.strftime("%H:%M UTC")


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
    run_id_arg = str(body.get("research_run_id") or body.get("run_id") or "").strip() or None
    if not run_id_arg and not is_research_request(query, False):
        return None
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
            run_id_arg,
        )
    except (ImportError, OSError, RuntimeError):
        current_app.logger.exception("Research run chat unavailable")
        return None
    if reply is None:
        return None
    run_id = reply.get("run_id")
    run_data = reply.get("run") or {}
    papers = run_data.get("papers", [])
    links = [
        {"evidence_id": f"R{i}", "title": p["title"], "url": url}
        for i, p in enumerate(papers, 1)
        if (url := (f"https://doi.org/{p['doi']}" if p.get("doi") else p.get("url")))
    ]
    topic_label = str(run_data.get("topic") or "Research Collection")
    anchor_concept = {
        "id": f"research_topic:{run_id or 'collection'}",
        "label": topic_label,
        "name": topic_label,
        "summary": f"{len(papers)} collected scholarly papers (newest-first, no quality ranking).",
        "concept_type": "research_collection",
        "difficulty": "collection",
    }
    related_concepts = [
        {
            "id": p.get("paper_id") or f"paper_{i}",
            "label": (p.get("title") or "Untitled")[:64],
            "name": p.get("title") or "Untitled",
            "summary": f"{p.get('year') or ''} · {p.get('venue') or p.get('source') or 'Scholarly source'}",
            "concept_type": "research_paper",
            "difficulty": str(p.get("year") or "paper"),
            "url": f"https://doi.org/{p['doi']}" if p.get("doi") else p.get("url"),
        }
        for i, p in enumerate(papers[:8], 1)
    ]
    research_entities = []
    seen_entities: set[str] = set()
    research_edges = []
    for p in papers[:8]:
        pid = p.get("paper_id") or p.get("title") or ""
        if pid:
            research_edges.append({"from": anchor_concept["id"], "to": pid, "relation": "HAS_PAPER"})
        for author in (p.get("authors") or [])[:2]:
            name = str(author.get("name") if isinstance(author, dict) else author).strip()
            if name and f"author:{name}" not in seen_entities and len(research_entities) < 8:
                seen_entities.add(f"author:{name}")
                research_entities.append({
                    "id": f"author:{name}",
                    "label": name,
                    "name": name,
                    "summary": f"Author in {topic_label}",
                    "concept_type": "author",
                    "difficulty": "AUTHORED_BY",
                })
                research_edges.append({"from": pid, "to": f"author:{name}", "relation": "AUTHORED_BY"})
        venue = str(p.get("venue") or p.get("source") or "").strip()
        if venue and f"venue:{venue}" not in seen_entities and len(research_entities) < 8:
            seen_entities.add(f"venue:{venue}")
            research_entities.append({
                "id": f"venue:{venue}",
                "label": venue,
                "name": venue,
                "summary": f"Publication venue/source in {topic_label}",
                "concept_type": "venue",
                "difficulty": "PUBLISHED_IN",
            })
            research_edges.append({"from": pid, "to": f"venue:{venue}", "relation": "PUBLISHED_IN"})

    payload = {
        "route": "RESEARCH_EVIDENCE",
        "contract": "RESEARCH_EVIDENCE",
        "routing": {"route": "RESEARCH_EVIDENCE", "reason": "research_run_snapshot"},
        "render_rule": "source_evidence",
        "hide_graph": False,
        "graph_mode": "research",
        "research_run_id": run_id,
        "anchor_concept": anchor_concept,
        "related_concepts": related_concepts,
        "prerequisites": [],
        "unlocks": [],
        "research_graph": {
            "entities": research_entities,
            "edges": research_edges,
        },
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

        principal = getattr(request, "archipelago_principal", None)
        if principal and principal.get("id") and principal.get("role") == "student":
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
                retry_after = int(quota.get("retry_after") or 1)
                reset_at = quota.get("reset_at")
                reset_label = _format_reset_time(reset_at, retry_after)
                response = jsonify(
                    {
                        "error": "query_limit",
                        "detail": (
                            f"Hourly chat limit reached (10/10). "
                            f"You can ask another question after {reset_label}."
                        ),
                        "used": quota.get("used", 10),
                        "limit": quota.get("limit", 10),
                        "remaining": quota.get("remaining", 0),
                        "retry_after": retry_after,
                        "reset_at": reset_at,
                    }
                )
                response.status_code = 429
                response.headers["Retry-After"] = str(retry_after)
                return response
            request.archipelago_quota = quota  # type: ignore[attr-defined]

        t_req_start = time.perf_counter()
        history = body.get("history")
        research = _research_run_reply(body, query, history)
        t_after_research = time.perf_counter()
        if research is not None:
            current_app.logger.info(
                "[CHAT_TIMING] route=RESEARCH_EVIDENCE research_ms=%.1f total_ms=%.1f",
                (t_after_research - t_req_start) * 1000,
                (t_after_research - t_req_start) * 1000,
            )
            response = current_app.response_class(research, mimetype=STREAM_MIME)
            response.headers["Cache-Control"] = "no-store"
            return response
        resolved_query = contextual_query(query, history)
        try:
            t_eng_start = time.perf_counter()
            prepared = ctx.engine.answer(resolved_query)
            t_eng_end = time.perf_counter()
            prepared = enrich_with_research(prepared, resolved_query)
            t_enrich_end = time.perf_counter()
        except Exception:
            current_app.logger.exception("Unable to prepare chat response")
            return jsonify({"error": "chat_unavailable"}), 503
        custom_reply = reply_detail == "expanded" or bool(template_id)

        previous_answer = ""
        if isinstance(history, list):
            for msg in reversed(history):
                if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
                    previous_answer = str(msg.get("content", ""))[:MAX_PREVIOUS_ANSWER_CHARS]
                    break

        ctx.cache_metrics.record_request()
        # Every chat request gets its own retrieval and provider stream, even
        # when an identical question is submitted at the same time.
        ctx.cache_metrics.record_miss()

        logger = current_app.logger

        def generate():
            ttft_ms = None
            try:
                if prepared.get("research_overlay") and not custom_reply:
                    yield json.dumps(prepared["payload"]) + STREAM_MARKER
                    ttft_ms = (time.perf_counter() - t_req_start) * 1000
                    yield prepared["text"]
                else:
                    options = {"previous_answer": previous_answer, "prepared": prepared}
                    if template_id:
                        options["reply_template_id"] = template_id
                    if reply_detail == "expanded":
                        options["reply_detail"] = "expanded"
                    for chunk in ctx.engine.stream_chat(resolved_query, **options):
                        if ttft_ms is None and STREAM_MARKER not in chunk:
                            ttft_ms = (time.perf_counter() - t_req_start) * 1000
                        yield chunk
            except Exception as exc:
                logger.error("Chat stream error: %s", exc)
                yield "\n\nAn unexpected error occurred during synthesis. Please retry your question."
            finally:
                t_end = time.perf_counter()
                logger.info(
                    "[CHAT_TIMING] route=%s research_ms=%.1f engine_ms=%.1f enrich_ms=%.1f ttft_ms=%.1f total_ms=%.1f",
                    prepared.get("route"),
                    (t_after_research - t_req_start) * 1000,
                    (t_eng_end - t_eng_start) * 1000,
                    (t_enrich_end - t_eng_end) * 1000,
                    ttft_ms if ttft_ms is not None else (t_end - t_req_start) * 1000,
                    (t_end - t_req_start) * 1000,
                )

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
