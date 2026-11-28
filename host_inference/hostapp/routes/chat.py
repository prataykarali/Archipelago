"""Chat, diagnostics, roadmap and quiz routes.

One concern: the student-facing query pipeline, grounded streaming synthesis,
the adaptive diagnostic QnA flow, and the roadmap/quiz builders.
"""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime, timedelta
import json
import re
import time
from uuid import UUID, uuid4

from engine.access_profile import active_access_profile, is_open_access_profile
from engine.citation_format import (
    has_verified_full_text_citations,
    sanitize_citations,
)
from engine.citations import (
    assign_canonical_citations,
    infer_synthesis_mode,
    validate_response_citations,
)
from engine.evidence_export import build_evidence_export, render_evidence_markdown
from engine.llm import provider_config as provider_config
from engine.reply_templates import (
    list_reply_templates,
    select_reply_template,
    valid_reply_template_id,
)
from engine.suggestions import (
    DEFAULT_SUGGESTION_COUNT,
    build_suggestions_payload,
)
from flask import Flask, current_app, jsonify, request
from host_roadmap import build_quiz, build_roadmap

from ..context import AppContext
from ..conversation import contextual_query
from ..research_chat import enrich_with_research
from ..research_run_chat import is_research_request, research_chat_reply
from ..runtime_state import runtime_release_sha
from ..user_traffic import clear_user_traffic, record_user_action

# Query hygiene: strip null bytes and ASCII control characters, keep whitespace.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_QUERY_CHARS = 500
MAX_PREVIOUS_ANSWER_CHARS = 800
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CONTENT_CHARS = 2000
MAX_CONCEPT_CHARS = 200
STREAM_MIME = "text/plain; charset=utf-8"
STREAM_MARKER = "\n[STREAM_START]\n"
STREAM_DONE_MARKER = "[STREAM_DONE]"
TELEMETRY_NO_CONTENT = 204
CHAT_REQUEST_DEADLINE_SECONDS = 45.0


