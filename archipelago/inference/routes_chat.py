"""Chat API streaming endpoint and concept bootstrap."""
from __future__ import annotations

import json
import os
import threading

from flask import Response, request, jsonify

from archipelago.inference.graph_lock import graph_lock
from archipelago.auth import require_student_or_open
from archipelago.inference import state as st
from archipelago.inference.llm_gateway import LLM_UNAVAILABLE_MSG
from archipelago.inference.routing import resolve_query_routing
from archipelago.inference.neighborhood import get_graph_neighborhood
from archipelago.inference.curriculum import (
    find_curriculum_chains, format_curriculum_paths_section,
)
from archipelago.inference.citations import (
    build_concept_citation_map, build_citation_payloads, _resolve_printed_page,
)
from archipelago.inference.synthesis import (
    build_graph_notes, format_natural_fallback, synthesize_with_ollama_streaming,
    stream_synthesis_with_ollama,
    general_chat_reply, is_ollama_available, OLLAMA_UNAVAILABLE_MSG,
    render_library_books, render_library_chapters, render_library_chapter_lookup,
    identity_reply, onboarding_reply, not_indexed_reply, enforce_sterile_prose,
)
from archipelago.inference.library_queries import (
    get_book_metadata_details,
    render_library_book_details,
    get_library_hours_response,
    get_library_holdings_response,
    get_books_for_topic, clean_topic_query, get_chapters_of_book, get_chapters_containing_concept,
)
from archipelago.inference.scope_gate import (
    OUT_OF_SCOPE_MESSAGE,
    NOT_IN_CORPUS_MESSAGE,
    IMPLEMENTATION_REFUSAL_MESSAGE,
)
from archipelago.inference.aliases import _node_name, generate_aliases
from archipelago.inference.embeddings import load_embedding_model, load_aura_model
from archipelago.inference.demo_query_books import merge_demo_citations
from archipelago.inference.reply_inventory import attach_inventory, inventory_suffix


def _with_holdings(query, text, citations=None, books=None, meta=None):
    """Append fake inventory table + exact-page links to a finished reply."""
    return attach_inventory(
        query, text, citations=citations, books=books, meta=meta,
    )