def _sanitize_history(raw_history: object) -> list[dict[str, str]]:
    """Bound conversation history length and strip control/protocol markers."""
    if not isinstance(raw_history, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in raw_history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = CONTROL_CHARS.sub("", str(item.get("content") or ""))
        content = content.replace("[STREAM_START]", "").replace(STREAM_DONE_MARKER, "").strip()
        if content:
            cleaned.append({"role": role, "content": content[:MAX_HISTORY_CONTENT_CHARS]})
    return cleaned


_STUDY_PLAN_ASK_RE = re.compile(
    r"\b(reading\s+order|study\s+plan|roadmap|learning\s+path|prerequisite)\b",
    re.I,
)
_RESEARCH_ENRICH_CUE_RE = re.compile(
    r"\b(research|papers?|publications?|studies|arxiv|doi|saved|ingested|collected|topics?|subjects?|research\s+areas?|literature)\b",
    re.I,
)
_CONCEPTUAL_ROUTES = frozenset(
    {
        "GRAPH_SYNTHESIS",
        "MULTI_CONCEPT",
        "GENERAL_EXPLANATION",
        "CROSS_DOMAIN",
        "RELATION",
        "DISCONNECTED",
        "RESEARCH_TOPIC",
    }
)
_COMPARE_CUE_RE = re.compile(r"\b(compare|versus|vs\.?|difference\s+between)\b", re.I)


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


_RESEARCH_STAFF_ROLES = frozenset({"faculty", "librarian", "administrator"})


def _research_run_reply(body: dict, query: str, history: object) -> str | None:
    """Answer paper-collection questions from the caller's stored S5 run, or defer."""
    run_id_arg = str(body.get("research_run_id") or body.get("run_id") or "").strip() or None
    principal = getattr(request, "archipelago_principal", None)
    if not principal or not principal.get("id"):
        return None
    if not run_id_arg and re.search(
        r"\b(books?|library|opac|koha|holdings?|catalog)\b", query, re.I
    ):
        return None
    if not run_id_arg and not is_research_request(query, True):
        return None
    if str(principal.get("role") or "").lower() not in _RESEARCH_STAFF_ROLES:
        denied_payload = {
            "route": "RESEARCH_RESTRICTED",
            "contract": "GUARDRAIL_INTERCEPT",
            "render_graph": False,
            "citations": [],
        }
        denied_text = (
            "Research Intelligence collections, saved runs, and topic monitors are restricted to "
            "**faculty and librarian** accounts. As a student, you can still ask about academic "
            "concepts, OPAC book availability, journal issue counts, and college publications."
        )
        return json.dumps(denied_payload) + STREAM_MARKER + denied_text + "\n[STREAM_DONE]\n"
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
            research_edges.append(
                {"from": anchor_concept["id"], "to": pid, "relation": "HAS_PAPER"}
            )
        for author in (p.get("authors") or [])[:2]:
            name = str(author.get("name") if isinstance(author, dict) else author).strip()
            if name and f"author:{name}" not in seen_entities and len(research_entities) < 8:
                seen_entities.add(f"author:{name}")
                research_entities.append(
                    {
                        "id": f"author:{name}",
                        "label": name,
                        "name": name,
                        "summary": f"Author in {topic_label}",
                        "concept_type": "author",
                        "difficulty": "AUTHORED_BY",
                    }
                )
                research_edges.append(
                    {"from": pid, "to": f"author:{name}", "relation": "AUTHORED_BY"}
                )
        venue = str(p.get("venue") or p.get("source") or "").strip()
        if venue and f"venue:{venue}" not in seen_entities and len(research_entities) < 8:
            seen_entities.add(f"venue:{venue}")
            research_entities.append(
                {
                    "id": f"venue:{venue}",
                    "label": venue,
                    "name": venue,
                    "summary": f"Publication venue/source in {topic_label}",
                    "concept_type": "venue",
                    "difficulty": "PUBLISHED_IN",
                }
            )
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

    @app.get("/api/chat/suggestions")
    def chat_suggestions():
        """Return dynamic numbered knowledge areas and shuffled starter questions."""
        raw_count = request.args.get("count")
        try:
            count = int(raw_count) if raw_count is not None else DEFAULT_SUGGESTION_COUNT
        except ValueError:
            count = DEFAULT_SUGGESTION_COUNT
        raw_seed = request.args.get("seed")
        seed: int | None = None
        if raw_seed is not None and raw_seed.strip():
            try:
                seed = int(raw_seed.strip())
            except ValueError:
                seed = None
        graph = getattr(ctx.engine, "graph", None)
        return jsonify(build_suggestions_payload(graph, count=count, seed=seed))

    @app.post("/api/chat/export")
    def chat_export_evidence():
        """Build a credential-scrubbed per-query evidence export bundle."""
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(
                {"error": "invalid_payload", "detail": "Request body must be a JSON object"}
            ), 400
        raw_query = CONTROL_CHARS.sub("", str(body.get("query") or "")).strip()
        raw_answer = CONTROL_CHARS.sub("", str(body.get("answer") or "")).strip()
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        bundle = build_evidence_export(raw_query, raw_answer, metadata)
        fmt = str(body.get("format") or "json").strip().lower()
        if fmt == "markdown":
            resp = jsonify({"markdown": render_evidence_markdown(bundle), "bundle": bundle})
        else:
            resp = jsonify(bundle)
        resp.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
        return resp

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
        record_user_action("chat_query", query, session_id=str(body.get("session_id") or ""))

        template_id = str(body.get("reply_template_id") or "").strip()
        if template_id and not valid_reply_template_id(template_id):
            return jsonify({"error": "invalid_reply_template_id"}), 400
        reply_detail = body.get("reply_detail")
        if reply_detail not in (None, "standard", "expanded"):
            return jsonify({"error": "invalid_reply_detail"}), 400

        prior_auth_ms = getattr(request, "archipelago_auth_ms", None)
        quota_ms: float | None = None
        principal = getattr(request, "archipelago_principal", None)
        raw_request_id = str(body.get("request_id") or "").strip()
        if raw_request_id:
            try:
                request_id = str(UUID(raw_request_id))
            except ValueError:
                return jsonify({"error": "invalid_request_id"}), 400
        else:
            request_id = str(uuid4())
        if principal and principal.get("id") and principal.get("role") == "student":
            t_quota_start = time.perf_counter()
            try:
                limited, quota = ctx.limiter.check_daily_chat(principal["id"], request_id)
            except Exception:
                current_app.logger.exception("Unable to update account quota")
                return jsonify({"error": "quota_unavailable"}), 503
            quota_ms = round((time.perf_counter() - t_quota_start) * 1000, 1)
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
                q_limit = int(quota.get("limit") or 10)
                q_used = int(quota.get("used") or q_limit)
                response = jsonify(
                    {
                        "error": "query_limit",
                        "detail": (
                            f"Hourly chat limit reached ({q_used}/{q_limit}). "
                            f"You can ask another question after {reset_label}."
                        ),
                        "used": q_used,
                        "limit": q_limit,
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
        history = _sanitize_history(body.get("history"))
        research = _research_run_reply(body, query, history)
        t_after_research = time.perf_counter()
        if research is not None:
            current_app.logger.info(
                "[CHAT_TIMING] route=RESEARCH_EVIDENCE research_ms=%.1f total_ms=%.1f",
                (t_after_research - t_req_start) * 1000,
                (t_after_research - t_req_start) * 1000,
            )
            response = current_app.response_class(research, mimetype=STREAM_MIME)
            response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
            response.headers["Vary"] = "Authorization, Cookie"
            return response
        t_res_start = time.perf_counter()
        resolved_query = contextual_query(query, history)
        query_resolution_ms = round((time.perf_counter() - t_res_start) * 1000, 1)

        graph_version = str(
            getattr(getattr(ctx.engine, "graph", None), "graph_version", "unknown") or "unknown"
        )
        cp_info = getattr(getattr(ctx.engine, "catalog", None), "candidate_passages_info", None)
        corpus_version = str(
            (cp_info.get("sha256")[:12] if isinstance(cp_info, dict) and cp_info.get("sha256") else None)
            or getattr(getattr(ctx.engine, "graph", None), "corpus_source", None)
            or "bundled"
        )
        release_sha = runtime_release_sha()
        access_profile = active_access_profile()
        tenant_scope = (
            f"user:{principal.get('id')}:role:{principal.get('role')}"
            if isinstance(principal, dict) and principal.get("id")
            else f"open:{access_profile}"
        )
        effective_detail = str(reply_detail or "standard")
        cache_eligible = not history and getattr(ctx, "cache_service", None) is not None and callable(
            getattr(ctx.cache_service, "build_versioned_key", None)
        )
        cache_key = (
            ctx.cache_service.build_versioned_key(
                resolved_query,
                tenant_scope=tenant_scope,
                access_profile=access_profile,
                graph_version=graph_version,
                corpus_version=corpus_version,
                release_sha=release_sha,
                reply_detail=effective_detail,
                template_id=template_id,
            )
            if cache_eligible
            else ""
        )
        auth_ms: float | None = (
            round(
                (float(prior_auth_ms) if isinstance(prior_auth_ms, (int, float)) else 0.0)
                + (float(quota_ms) if isinstance(quota_ms, (int, float)) else 0.0),
                1,
            )
            if (isinstance(prior_auth_ms, (int, float)) or isinstance(quota_ms, (int, float)))
            else None
        )

        if cache_key and callable(getattr(ctx.cache_service, "get_versioned_entry", None)):
            cached = ctx.cache_service.get_versioned_entry(cache_key)
            if isinstance(cached, dict) and cached.get("text") and isinstance(cached.get("metadata"), dict):
                cached_meta = dict(cached["metadata"])
                cached_citations = cached_meta.get("citations") or []
                if not _withdrawn_notice(cached_citations):
                    ctx.cache_metrics.record_request()
                    ctx.cache_metrics.record_hit()
                    total_hit_ms = round((time.perf_counter() - t_req_start) * 1000, 1)
                    hit_timings = {
                        "auth_ms": auth_ms,
                        "query_resolution_ms": query_resolution_ms,
                        "retrieval_ms": None,
                        "evidence_retrieval_ms": None,
                        "reranking_ms": None,
                        "provider_ttft_ms": None,
                        "visible_ttft_ms": total_hit_ms,
                        "ttft_visible_ms": total_hit_ms,
                        "ttft_ms": total_hit_ms,
                        "total_ms": total_hit_ms,
                    }
                    cached_meta["stage_timings_ms"] = hit_timings
                    hit_trace = dict(cached_meta.get("trace") or {})
                    hit_trace.update(
                        request_id=request_id,
                        release_sha=release_sha,
                        graph_version=graph_version,
                        graph_revision=graph_version,
                        corpus_version=corpus_version,
                        cache_status="hit",
                        completion_status="complete",
                        stream_status="complete",
                        stage_timings_ms=hit_timings,
                    )
                    cached_meta["trace"] = hit_trace
                    terminal_meta = {
                        "request_id": request_id,
                        "provider_status": "cached",
                        "fallback_reason": None,
                        "cache_status": "hit",
                        "stream_status": "complete",
                        "completion_status": "complete",
                        "auth_ms": auth_ms,
                        "query_resolution_ms": query_resolution_ms,
                        "retrieval_ms": None,
                        "evidence_retrieval_ms": None,
                        "reranking_ms": None,
                        "provider_ttft_ms": None,
                        "visible_ttft_ms": total_hit_ms,
                        "ttft_visible_ms": total_hit_ms,
                        "total_ms": total_hit_ms,
                    }
                    cached_body = (
                        json.dumps(cached_meta)
                        + STREAM_MARKER
                        + str(cached["text"])
                        + f"\n[STREAM_META:{json.dumps(terminal_meta)}]\n"
                        + "\n[STREAM_DONE]\n"
                    )
                    response = current_app.response_class(cached_body, mimetype=STREAM_MIME)
                    response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
                    response.headers["Vary"] = "Authorization, Cookie"
                    response.headers["X-Accel-Buffering"] = "no"
                    return response

        try:
            t_eng_start = time.perf_counter()
            answer_fn = getattr(ctx.engine, "answer", None)
            prepared = answer_fn(resolved_query) if callable(answer_fn) else {}
            t_eng_end = time.perf_counter()
            principal_role = str(
                (getattr(request, "archipelago_principal", None) or {}).get("role") or ""
            ).lower()
            is_research_staff = (
                principal_role in _RESEARCH_STAFF_ROLES
                or not getattr(ctx.auth, "required", lambda: True)()
            )
            should_enrich = (
                bool(prepared)
                and is_research_staff
                and (
                    prepared.get("route") in {"RESEARCH_TOPIC", "RESEARCH_UNVERIFIED"}
                    or bool(_RESEARCH_ENRICH_CUE_RE.search(query))
                )
            )
            if should_enrich:
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
        ctx.cache_metrics.record_miss()
        cache_status_label = "miss" if cache_key else ("bypass_history" if history else "miss_no_reuse")

        logger = current_app.logger

        def annotate_trace(metadata: dict, *, timing: dict[str, float | None]) -> None:
            """Attach measured execution facts without asserting claim entailment."""
            citations = metadata.get("citations") or []
            trace = metadata.setdefault("trace", {})
            if not isinstance(trace, dict):
                trace = {}
                metadata["trace"] = trace
            model = metadata.get("model") or {}
            cited_ids = sorted(
                {
                    str(
                        c.get("canonical_passage_id")
                        or c.get("passage_id")
                        or c.get("chunk_id")
                    )
                    for c in citations
                    if isinstance(c, dict)
                    and (
                        c.get("canonical_passage_id")
                        or c.get("passage_id")
                        or c.get("chunk_id")
                    )
                }
            )
            raw_retrieved = (
                prepared.get("retrieved_passage_ids")
                or metadata.get("retrieved_passage_ids")
                or []
            )
            retrieved_ids = sorted(
                {
                    str(pid)
                    for pid in list(raw_retrieved) + cited_ids
                    if pid
                }
            )
            synth_mode = metadata.get("synthesis_mode") or "unknown"
            trace.update(
                request_id=request_id,
                intent=prepared.get("route") or "unknown",
                synthesis_mode=synth_mode,
                generation_mode=synth_mode,
                provider=metadata.get("provider") or "deterministic",
                provider_status=metadata.get("provider_status"),
                fallback_reason=metadata.get("fallback_reason"),
                model=model.get("model") if isinstance(model, dict) else "",
                cache_status=cache_status_label,
                release_sha=release_sha,
                graph_version=graph_version,
                graph_revision=graph_version,
                corpus_version=corpus_version,
                completion_status=metadata.get("completion_status"),
                source_document_ids=sorted(
                    {
                        str(c.get("doc_id"))
                        for c in citations
                        if isinstance(c, dict) and c.get("doc_id")
                    }
                ),
                passage_ids=cited_ids,
                cited_passage_ids=cited_ids,
                retrieved_passage_ids=retrieved_ids,
                stage_timings_ms=timing,
            )

        def generate():
            ttft_ms = None
            ttft_visible_ms = None
            t_stream_start = None
            live_provider_active = False
            recorded_prov_ttft: float | None = None
            research_ms = round((t_after_research - t_req_start) * 1000, 1)
            engine_ms = round((t_eng_end - t_eng_start) * 1000, 1)
            ev_ms = prepared.get("evidence_retrieval_ms")
            enrich_ms = round((t_enrich_end - t_eng_end) * 1000, 1) if should_enrich else None
            request_deadline = t_req_start + CHAT_REQUEST_DEADLINE_SECONDS
            oa_only = is_open_access_profile()
            payload = dict(prepared.get("payload") or {})
            sanitized_initial = sanitize_citations(
                payload.get("citations"), open_access_only=oa_only
            )
            canonical_citations = assign_canonical_citations(sanitized_initial)
            payload["citations"] = canonical_citations
            payload["evidence_backed"] = has_verified_full_text_citations(canonical_citations)
            try:
                if prepared.get("research_overlay") and not custom_reply:
                    payload["synthesis_mode"] = infer_synthesis_mode(prepared, payload)
                    payload.setdefault("provider_status", "not_invoked")
                    payload.setdefault("fallback_reason", None)
                    ttft_ms = round((time.perf_counter() - t_req_start) * 1000, 1)
                    ttft_visible_ms = ttft_ms
                    payload["stage_timings_ms"] = {
                        "auth_ms": auth_ms,
                        "query_resolution_ms": query_resolution_ms,
                        "research_run_ms": research_ms,
                        "intent_and_graph_ms": engine_ms,
                        "retrieval_ms": ev_ms,
                        "evidence_retrieval_ms": ev_ms,
                        "reranking_ms": None,
                        "research_enrichment_ms": enrich_ms,
                        "provider_ttft_ms": None,
                        "visible_ttft_ms": ttft_visible_ms,
                        "ttft_visible_ms": ttft_visible_ms,
                        "ttft_ms": ttft_ms,
                        "total_ms": ttft_ms,
                    }
                    payload["completion_status"] = "complete"
                    annotate_trace(payload, timing=payload["stage_timings_ms"])
                    payload["trace"]["evidence_backed"] = payload["evidence_backed"]
                    yield json.dumps(payload) + STREAM_MARKER
                    clean_text, _removed = validate_response_citations(
                        str(prepared.get("text") or ""),
                        canonical_citations,
                    )
                    yield clean_text
                    total_now = round((time.perf_counter() - t_req_start) * 1000, 1)
                    yield (
                        "\n[STREAM_META:"
                        + json.dumps(
                            {
                                "request_id": request_id,
                                "provider_status": "not_invoked",
                                "fallback_reason": None,
                                "cache_status": cache_status_label,
                                "stream_status": "complete",
                                "completion_status": "complete",
                                "auth_ms": auth_ms,
                                "query_resolution_ms": query_resolution_ms,
                                "retrieval_ms": ev_ms,
                                "evidence_retrieval_ms": ev_ms,
                                "reranking_ms": None,
                                "visible_ttft_ms": ttft_visible_ms,
                                "ttft_visible_ms": ttft_visible_ms,
                                "provider_ttft_ms": None,
                                "total_ms": total_now,
                            }
                        )
                        + "]\n"
                    )
                else:
                    prepared_for_stream = dict(prepared)
                    prepared_for_stream["payload"] = payload
                    options = {
                        "previous_answer": previous_answer,
                        "prepared": prepared_for_stream,
                        "request_deadline": request_deadline,
                    }
                    if template_id:
                        options["reply_template_id"] = template_id
                    elif prepared.get(
                        "route"
                    ) in _CONCEPTUAL_ROUTES and not _STUDY_PLAN_ASK_RE.search(resolved_query):
                        auto_tpl = select_reply_template(
                            resolved_query, str(prepared.get("route") or "")
                        )
                        if auto_tpl.get("id") in {"RES-102", "RES-121"}:
                            options["reply_template_id"] = (
                                "RES-091" if _COMPARE_CUE_RE.search(resolved_query) else "RES-114"
                            )
                    if reply_detail == "expanded":
                        options["reply_detail"] = "expanded"
                    active_citations = canonical_citations
                    t_stream_start = time.perf_counter()
                    try:
                        stream_iter = ctx.engine.stream_chat(resolved_query, **options)
                    except TypeError:
                        options.pop("request_deadline", None)
                        try:
                            stream_iter = ctx.engine.stream_chat(resolved_query, **options)
                        except TypeError:
                            stream_iter = ctx.engine.stream_chat(resolved_query)
                    captured_meta: dict | None = None
                    captured_prose: list[str] = []
                    terminal_stream_status = "complete"
                    for chunk in stream_iter:
                        if STREAM_MARKER in chunk:
                            head, rest = chunk.split(STREAM_MARKER, 1)
                            try:
                                meta = json.loads(head)
                            except ValueError:
                                yield chunk
                                continue
                            raw_meta_cites = sanitize_citations(
                                meta.get("citations"), open_access_only=oa_only
                            )
                            meta_citations = assign_canonical_citations(raw_meta_cites)
                            meta["citations"] = meta_citations
                            active_citations = meta_citations
                            evidence_backed = has_verified_full_text_citations(meta_citations)
                            meta["evidence_backed"] = evidence_backed
                            if meta or prepared.get("synthesis_mode") or meta_citations:
                                meta["synthesis_mode"] = infer_synthesis_mode(prepared, meta)
                            now_ms = round((time.perf_counter() - t_req_start) * 1000, 1)
                            provider_name = str(meta.get("provider") or "").strip().lower()
                            live_provider = provider_name not in {
                                "",
                                "deterministic",
                                "unavailable",
                            }
                            live_provider_active = live_provider
                            prov_ttft = (
                                round((time.perf_counter() - t_stream_start) * 1000, 1)
                                if (live_provider and t_stream_start is not None)
                                else None
                            )
                            recorded_prov_ttft = prov_ttft
                            if meta:
                                meta["stage_timings_ms"] = {
                                    "auth_ms": auth_ms,
                                    "query_resolution_ms": query_resolution_ms,
                                    "research_run_ms": research_ms,
                                    "intent_and_graph_ms": engine_ms,
                                    "retrieval_ms": ev_ms,
                                    "evidence_retrieval_ms": ev_ms,
                                    "reranking_ms": None,
                                    "research_enrichment_ms": enrich_ms,
                                    "provider_ttft_ms": prov_ttft,
                                    "visible_ttft_ms": now_ms,
                                    "ttft_visible_ms": now_ms,
                                    "ttft_ms": now_ms,
                                    "total_ms": None,
                                }
                                annotate_trace(meta, timing=meta["stage_timings_ms"])
                                meta["trace"]["evidence_backed"] = evidence_backed
                                captured_meta = dict(meta)
                            yield json.dumps(meta) + STREAM_MARKER + rest
                            if rest:
                                captured_prose.append(rest)
                            continue
                        if "[STREAM_META:" in chunk:
                            try:
                                prefix, tail = chunk.split("[STREAM_META:", 1)
                                json_str, suffix = tail.split("]", 1)
                                tmeta = json.loads(json_str)
                                total_now = round((time.perf_counter() - t_req_start) * 1000, 1)
                                visible_now = (
                                    ttft_visible_ms if ttft_visible_ms is not None else total_now
                                )
                                terminal_stream_status = str(
                                    tmeta.get("stream_status") or "complete"
                                )
                                tmeta["request_id"] = request_id
                                tmeta["cache_status"] = cache_status_label
                                tmeta["completion_status"] = terminal_stream_status
                                tmeta["auth_ms"] = auth_ms
                                tmeta["query_resolution_ms"] = query_resolution_ms
                                tmeta["retrieval_ms"] = ev_ms
                                tmeta["evidence_retrieval_ms"] = ev_ms
                                tmeta["reranking_ms"] = None
                                tmeta["visible_ttft_ms"] = visible_now
                                tmeta["ttft_visible_ms"] = visible_now
                                tmeta["provider_ttft_ms"] = (
                                    tmeta.get("provider_ttft_ms")
                                    if (
                                        live_provider_active
                                        and tmeta.get("provider_ttft_ms") is not None
                                    )
                                    else (recorded_prov_ttft if live_provider_active else None)
                                )
                                tmeta["total_ms"] = total_now
                                tmeta["provider_stream_ms"] = (
                                    round((time.perf_counter() - t_stream_start) * 1000, 1)
                                    if (live_provider_active and t_stream_start is not None)
                                    else None
                                )
                                yield f"{prefix}[STREAM_META:{json.dumps(tmeta)}]{suffix}"
                                continue
                            except Exception:
                                yield chunk
                                continue
                        if ttft_ms is None:
                            ttft_ms = round((time.perf_counter() - t_req_start) * 1000, 1)
                        if ttft_visible_ms is None and chunk.strip():
                            ttft_visible_ms = round((time.perf_counter() - t_req_start) * 1000, 1)
                        if "[" in chunk and active_citations is not None:
                            chunk, _removed = validate_response_citations(chunk, active_citations)
                        captured_prose.append(chunk)
                        yield chunk
                    if (
                        cache_key
                        and terminal_stream_status == "complete"
                        and captured_meta is not None
                        and captured_prose
                        and not _withdrawn_notice(captured_meta.get("citations") or [])
                        and callable(getattr(ctx.cache_service, "set_versioned_entry", None))
                    ):
                        full_text = "".join(captured_prose).strip()
                        if full_text:
                            ctx.cache_service.set_versioned_entry(
                                cache_key,
                                {"metadata": captured_meta, "text": full_text},
                            )
                yield "\n[STREAM_DONE]\n"
            except Exception as exc:
                logger.error("Chat stream error: %s", exc)
                yield "\n\nAn unexpected error occurred during synthesis. Please retry your question."
                yield "\n[STREAM_DONE]\n"
            finally:
                t_end = time.perf_counter()
                provider_stream_ms = (
                    round((t_end - t_stream_start) * 1000, 1) if t_stream_start is not None else 0.0
                )
                logger.info(
                    "[CHAT_TIMING] route=%s auth_ms=%s research_ms=%.1f engine_ms=%.1f enrich_ms=%s provider_ms=%.1f ttft_visible_ms=%.1f total_ms=%.1f",
                    prepared.get("route"),
                    f"{auth_ms:.1f}" if auth_ms is not None else "null",
                    research_ms,
                    engine_ms,
                    f"{enrich_ms:.1f}" if enrich_ms is not None else "null",
                    provider_stream_ms,
                    ttft_visible_ms if ttft_visible_ms is not None else (t_end - t_req_start) * 1000,
                    (t_end - t_req_start) * 1000,
                )

        response = current_app.response_class(generate(), mimetype=STREAM_MIME)
        response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
        response.headers["Vary"] = "Authorization, Cookie"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @app.get("/api/chat/diagnostic-mcqs")
    def diagnostic_mcqs():
        raw_concept = request.args.get("concept") or ""
        concept = CONTROL_CHARS.sub("", raw_concept).strip()
        if len(concept) > MAX_CONCEPT_CHARS:
            return jsonify({"error": "invalid_concept"}), 400
        record_user_action("quiz_activity", concept)
        principal = getattr(request, "archipelago_principal", None)
        if principal and principal.get("id"):
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
        raw_body = request.get_json(silent=True)
        body = raw_body if isinstance(raw_body, dict) else {}
        principal = getattr(request, "archipelago_principal", None)
        target = CONTROL_CHARS.sub("", str(body.get("target_concept") or "")).strip()
        if len(target) > MAX_CONCEPT_CHARS:
            return jsonify({"error": "invalid_target_concept"}), 400
        if principal and principal.get("id") and target:
            saved = ctx.limiter.completed_quiz(principal["id"], target)
            if saved:
                return jsonify(saved)
        result = ctx.engine.adaptive_step(body)
        if principal and principal.get("id") and target and result.get("completed"):
            ctx.limiter.save_completed_quiz(principal["id"], target, result)
        return jsonify(result)

    @app.post("/api/chat/telemetry")
    def telemetry():
        raw_body = request.get_json(silent=True)
        body = raw_body if isinstance(raw_body, dict) else {}
        record_user_action("graph_explore", str(body.get("concept_id") or body.get("event") or ""))
        return ("", TELEMETRY_NO_CONTENT)

    @app.route("/api/chat/history", methods=["DELETE", "POST"])
    def delete_chat_history():
        """Delete the caller's server-side chat activity log and saved diagnostic state."""
        principal = getattr(request, "archipelago_principal", None)
        if principal is None and getattr(ctx, "auth", None) is not None:
            principal, _err = ctx.auth.principal()
        if principal is None or not principal.get("id"):
            return jsonify({"error": "unauthorized"}), 401
        raw_body = request.get_json(silent=True)
        body = raw_body if isinstance(raw_body, dict) else {}
        session_id = (
            CONTROL_CHARS.sub(
                "", str(body.get("session_id") or request.args.get("session_id") or "")
            ).strip()[:128]
            or None
        )
        user_id = str(principal["id"])
        removed_events = clear_user_traffic(user_id=user_id, session_id=session_id)
        quiz_conn_fn = getattr(ctx.limiter, "_quota_connection", None)
        if callable(quiz_conn_fn):
            try:
                with closing(quiz_conn_fn()) as conn, conn:
                    conn.execute("DELETE FROM completed_quiz WHERE user_id = ?", (user_id,))
            except Exception:
                pass
        resp = jsonify({"ok": True, "deleted": True, "removed_events": removed_events})
        resp.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
        resp.headers["Vary"] = "Authorization, Cookie"
        return resp, 200

    @app.route("/api/roadmap", methods=["GET", "POST", "OPTIONS"])
    def api_roadmap():
        """Build a staged learning roadmap from the concept graph."""
        raw_body = request.get_json(silent=True) if request.method == "POST" else None
        body = raw_body if isinstance(raw_body, dict) else {}
        topic = CONTROL_CHARS.sub(
            "", str(body.get("topic") or request.args.get("topic") or "")
        ).strip()
        if not topic:
            return jsonify({"error": "A topic is required to build a roadmap."}), 400
        if len(topic) > MAX_QUERY_CHARS:
            return jsonify({"error": "Topic exceeds maximum length."}), 400
        result = build_roadmap(ctx.engine.graph, topic)
        if result.get("error"):
            return jsonify(result), 404
        return jsonify(result)

    @app.route("/api/quiz", methods=["GET", "POST", "OPTIONS"])
    def api_quiz():
        """Build a short practice quiz from the concept graph."""
        raw_body = request.get_json(silent=True) if request.method == "POST" else None
        body = raw_body if isinstance(raw_body, dict) else {}
        topic = CONTROL_CHARS.sub(
            "", str(body.get("topic") or request.args.get("topic") or "")
        ).strip()
        if not topic:
            return jsonify({"error": "A topic is required to build a quiz."}), 400
        if len(topic) > MAX_QUERY_CHARS:
            return jsonify({"error": "Topic exceeds maximum length."}), 400
        result = build_quiz(ctx.engine, topic)
        if result.get("error"):
            return jsonify(result), 404
        return jsonify(result)