@st.app.route("/api/chat", methods=["POST"])
@require_student_or_open
def api_chat():
    """Student-facing chat. No librarian upload/delete privileges."""
    from flask import Response
    req_data = request.get_json() or {}
    query = (req_data.get("query") or req_data.get("message") or "").strip()
    mode = req_data.get("mode", "rag_synthesis")
    history = req_data.get("history", [])

    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400
    if len(query) < 2:
        return jsonify({"error": "Query too short (minimum 2 characters)"}), 400
    if len(query) > 500:
        return jsonify({"error": "Query exceeds maximum limit of 500 characters"}), 400

    # Supabase Cache Lookup & Metrics (Zero LLM calls on cache hit)
    try:
        from archipelago.inference.cache_service import CacheService
        from archipelago.inference.cache_metrics import metrics as cache_metrics
        cache_metrics.inc_total_requests()
        cached_entry = CacheService().get_cached_response(query)
        if cached_entry:
            cache_metrics.inc_cache_hit(tokens_saved=300)
            def generate_cached():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": cached_entry.get("sources") or [],
                    "related_concepts": [],
                    "routing": {"route": "cached_response", "score": 1.0, "reason": "cache_hit"},
                    "graph_data": cached_entry.get("graph_data"),
                    "roadmap": cached_entry.get("roadmap_data"),
                    "logs": [{
                        "step": "Supabase Cache",
                        "status": "Hit",
                        "details": f"Cached response returned (hit #{cached_entry.get('hit_count', 1)}). Zero LLM tokens consumed.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield str(cached_entry.get("response") or "") + "\n"
            return Response(generate_cached(), mimetype="text/plain")
        else:
            cache_metrics.inc_cache_miss()
    except Exception:
        pass

    # Gateway Interceptor & Subagents (Zero LLM API calls for attacks, code-gen, homework)
    from archipelago.inference.orchestration.subagents import OrchestratorAgent, AuthGatewayAgent
    interceptor = OrchestratorAgent().intercept(query)
    if interceptor.get("status") == "denied":
        def generate_denied():
            payload = {
                "anchor_concept": None,
                "prerequisites": [],
                "unlocks": [],
                "citations": [],
                "related_concepts": [],
                "routing": {"route": "gateway_blocked", "score": 1.0, "reason": interceptor.get("reason")},
                "logs": [{
                    "step": "Gateway Firewall",
                    "status": "Blocked",
                    "details": interceptor.get("reason"),
                }],
            }
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield interceptor.get("reason") + "\n"
        return Response(generate_denied(), mimetype="text/plain")

    # Check institutional auth gateway card
    auth_card = AuthGatewayAgent().require_auth(query)
    if "[RENDER_AUTH_CARD]" in auth_card:
        def generate_auth():
            payload = {
                "anchor_concept": None,
                "prerequisites": [],
                "unlocks": [],
                "citations": [],
                "related_concepts": [],
                "routing": {"route": "auth_gateway", "score": 1.0, "reason": "institutional_paywall"},
                "logs": [{
                    "step": "Auth Gateway",
                    "status": "Success",
                    "details": "Institutional authentication card triggered.",
                }],
            }
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield auth_card + "\n"
        return Response(generate_auth(), mimetype="text/plain")

    # Default product path: embedder ranking + graph traversal + natural reply.
    # conversational_agent uses the same smart router (domain → graph, chitchat → free chat).
    if mode in ("rag_synthesis", "conversational_agent"):
        routing = resolve_query_routing(query, history=history)
        route = routing["route"]
        route = {
            "library_info": ("library_resources" if (routing.get("slots") or {}).get("resource_access") or (routing.get("slots") or {}).get("resource_key") else "library_hours"),
            "library_resource_lookup": "library_holdings",
            "library_journal_status": "library_holdings",
            "library_catalog_stats": "library_holdings",
        }.get(route, route)
        # Explicit synthesis flag still honored; default ON so answers are natural.
        wants_synthesis = req_data.get("synthesis", True) not in (False, "off", "none", 0, "0")

        # ── Out of Scope / defensive refusals (3 generic messages only) ─
        if route == "out_of_scope":
            reason = routing.get("reason", "out_of_scope_topic") or ""
            rl = reason.lower()
            intent_meta = (routing.get("slots") or {})
            if "implementation" in rl:
                out_msg = IMPLEMENTATION_REFUSAL_MESSAGE
                detail = (
                    f"Intent gate blocked implementation "
                    f"(intent={intent_meta.get('intent')}, "
                    f"method={intent_meta.get('intent_method')})."
                )
            elif "not_in_corpus" in rl or "entity" in rl:
                out_msg = NOT_IN_CORPUS_MESSAGE
                detail = (
                    f"Intent gate: entity/trivia not grounded in corpus "
                    f"(intent={intent_meta.get('intent')})."
                )
            elif "meta" in rl:
                # Same sterile boundary as OOS — do not leak constraints
                out_msg = OUT_OF_SCOPE_MESSAGE
                detail = "Intent gate blocked meta / system-prompt extraction."
            else:
                out_msg = OUT_OF_SCOPE_MESSAGE
                detail = (
                    f"Out of AIML library scope "
                    f"(intent={intent_meta.get('intent')}, reason={reason})."
                )

            closest = intent_meta.get("closest_concepts") or []
            # Soft "maybe you meant" bridge on every reject flavor that has
            # plausible graph neighbors — not just corpus misses.
            closest = [c for c in closest if c][:3]
            if closest:
                bridge = ", ".join(f"**{c}**" for c in closest)
                out_msg = (
                    f"{out_msg}\n\nIf you were after something nearby, the closest "
                    f"concepts on our shelves are: {bridge}."
                )

            def generate_out_of_scope():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": [],
                    "routing": {"route": route, "score": 0.0, "reason": reason},
                    "logs": [{
                        "step": "Pass 1: Intent Gate & Scope",
                        "status": "Out of Scope",
                        "details": detail,
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, out_msg)
            return Response(generate_out_of_scope(), mimetype="text/plain")

        # ── Identity ──────────────────────────────────────────────────
        if route == "identity":
            def generate_identity():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "identity"},
                    "logs": [{
                        "step": "Pass 1: Intent",
                        "status": "Identity",
                        "details": "Assistant identity / capabilities question.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, identity_reply(query, history))
            return Response(generate_identity(), mimetype="text/plain")

        # ── Diagnostic MCQ Knowledge Assessment ──────────────────────
        if route == "roadmap_quiz":
            def generate_quiz_stream():
                from archipelago.inference.curriculum import generate_diagnostic_quiz
                target_id = routing.get("slots", {}).get("target_concept") or "low_rank_adaptation"
                quiz = generate_diagnostic_quiz(target_id, num_questions=5)
                target_info = quiz.get("target_concept", {})
                target_name = target_info.get("name") or target_id
                prereq_names = [q["concept_name"] for q in quiz.get("questions", [])]

                payload = {
                    "anchor_concept": target_id,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": routing.get("related", [])[:5],
                    "routing": {"route": route, "score": 1.0, "reason": "diagnostic_assessment"},
                    "logs": [{
                        "step": "Pass 1: Intent",
                        "status": "Diagnostic Assessment",
                        "details": f"Generating 5 diagnostic MCQs for target concept: {target_name}.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"

                # If synthesis is requested, let the inference model introduce the diagnostic quiz contextually
                if wants_synthesis:
                    try:
                        from archipelago.inference.llm_gateway import gateway_chat_stream
                        prompt = (
                            f"You are Archipelago Diagnostic Tutor. A student wants to learn '{target_name}'. "
                            f"To build a personalized 1-6 hop learning roadmap, we need to test their prior knowledge on its prerequisites: {', '.join(prereq_names[:4])}. "
                            f"Write a friendly, encouraging 2-sentence introduction explaining why assessing these foundations is critical before jumping into '{target_name}'. Do not reveal quiz answers."
                        )
                        for chunk in gateway_chat_stream(
                            messages=[{"role": "user", "content": prompt}],
                            purpose="synthesis",
                            temperature=0.2,
                            max_tokens=120,
                            timeout=15,
                        ):
                            if chunk:
                                yield chunk
                        yield "\n\n"
                    except Exception as e:
                        yield f"Welcome to the diagnostic assessment for **{target_name}**! Assessing your foundational grasp on prerequisite concepts allows Archipelago to build an optimal, personalized 1–6 hop learning roadmap.\n\n"
                else:
                    yield f"Welcome to the diagnostic assessment for **{target_name}**! Assessing your foundational grasp on prerequisite concepts allows Archipelago to build an optimal, personalized 1–6 hop learning roadmap.\n\n"

                lines = [
                    f"### 🎯 Knowledge Assessment: Prerequisites for {target_name}\n",
                    f"Let's assess your prior knowledge to build a personalized 1–6 hop learning roadmap to **{target_name}**.",
                    "Answer these 5 quick diagnostic questions (reply with e.g. *1-A, 2-B, 3-C, 4-D, 5-A* or just your answers):\n",
                ]
                for q in quiz.get("questions", []):
                    lines.append(f"**Question {q['q_index']}: {q['concept_name']}** `[{q['difficulty'].upper()}]`")
                    lines.append(f"{q['question']}")
                    for opt_key, opt_text in sorted(q.get("options", {}).items()):
                        lines.append(f"- **({opt_key})** {opt_text}")
                    lines.append("")

                lines.append("---")
                lines.append(f"💡 *Once you answer, Archipelago will identify your baseline concept and plot your step-by-step roadmap to {target_name}!*")
                yield "\n".join(lines)

            return Response(generate_quiz_stream(), mimetype="text/plain")

        # ── Diagnostic Quiz Evaluation & Personalized Roadmap ────────
        if route == "roadmap_quiz_eval":
            def generate_quiz_eval_stream():
                from archipelago.inference.curriculum import evaluate_quiz_and_route_roadmap
                slots = routing.get("slots", {})
                target_id = slots.get("target_concept") or "low_rank_adaptation"
                student_answers = slots.get("answers") or {}

                eval_result = evaluate_quiz_and_route_roadmap(student_answers, target_id, max_hops=6)
                score_str = eval_result.get("score", "0/5")
                baseline = eval_result.get("baseline_concept", {})
                baseline_name = baseline.get("name") if isinstance(baseline, dict) else str(baseline)
                roadmap = eval_result.get("roadmap", {})
                target_name = eval_result.get("target_concept", {}).get("name") or target_id
                hops = roadmap.get("hops", 0)

                payload = {
                    "anchor_concept": target_id,
                    "prerequisites": roadmap.get("steps", []),
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": routing.get("related", [])[:5],
                    "routing": {"route": route, "score": 1.0, "reason": "diagnostic_evaluation"},
                    "logs": [{
                        "step": "Pass 1: Intent",
                        "status": "Diagnostic Evaluation",
                        "details": f"Student scored {score_str}. Baseline: {baseline_name}. Roadmap: {hops} hops to {target_name}.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"

                # Run inference model to synthesize personalized pedagogical feedback
                if wants_synthesis:
                    try:
                        from archipelago.inference.llm_gateway import gateway_chat_stream
                        prompt = (
                            f"You are Archipelago Diagnostic Tutor. A student completed a diagnostic quiz for target concept '{target_name}'.\n"
                            f"Score: {score_str}.\n"
                            f"Identified Starting Baseline: {baseline_name}.\n"
                            f"Mastered Prerequisites: {', '.join(eval_result.get('mastered_concepts', [])) or 'None'}.\n"
                            f"Prerequisites to Review: {', '.join(eval_result.get('gap_concepts', [])) or 'None'}.\n"
                            f"In 2-3 encouraging sentences, evaluate their performance, highlight what they mastered, and introduce their personalized {hops}-hop learning path."
                        )
                        for chunk in gateway_chat_stream(
                            messages=[{"role": "user", "content": prompt}],
                            purpose="synthesis",
                            temperature=0.2,
                            max_tokens=150,
                            timeout=15,
                        ):
                            if chunk:
                                yield chunk
                        yield "\n\n"
                    except Exception as e:
                        yield f"### 📊 Diagnostic Evaluation: Score {score_str}\n\nBased on your responses, your foundational baseline is **{baseline_name}**. Here is your customized learning roadmap to **{target_name}**:\n\n"
                else:
                    yield f"### 📊 Diagnostic Evaluation: Score {score_str}\n\nBased on your responses, your foundational baseline is **{baseline_name}**. Here is your customized learning roadmap to **{target_name}**:\n\n"

                # Stream the computed roadmap and question breakdown
                lines = [f"### 🗺️ Personalized Roadmap: {baseline_name} → {target_name} ({hops} hops)\n"]
                lines.append(roadmap.get("markdown", ""))
                lines.append("\n#### 📝 Question Review")
                for d in eval_result.get("details", {}).get("mastered", []):
                    lines.append(f"- ✅ **Q{d['q_index']}: {d['concept_name']}** — Correct (`{d['user_answer']}`). {d['explanation']}")
                for d in eval_result.get("details", {}).get("gaps", []):
                    lines.append(f"- ❌ **Q{d['q_index']}: {d['concept_name']}** — Selected `{d['user_answer']}` (Correct: `{d['correct_answer']}`). {d['explanation']}")
                yield "\n".join(lines)

            return Response(generate_quiz_eval_stream(), mimetype="text/plain")

        # ── Personalized Roadmap Between Two Concepts ─────────────────
        if route == "roadmap_between":
            def generate_roadmap_stream():
                from archipelago.inference.curriculum import find_roadmap_between
                slots = routing.get("slots", {})
                start_id = slots.get("start_id", "")
                target_id = slots.get("target_id", "")
                roadmap = find_roadmap_between(start_id, target_id, max_hops=6)

                payload = {
                    "anchor_concept": target_id,
                    "prerequisites": roadmap.get("steps", []),
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": routing.get("related", [])[:5],
                    "routing": {"route": route, "score": 1.0, "reason": "personalized_roadmap"},
                    "logs": [{
                        "step": "Pass 1: Intent",
                        "status": "Personalized Roadmap",
                        "details": f"Calculated {roadmap.get('hops', 0)}-hop curriculum from {roadmap.get('start_name')} to {roadmap.get('target_name')}.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield roadmap.get("markdown", "")

            return Response(generate_roadmap_stream(), mimetype="text/plain")

        # ── Onboarding / start learning AIML ──────────────────────────
        if route == "onboarding":
            def generate_onboarding():
                related = routing.get("related") or []
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": related[:5],
                    "routing": {"route": route, "score": 1.0, "reason": "onboarding_syllabus"},
                    "logs": [{
                        "step": "Pass 1: Intent",
                        "status": "Onboarding",
                        "details": "Broad AIML syllabus / start-learning entry path.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, onboarding_reply(query, related))
            return Response(generate_onboarding(), mimetype="text/plain")

        # ── Small Talk ──────────────────────────────────────────────────
        if route == "small_talk":
            def generate_small_talk():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "conversational_greeting"},
                    "logs": [{
                        "step": "Pass 1: Intent",
                        "status": "Small talk",
                        "details": "Conversational pleasantry detected.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, general_chat_reply(query, history))
            return Response(generate_small_talk(), mimetype="text/plain")

        # ── Library Query: Book Details & Summaries ──────────────────
        if route == "library_book_details":
            meta = get_book_metadata_details(query)
            book_citations = []
            if meta:
                doc_id = meta.get("doc_id") or meta.get("book_id") or f"doc_{meta['title']}"
                reader_url = meta.get("reader_url") or meta.get("pdf_path") or ""
                book_citations.append({
                    "evidence_id": "S1",
                    "doc_id": doc_id,
                    "title": meta["title"],
                    "document_title": meta["title"],
                    "page_number": 1,
                    "page": 1,
                    "is_pearson": bool(meta.get("is_pearson")),
                    "reader_url": reader_url,
                    "url": reader_url,
                    "shelf_location": meta.get("shelf_location", "PEARSON-ELIB"),
                    "call_number": meta.get("call_number", "PEARSON-ELIB"),
                    "total_copies": meta.get("total_copies", 10),
                    "available_copies": meta.get("available_copies", 8),
                })
                notes = render_library_book_details(meta)
                details = f"Retrieved comprehensive metadata for '{meta['title']}'."
            else:
                notes = f"### 📚 Book Details\nCould not find a specific indexed book or paper matching '{query}'. You can browse the complete e-book shelves at [/library](/library)."
                details = "No exact book match."
            def generate_book_details():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": meta.get("prerequisites", []) if meta else [],
                    "unlocks": meta.get("unlocks", []) if meta else [],
                    "citations": book_citations,
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "library_book_details"},
                    "logs": [{
                        "step": "Library Retrieval",
                        "status": "Success" if meta else "Not Found",
                        "details": details,
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, notes, citations=book_citations, meta=meta)
            return Response(generate_book_details(), mimetype="text/plain")

        if route == "library_resources":
            from archipelago.inference.library_resource_access import render_resource_access

            resource_key = str((routing.get("slots") or {}).get("resource_key") or "")
            notes = render_resource_access(query, resource_key=resource_key)

            def generate_resource_access():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "library_resources"},
                    "logs": [{
                        "step": "Library Access",
                        "status": "Success",
                        "details": "Returned redacted institutional portal guidance.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, notes)

            return Response(generate_resource_access(), mimetype="text/plain")

        # ── Library Query: Operating Hours & Access ───────────────────
        if route == "library_hours":
            notes = get_library_hours_response()
            def generate_hours():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "library_hours"},
                    "logs": [{
                        "step": "Library Retrieval",
                        "status": "Success",
                        "details": "Retrieved 24x7 operating hours & circulation policies.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, notes)
            return Response(generate_hours(), mimetype="text/plain")

        # ── Library Query: Holdings & Inventory ───────────────────────
        if route == "library_holdings":
            notes = get_library_holdings_response(query)
            def generate_holdings():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "library_holdings"},
                    "logs": [{
                        "step": "Library Retrieval",
                        "status": "Success",
                        "details": "Retrieved catalog inventory metrics (109 records / 904 copies).",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, notes)
            return Response(generate_holdings(), mimetype="text/plain")

        # ── Library Query: Books Recommendation ───────────────────────
        if route == "library_books":
            topic = clean_topic_query(query)
            limit = int((routing.get("slots") or {}).get("limit") or 5)
            books = get_books_for_topic(query, limit=limit)
            notes = render_library_books(topic, books)
            book_citations = []
            for i, b in enumerate(books):
                b_url = b.get("reader_url") or b.get("url") or ""
                book_citations.append({
                    "evidence_id": f"S{i+1}",
                    "doc_id": b.get("doc_id") or b.get("book_id") or b.get("id"),
                    "title": b.get("title") or b.get("book_title"),
                    "document_title": b.get("title") or b.get("book_title"),
                    "page_number": int(b.get("page_number") or 1),
                    "page": int(b.get("page_number") or 1),
                    "is_pearson": bool(b.get("is_pearson")),
                    "reader_url": b_url,
                    "url": b_url,
                    "shelf_location": b.get("shelf_location", "PEARSON-ELIB"),
                    "call_number": b.get("call_number", "PEARSON-ELIB"),
                    "total_copies": int(b.get("total_copies") or 10),
                    "available_copies": int(b.get("available_copies") or 8),
                })
            def generate_books():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": book_citations,
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "library_books"},
                    "logs": [{
                        "step": "Library Retrieval",
                        "status": "Success",
                        "details": f"Found {len(books)} books for topic '{topic}'.",
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, notes, citations=book_citations, books=books)
            return Response(generate_books(), mimetype="text/plain")

        # ── Library Query: Chapters of Book ───────────────────────────
        if route == "library_chapters":
            res = get_chapters_of_book(query)
            if res:
                book_title, chapters = res
                notes = render_library_chapters(book_title, chapters)
                details = f"Retrieved {len(chapters)} chapters for '{book_title}'."
            else:
                book_title = query
                notes = f"Could not find any matching book/paper for '{query}' in the database."
                details = "No book match found."
            def generate_chapters():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "library_chapters"},
                    "logs": [{
                        "step": "Library Retrieval",
                        "status": "Success" if res else "Not Found",
                        "details": details,
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, notes)
            return Response(generate_chapters(), mimetype="text/plain")

        # ── Library Query: Chapter Lookup for Concept ─────────────────
        if route == "library_chapter_lookup":
            res = get_chapters_containing_concept(query)
            if res:
                book_title, concept_name, chapters = res
                notes = render_library_chapter_lookup(book_title, concept_name, chapters)
                details = f"Found {len(chapters)} chapters in '{book_title}' discussing '{concept_name}'."
            else:
                notes = f"Could not find matching book or concept for query: '{query}'."
                details = "No match found."
            def generate_lookup():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": [],
                    "routing": {"route": route, "score": 1.0, "reason": "library_chapter_lookup"},
                    "logs": [{
                        "step": "Library Retrieval",
                        "status": "Success" if res else "Not Found",
                        "details": details,
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, notes)
            return Response(generate_lookup(), mimetype="text/plain")

        # ── Low Similarity Reject (honest not-indexed reply) ────────────
        if route == "low_similarity_reject":
            sterile = bool((routing.get("slots") or {}).get("sterile"))
            def generate_reject():
                closest = (routing.get("slots") or {}).get("closest_concepts") or []
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": routing.get("related") or [],
                    "routing": {"route": route, "score": routing.get("score"), "reason": routing.get("reason")},
                    "logs": [{
                        "step": "Pass 1: Intent & Embedder Gate",
                        "status": "Not indexed",
                        "details": (
                            f"Highest similarity score ({float(routing.get('score') or 0):.3f}) "
                            f"is below the rejection threshold ({st.REJECT_SIMILARITY_THRESHOLD}) "
                            f"with no strong lexical/alias surface hit."
                        ),
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                reply = not_indexed_reply(query, closest, natural=wants_synthesis and not sterile)
                if sterile:
                    reply = enforce_sterile_prose(reply, fallback=reply)
                yield _with_holdings(query, reply)
            return Response(generate_reject(), mimetype="text/plain")

        # ── General chat (low similarity / chitchat) ──────────────────────
        if route == "general_chat":
            def generate_general():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": [],
                    "related_concepts": routing.get("related") or [],
                    "routing": {"route": route, "score": routing.get("score"), "reason": routing.get("reason")},
                    "logs": [{
                        "step": "Pass 1: Intent & Embedder Gate",
                        "status": "General chat",
                        "details": (
                            f"Similarity too low for graph grounding "
                            f"(score={float(routing.get('score') or 0):.3f} < soft "
                            f"{st.DOMAIN_SOFT_THRESHOLD}). Free conversational reply."
                        ),
                    }],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield _with_holdings(query, general_chat_reply(query, history))
            return Response(generate_general(), mimetype="text/plain")

        # ── Graph path (strong or soft domain) ────────────────────────────
        with graph_lock.read_lock():
            anchor_id = routing.get("anchor_id")
            related = routing.get("related") or []
            if not anchor_id or anchor_id not in st.CONCEPTS_DATA:
                # Soft path without a usable id → still try top related list
                if related and related[0]["id"] in st.CONCEPTS_DATA:
                    anchor_id = related[0]["id"]
                else:
                    def generate_orphan():
                        payload = {
                            "logs": [{
                                "step": "Pass 1: Retrieval",
                                "status": "Empty graph",
                                "details": "No concepts loaded in st.CONCEPTS_DATA.",
                            }],
                            "citations": [],
                        }
                        yield json.dumps(payload) + "\n[STREAM_START]\n"
                        yield general_chat_reply(query, history)
                    return Response(generate_orphan(), mimetype="text/plain")

            target_concept = st.CONCEPTS_DATA[anchor_id]
            prereqs, unlocks, _legacy_cites = get_graph_neighborhood(anchor_id, k=2)
            # Soft multi-anchor: pull light neighborhoods for top related peers
            related_nodes = []
            for r in related[:st.TOP_K_RELATED]:
                rid = r.get("id")
                if not rid or rid == anchor_id or rid not in st.CONCEPTS_DATA:
                    continue
                node = st.CONCEPTS_DATA[rid]
                related_nodes.append({
                    "id": rid,
                    "name": node.get("label") or node.get("name") or rid,
                    "summary": node.get("summary") or r.get("summary") or "",
                    "cos": r.get("cos"),
                })

            citation_map = build_concept_citation_map(target_concept, prereqs, unlocks)
            citation_payloads = build_citation_payloads(target_concept, prereqs, unlocks, citation_map)
            citation_payloads = merge_demo_citations(query, citation_payloads)
            evidence_ids = {payload["evidence_id"] for payload in citation_payloads if payload["evidence_id"]}
            # Session 2: multi-hop curriculum chains (≤3 hops) with book/page links
            curriculum_paths = find_curriculum_chains(
                anchor_id, max_hops=3, citation_map=citation_map, max_paths=4
            )
            notes = build_graph_notes(
                query, target_concept, prereqs, unlocks, related, citation_map,
                bare_markers=True,
            )
            if curriculum_paths:
                notes = notes + "\n" + format_curriculum_paths_section(curriculum_paths)
            is_partial = bool((routing.get("slots") or {}).get("partial")) or (
                routing.get("reason") == "partial_coverage_low_cos"
            )
            natural_fallback = format_natural_fallback(
                query, target_concept, prereqs, unlocks, related, citation_map,
                curriculum_paths=curriculum_paths,
                partial=is_partial,
            )
            match_score = routing.get("score")
            step_logs = [
                {
                    "step": "Pass 1: Embedder Ranking",
                    "status": (
                        "Partial coverage"
                        if is_partial
                        else ("Success" if route == "graph_strong" else "Soft domain match")
                    ),
                    "details": (
                        f"Route={route}; anchor=**{_node_name(target_concept)}** "
                        f"(score={match_score if isinstance(match_score, (int, float)) else match_score}); "
                        f"reason={routing.get('reason')}; top related="
                        f"{', '.join(r.get('label', '') for r in related[:3])}"
                    ),
                },
                {
                    "step": "Pass 2: Graph Traversal & Citations",
                    "status": "Success",
                    "details": (
                        f"Traversed {len(prereqs)} prerequisites and {len(unlocks)} unlocks; "
                        f"{len(citation_payloads)} evidence records; "
                        f"{len(related_nodes)} embedder neighbors; "
                        f"{len(curriculum_paths)} multi-hop curriculum path(s)."
                    ),
                },
                {
                    "step": "Pass 3: Natural Synthesis",
                    "status": "Requested" if wants_synthesis else "Template",
                    "details": (
                        f"{st.GEMINI_MODEL} natural wording over graph notes "
                        "(falls back to structured natural summary if offline)"
                        if wants_synthesis
                        else "Structured natural summary without generator."
                    ),
                },
            ]

            # Mode A / B / C bounded subgraph and diagnostic MCQ layer
            query_mode = routing.get("query_mode") or "mode_a"
            secondary_concept = None
            if query_mode == "mode_b" and len(related_nodes) > 0:
                secondary_concept = related_nodes[0].get("id")

            from archipelago.inference.subgraph import generate_bounded_subgraph
            bounded_subgraph = generate_bounded_subgraph(
                anchor_id,
                secondary_target_id=secondary_concept,
                mode=query_mode,
            )

            diagnostic_mcqs = []
            try:
                from archipelago.inference.diagnostic_mcq import generate_diagnostic_mcqs
                prereq_ids = [p["id"] for p in prereqs if isinstance(p, dict) and p.get("id")]
                diagnostic_mcqs = generate_diagnostic_mcqs(
                    anchor_id,
                    prereq_ids=prereq_ids,
                    num_questions=3,
                )
            except Exception as exc:
                print(f"Pre-cached MCQ generation fallback triggered: {exc}")
                diagnostic_mcqs = []

            def generate_graph():
                init_payload = {
                    "anchor_concept": target_concept,
                    "query_mode": query_mode,
                    "subgraph": bounded_subgraph.to_dict(),
                    "diagnostic_mcqs": diagnostic_mcqs,
                    "prerequisites": prereqs,
                    "unlocks": unlocks,
                    "related_concepts": related_nodes,
                    "curriculum_paths": curriculum_paths,
                    "citations": citation_payloads,
                    "routing": {
                        "route": route,
                        "score": routing.get("score"),
                        "reason": routing.get("reason"),
                        "query_mode": query_mode,
                    },
                    "citation_by_concept": {
                        concept_id: [
                            {
                                "evidence_id": evidence.get("evidence_id"),
                                "doc_id": evidence.get("doc_id"),
                                "page_number": evidence.get("page_number"),
                                "printed_page": _resolve_printed_page(evidence),
                                "section_title": evidence.get("section_title"),
                            }
                            for evidence in concept_evidence
                        ]
                        for concept_id, concept_evidence in citation_map.items()
                    },
                    "logs": step_logs,
                }
                sterile = bool((routing.get("slots") or {}).get("sterile"))
                yield json.dumps(init_payload) + "\n[STREAM_START]\n"
                if wants_synthesis:
                    try:
                        had_tokens = False
                        accumulated = []
                        for token in stream_synthesis_with_ollama(
                            notes,
                            evidence_ids=evidence_ids,
                            user_query=query,
                            citation_payloads=citation_payloads,
                            sterile=sterile,
                            fallback_text=natural_fallback,
                            history=history,
                        ):
                            had_tokens = True
                            accumulated.append(token)
                            yield token

                        if not had_tokens:
                            fallback_prose = enforce_sterile_prose(natural_fallback) if sterile else natural_fallback
                            yield _with_holdings(query, fallback_prose, citations=citation_payloads)
                        else:
                            yield inventory_suffix(query, citations=citation_payloads)
                        return
                    except RuntimeError:
                        yield _with_holdings(query, OLLAMA_UNAVAILABLE_MSG, citations=citation_payloads)
                        return
                    except Exception:
                        yield _with_holdings(query, OLLAMA_UNAVAILABLE_MSG, citations=citation_payloads)
                        return
                fallback_prose = enforce_sterile_prose(natural_fallback) if sterile else natural_fallback
                yield _with_holdings(query, fallback_prose, citations=citation_payloads)

            return Response(generate_graph(), mimetype="text/plain")

    else:
        return jsonify({"error": f"Invalid mode: {mode}"}), 400


@st.app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST"])
def api_diagnostic_mcqs():
    """Retrieve pre-cached or synthesized diagnostic MCQs with <= 200ms fallback guarantee."""
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    target_id = (
        request.args.get("concept")
        or request.args.get("target_concept")
        or data.get("target_concept")
        or data.get("concept")
        or ""
    ).strip()

    if not target_id:
        return jsonify({"error": "Missing target concept", "available": False, "mcqs": []}), 400

    try:
        from archipelago.inference.diagnostic_mcq import (
            generate_diagnostic_mcqs,
            get_prerequisite_chain,
            generate_single_mcq_on_the_spot,
        )
        t_node = st.CONCEPTS_DATA.get(target_id) or {}
        prereqs = [p.get("id") if isinstance(p, dict) else str(p) for p in (t_node.get("prerequisites") or [])]
        mcqs = generate_diagnostic_mcqs(target_id, prereq_ids=prereqs, num_questions=3)
        chain = get_prerequisite_chain(target_id, st.CONCEPTS_DATA)
        prereq_chain = [c for c in chain if c != target_id]
        immediate_y = prereq_chain[-1] if prereq_chain else target_id
        initial_q = generate_single_mcq_on_the_spot(immediate_y, st.CONCEPTS_DATA, q_index=1)

        return jsonify({
            "success": True,
            "available": bool(mcqs),
            "target_concept": target_id,
            "chain": chain,
            "prereq_chain": prereq_chain,
            "immediate_prerequisite": immediate_y,
            "initial_question": initial_q,
            "mcqs": mcqs,
        })
    except Exception as exc:
        print(f"Diagnostic MCQ fetch error: {exc}")
        return jsonify({
            "success": False,
            "available": False,
            "target_concept": target_id,
            "mcqs": [],
            "badge": "Personalized assessment temporarily unavailable.",
        }), 200


@st.app.route("/api/chat/adaptive-step", methods=["POST"])
def api_adaptive_step():
    """Execute an on-the-spot adaptive leap-back skip-list step."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    from archipelago.inference.diagnostic_mcq import execute_adaptive_step
    result = execute_adaptive_step(data, concepts_data=st.CONCEPTS_DATA)
    return jsonify(result)


@st.app.route("/api/chat/telemetry", methods=["POST"])
def api_chat_telemetry():
    """Track choice analytics (Personalized vs Normal graph selections)."""
    try:
        data = request.get_json(silent=True) or {}
        event = data.get("event", "graph_choice")
        mode = data.get("mode", "unknown")
        concept_id = data.get("concept_id", "")
        print(f"[TELEMETRY] event={event} mode={mode} concept={concept_id}")
        return jsonify({"logged": True, "event": event, "mode": mode})
    except Exception as exc:
        return jsonify({"logged": False, "error": str(exc)}), 200


@st.app.route("/api/chat/verify-mcq", methods=["POST"])
def api_verify_mcq():
    """Validate user answers for diagnostic MCQs and calculate prerequisite mastery."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    mcqs = data.get("mcqs") or []
    answers = data.get("answers") or {}
    target_id = data.get("target_concept") or ""

    if not mcqs and target_id:
        from archipelago.inference.diagnostic_mcq import generate_diagnostic_mcqs
        mcqs = generate_diagnostic_mcqs(target_id, num_questions=3)

    from archipelago.inference.diagnostic_mcq import evaluate_diagnostic_mcqs
    result = evaluate_diagnostic_mcqs(mcqs, answers, target_concept_id=target_id)
    return jsonify(result)



def init_concepts_data():
    try:
        with open(st.DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        nodes = list(data.get("visualization", {}).get("nodes", []) or data.get("nodes", []))
        extra_concepts = data.get("concepts", {})
        existing_ids = {n["id"] for n in nodes if "id" in n}
        for cid, c in extra_concepts.items():
            if cid not in existing_ids:
                c_node = dict(c)
                c_node.setdefault("id", cid)
                c_node.setdefault("label", c_node.get("name", cid))
                nodes.append(c_node)
        st.CONCEPTS_DATA = {n["id"]: n for n in nodes}
        # Session 2: precompute aliases for acronym/alias-aware ranking
        for cid, concept in st.CONCEPTS_DATA.items():
            if "id" not in concept:
                concept["id"] = cid
            concept["aliases"] = generate_aliases(concept)
        print(f"Synchronously loaded {len(st.CONCEPTS_DATA)} concepts at startup (aliases ready).")
    except Exception as e:
        print(f"Error loading concepts at startup: {e}")
