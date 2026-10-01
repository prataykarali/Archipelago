"""
src/api/app.py — Production REST & SSE Streaming API Server for Archipelago.

Features:
- Completely replaces Gradio with Flask + Gunicorn production backend
- POST /api/chat: Length check -> Router (6 intents, 3 tiers) -> Two-Pass Hybrid Retrieval ->
                  Context Isolation Assembly (max 6 nodes, max 3 chunks) ->
                  Local Ollama SLM (qwen3.5:0.8b) synthesis or topic suggestions
- GET /api/readiness: Health and readiness probe for podless/container orchestration
- GET /api/topics/suggest: Fuzzy concept discovery endpoint
- POST /api/roadmap/quiz: Diagnostic MCQ generation and evaluation
- GET /api/catalog/search: Physical library inventory search
- GET /api/eresources: Institutional gateway and database portal credentials
- POST /api/upload: Live universal PDF ingestion via lib-qwen:latest into KùzuDB
- GET /api/documents: List indexed documents
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request

from archipelago import supabase_auth
from archipelago.core.prompt_assembly import PromptPayloadAssembler
from archipelago.core.retrieval import TwoPassHybridRetriever
from archipelago.core.router import (
    OUT_OF_SCOPE_MESSAGE,
    QueryIntent,
    QueryRouter,
    RoutingTier,
    SECURITY_BOUNDARY_MESSAGE,
)
from archipelago.core.synthesis_service import SynthesisService

logger = logging.getLogger("archipelago.api")
logging.basicConfig(level=logging.INFO)

# Local development loads the ignored repository .env file. Deployed hosts
# provide the same values through their managed environment instead.
load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).resolve().parents[2]
PDF_DIR = BASE_DIR / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = BASE_DIR / "okf_graph.json"
DB_PATH = str(BASE_DIR / "okf_graph.db")

app = Flask(__name__)

_PUBLIC_AUTH_PATHS = frozenset({"/api/readiness", "/api/auth/config"})
_LIBRARIAN_OR_ADMIN_PATHS = frozenset({"/api/upload", "/api/users"})
_LIBRARIAN_OR_ADMIN_ROLES = frozenset({"librarian", "administrator"})

# Global instances initialized lazily or on startup
_router: Optional[QueryRouter] = None
_retriever: Optional[TwoPassHybridRetriever] = None
_assembler: Optional[PromptPayloadAssembler] = None
_synthesis: Optional[SynthesisService] = None
_concepts_data: Dict[str, Any] = {}
_kuzu_conn: Optional[Any] = None


def get_kuzu_connection() -> Optional[Any]:
    """Obtain or reuse KùzuDB connection safely."""
    global _kuzu_conn
    if _kuzu_conn is not None:
        return _kuzu_conn
    try:
        import kuzu
        db = kuzu.Database(DB_PATH, read_only=True)
        _kuzu_conn = kuzu.Connection(db)
        logger.info("Connected to KùzuDB at %s (read_only=True)", DB_PATH)
        return _kuzu_conn
    except Exception as exc:
        logger.info("Kùzu DB direct handle unavailable (%s); relying on in-memory concepts index.", exc)
        _kuzu_conn = None
        return None



def init_engine() -> None:
    """Initialize all runtime components."""
    global _router, _retriever, _assembler, _synthesis, _concepts_data

    # 1. Load concepts data from JSON
    if DATA_FILE.is_file():
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            nodes = raw.get("visualization", {}).get("nodes", []) or raw.get("nodes", [])
            for n in nodes:
                cid = n.get("id", "")
                if cid:
                    _concepts_data[cid] = n
            logger.info("Loaded %d concepts from %s", len(_concepts_data), DATA_FILE.name)
        except Exception as exc:
            logger.warning("Failed loading okf_graph.json: %s", exc)

    # 2. Initialize Core Modules
    conn = get_kuzu_connection()
    _router = QueryRouter()
    _retriever = TwoPassHybridRetriever(kuzu_conn=conn, concepts_data=_concepts_data)
    _assembler = PromptPayloadAssembler()
    _synthesis = SynthesisService()


init_engine()


# ── CORS Middleware ────────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
    return response


from archipelago.auth import load_user
app.before_request(load_user)

@app.before_request
def require_supabase_session() -> Response | None:
    """Protect deployed API routes with a Supabase session and role checks."""
    if request.method == "OPTIONS" or request.path in _PUBLIC_AUTH_PATHS:
        return None
    if not supabase_auth.is_auth_required():
        return None

    principal, error = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    if (
        (request.path in _LIBRARIAN_OR_ADMIN_PATHS or request.path.startswith("/api/users"))
        and principal.role not in _LIBRARIAN_OR_ADMIN_ROLES
    ):
        return jsonify({"error": "forbidden", "detail": "Librarian or administrator role required."}), 403
    g.archipelago_principal = principal
    return None


@app.route("/api/auth/config", methods=["GET"])
def api_auth_config() -> Response:
    """Return only browser-safe Supabase Auth settings."""
    return jsonify(supabase_auth.public_config())


@app.route("/api/auth/me", methods=["GET"])
def api_auth_me() -> Response:
    """Return the authenticated user's Archipelago role."""
    if not supabase_auth.is_auth_required():
        return jsonify({"authenticated": False, "auth_required": False})
    principal = getattr(g, "archipelago_principal", None)
    if principal is None:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({
        "authenticated": True,
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role,
    })


@app.route("/api/users", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/users/<user_id>", methods=["PUT", "DELETE", "OPTIONS"])
def api_manage_users(user_id=None) -> Response:
    """Manage users with role-based access for librarian and administrator."""
    if request.method == "OPTIONS":
        return Response("", 204)
    principal = getattr(g, "archipelago_principal", None)
    if principal is None:
        principal, auth_err = supabase_auth.authenticate_request(request)
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": auth_err or "Authentication required"}), 401

    if request.method == "GET":
        users, err = supabase_auth.list_managed_users(principal)
        if err:
            return jsonify({"error": "forbidden", "detail": err}), 403
        return jsonify({"users": users, "requester": {"role": principal.role, "user_id": principal.user_id}})

    elif request.method == "POST":
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.create_managed_user(principal, data)
        if err:
            return jsonify({"error": "bad_request", "detail": err}), 400
        return jsonify({"success": True, "user": user}), 201

    elif request.method == "PUT":
        if not user_id:
            return jsonify({"error": "missing_user_id"}), 400
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.update_managed_user(principal, user_id, data)
        if err:
            return jsonify({"error": "update_failed", "detail": err}), 400
        return jsonify({"success": True, "user": user})

    elif request.method == "DELETE":
        if not user_id:
            return jsonify({"error": "missing_user_id"}), 400
        ok, err = supabase_auth.delete_managed_user(principal, user_id)
        if err:
            return jsonify({"error": "delete_failed", "detail": err}), 400
        return jsonify({"success": True})

    return jsonify({"error": "method_not_allowed"}), 405



# ── Health & Readiness Probe ──────────────────────────────────────────────────
@app.route("/api/readiness", methods=["GET"])
def api_readiness() -> Response:
    """Health check endpoint reporting DB status, concept count, and LLM state."""
    llm_ready = False
    try:
        from archipelago.inference.llm_gateway import is_llm_available
        llm_ready = is_llm_available()
    except Exception:
        llm_ready = False

    return jsonify({
        "status": "ready",
        "graph": {
            "concept_count": len(_concepts_data),
            "kuzu_connected": _kuzu_conn is not None,
            "database_path": DB_PATH,
        },
        "models": {
            "synthesis_model": _synthesis.synthesis_model if _synthesis else "qwen/qwen3.8-max:free",
            "ingestion_model": _synthesis.ingestion_model if _synthesis else "lib-qwen:latest",
            "ollama_ready": llm_ready,
            "llm_ready": llm_ready,
        },
        "runtime": "production_docker",
    })


# ── Chat & Grounded Inference ─────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat() -> Response:
    """Primary inference endpoint executing the complete 3-Tier Guardrailed Pipeline."""
    req_data = request.get_json(silent=True) or {}
    query = req_data.get("query") or req_data.get("message") or ""
    stream = bool(req_data.get("stream") or request.args.get("stream") == "true")

    if not _router or not _retriever or not _assembler or not _synthesis:
        init_engine()

    assert _router is not None
    assert _retriever is not None
    assert _assembler is not None
    assert _synthesis is not None

    # Helper scoring function passed to router
    def score_query(term: str) -> tuple[float, Any]:
        hits = _retriever.resolve_anchor(term, top_k=1)
        if hits:
            cid, score = hits[0]
            cdata = _concepts_data.get(cid, {})
            name = cdata.get("name") or cdata.get("label") or cid
            exact = term.strip().lower() in (cid.lower(), name.lower())
            return score, {"id": cid, "exact_alias": exact}
        return 0.0, None

    # Step 1: Firewall & 3-Tier Routing
    routing_result = _router.route_query(query, retriever_fn=score_query)
    route = routing_result["route"]
    tier = routing_result["tier"]
    intent = routing_result.get("intent")
    norm_q = routing_result.get("normalized_query", query)

    # Handle Tier 3 / Rejections
    if route == "rejected":
        status_code = 400 if routing_result.get("is_malicious") else 400
        return jsonify({
            "status": "rejected",
            "tier": tier,
            "text": routing_result.get("message") or SECURITY_BOUNDARY_MESSAGE,
            "citations": [],
            "topology": None,
        }), status_code

    if route == "out_of_scope":
        return jsonify({
            "status": "out_of_scope",
            "tier": tier,
            "text": OUT_OF_SCOPE_MESSAGE,
            "citations": [],
            "topology": None,
        }), 200

    # Step 2: Handle Non-Graph Direct Intents
    if intent == QueryIntent.CATALOG_SHELF_ROUTING.value:
        try:
            from archipelago.inference.catalog_ops import subject_title_counts
            counts = subject_title_counts(limit=5)
            text_lines = ["### Institutional Library Holdings\n"]
            for c in counts:
                text_lines.append(f"- **{c.get('subject')}**: {c.get('title_count')} titles available in stacks")
            ans = "\n".join(text_lines)
        except Exception:
            ans = "The catalog shelf coordinates are located in Central Library Stack Room A (Floors 2 & 3)."
        return jsonify({"status": "success", "intent": intent, "text": ans, "citations": []}), 200

    if intent == QueryIntent.AUTH_GATEWAY.value:
        try:
            from archipelago.inference.eresource_credentials import format_credential_reply
            ans = format_credential_reply(norm_q)
        except Exception:
            ans = (
                "Institutional e-resources (NDLI, IEEE Xplore, Scopus, ScienceDirect) are accessible "
                "via the Central Library Portal using your institutional SSO credentials."
            )
        return jsonify({"status": "success", "intent": intent, "text": ans, "citations": []}), 200

    if intent == QueryIntent.MCQ_DIAGNOSTIC.value:
        anchor_hits = _retriever.resolve_anchor(norm_q, top_k=1)
        anchor_id = anchor_hits[0][0] if anchor_hits else "low_rank_adaptation"
        anchor_info = _concepts_data.get(anchor_id, {})
        anchor_name = anchor_info.get("name") or anchor_id
        prereqs = _retriever.get_upstream_prerequisites(anchor_id, max_hops=1)
        mcq_payload = _synthesis.generate_diagnostic_mcq(anchor_name, prereqs)
        return jsonify({"status": "success", "intent": intent, "quiz": mcq_payload}), 200

    # Step 3: Handle Tier 2 / TOPIC_SUGGESTION
    if route == "suggest_topics" or intent == QueryIntent.TOPIC_SUGGESTION.value:
        candidates = _retriever.suggest_topics(norm_q, top_k=5)
        suggestion_payload = _synthesis.generate_topic_suggestions(norm_q, candidates)
        return jsonify({
            "status": "suggest_topics",
            "tier": tier,
            "intent": QueryIntent.TOPIC_SUGGESTION.value,
            **suggestion_payload,
        }), 200

    # Step 4: Tier 1 Execute (GRAPH_SYNTHESIS)
    dual_ents = routing_result.get("dual_entities") or []
    path = None
    anchor_id = None
    anchor_name = ""
    difficulty = "intermediate"

    if dual_ents and len(dual_ents) >= 2:
        # Dual-Entity Shortest-Path Resolution (TC-04 Bug Fix)
        path = _retriever.find_shortest_path(dual_ents[0], dual_ents[1])
        anchor_hits = _retriever.resolve_anchor(dual_ents[0], top_k=1)
        if anchor_hits:
            anchor_id = anchor_hits[0][0]
            anchor_info = _concepts_data.get(anchor_id, {})
            anchor_name = anchor_info.get("name") or anchor_id
            difficulty = anchor_info.get("difficulty", "intermediate")
    else:
        anchor_hits = _retriever.resolve_anchor(norm_q, top_k=1)
        if anchor_hits:
            anchor_id = anchor_hits[0][0]
            anchor_info = _concepts_data.get(anchor_id, {})
            anchor_name = anchor_info.get("name") or anchor_info.get("label") or anchor_id
            difficulty = anchor_info.get("difficulty", "intermediate")

    if not anchor_id:
        # Fallback to topic suggestions if no anchor found
        candidates = _retriever.suggest_topics(norm_q, top_k=3)
        return jsonify({
            "status": "suggest_topics",
            "tier": RoutingTier.TIER_2_SUGGEST.value,
            **_synthesis.generate_topic_suggestions(norm_q, candidates),
        }), 200

    # Retrieve bounded upstream, downstream, and lineage chunks
    prereqs = _retriever.get_upstream_prerequisites(anchor_id, max_hops=2)
    unlocks = _retriever.get_downstream_unlocks(anchor_id, max_hops=2)
    chunks = _retriever.get_evidence_chunks(anchor_id, max_chunks=3)

    # Step 5: Isolated Context Assembly
    payload = _assembler.assemble_payload(
        query=norm_q,
        anchor_name=anchor_name,
        difficulty=difficulty,
        prerequisites=prereqs,
        unlocks=unlocks,
        chunks=chunks,
        path=path,
    )

    # Step 6: Local SLM Synthesis
    if stream:
        gen = _synthesis.synthesize_response(payload, stream=True)
        return Response(gen, mimetype="text/event-stream")

    response_data = _synthesis.synthesize_response(payload, stream=False)
    return jsonify({
        "status": "success",
        "tier": tier,
        "intent": QueryIntent.GRAPH_SYNTHESIS.value,
        **response_data,
    }), 200


# ── Fuzzy Topic Discovery Endpoint ────────────────────────────────────────────
@app.route("/api/topics/suggest", methods=["GET"])
def api_topic_suggest() -> Response:
    """Fuzzy concept discovery returning top 3-5 candidates with prerequisite roadmap."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    if not _retriever or not _synthesis:
        init_engine()

    assert _retriever is not None
    assert _synthesis is not None

    candidates = _retriever.suggest_topics(query, top_k=5)
    return jsonify(_synthesis.generate_topic_suggestions(query, candidates)), 200


# ── Diagnostic MCQ Evaluation Endpoint ────────────────────────────────────────
@app.route("/api/roadmap/quiz", methods=["POST"])
def api_roadmap_quiz() -> Response:
    """Evaluate diagnostic MCQ answers and produce a custom learning roadmap."""
    data = request.get_json(silent=True) or {}
    concept = data.get("concept", "Deep Learning")
    answers = data.get("answers", {})

    # Evaluate score
    total = len(answers) if answers else 3
    correct = sum(1 for v in answers.values() if str(v).upper() == "A") if answers else 2
    score = (correct / total) if total > 0 else 0.5

    roadmap = [
        {"step": 1, "concept": "Mathematical Foundations", "status": "Mastered" if score > 0.6 else "Review Required"},
        {"step": 2, "concept": "Linear Algebra & SVD", "status": "Mastered" if score > 0.8 else "In Progress"},
        {"step": 3, "concept": concept, "status": "Unlocked Ready for Study"},
    ]

    return jsonify({
        "concept": concept,
        "score": round(score, 2),
        "mastery": "Sufficient" if score >= 0.66 else "Needs Remediation",
        "custom_roadmap": roadmap,
    }), 200


@app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST"])
def api_chat_diagnostic_mcqs() -> Response:
    """Retrieve diagnostic MCQs and prerequisite sequence for target concept."""
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
        t_node = _concepts_data.get(target_id) or {}
        prereqs = [p.get("id") if isinstance(p, dict) else str(p) for p in (t_node.get("prerequisites") or [])]
        mcqs = generate_diagnostic_mcqs(target_id, prereq_ids=prereqs, num_questions=3, concepts_data=_concepts_data)
        chain = get_prerequisite_chain(target_id, _concepts_data)
        prereq_chain = [c for c in chain if c != target_id]
        immediate_y = prereq_chain[-1] if prereq_chain else target_id
        initial_q = generate_single_mcq_on_the_spot(immediate_y, _concepts_data, q_index=1)

        return jsonify({
            "success": True,
            "available": bool(mcqs),
            "target_concept": target_id,
            "chain": chain,
            "prereq_chain": prereq_chain,
            "immediate_prerequisite": immediate_y,
            "initial_question": initial_q,
            "mcqs": mcqs,
        }), 200
    except Exception as exc:
        logger.warning("Diagnostic MCQ API error: %s", exc)
        return jsonify({
            "success": False,
            "available": False,
            "target_concept": target_id,
            "mcqs": [],
            "badge": "Personalized assessment temporarily unavailable.",
        }), 200


@app.route("/api/chat/verify-mcq", methods=["POST"])
def api_chat_verify_mcq() -> Response:
    """Validate user answers for diagnostic MCQs and calculate prerequisite mastery."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    mcqs = data.get("mcqs") or []
    answers = data.get("answers") or {}
    target_id = data.get("target_concept") or ""

    from archipelago.inference.diagnostic_mcq import (
        evaluate_diagnostic_mcqs,
        generate_diagnostic_mcqs,
    )
    if not mcqs and target_id:
        mcqs = generate_diagnostic_mcqs(target_id, num_questions=3, concepts_data=_concepts_data)

    result = evaluate_diagnostic_mcqs(mcqs, answers, target_concept_id=target_id, concepts_data=_concepts_data)
    return jsonify(result), 200


@app.route("/api/chat/adaptive-step", methods=["POST"])
def api_chat_adaptive_step() -> Response:
    """Execute an on-the-spot adaptive leap-back skip-list step."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    from archipelago.inference.diagnostic_mcq import execute_adaptive_step
    result = execute_adaptive_step(data, concepts_data=_concepts_data)
    return jsonify(result), 200


@app.route("/api/chat/telemetry", methods=["POST"])
def api_chat_telemetry() -> Response:
    """Track choice analytics (Personalized vs Normal graph selections)."""
    try:
        data = request.get_json(silent=True) or {}
        event = data.get("event", "graph_choice")
        mode = data.get("mode", "unknown")
        concept_id = data.get("concept_id", "")
        logger.info("[TELEMETRY] event=%s mode=%s concept=%s", event, mode, concept_id)
        return jsonify({"logged": True, "event": event, "mode": mode}), 200
    except Exception as exc:
        return jsonify({"logged": False, "error": str(exc)}), 200


# ── Catalog Shelf Search Endpoint ─────────────────────────────────────────────
@app.route("/api/catalog/search", methods=["GET"])
def api_catalog_search() -> Response:
    """Search Koha/OPAC physical inventory by title, author, or subject."""
    q = request.args.get("q", "").strip().lower()
    results = []

    conn = get_kuzu_connection()
    if conn is not None:
        try:
            res = conn.execute(
                f"MATCH (r:Resource) WHERE lower(r.title) CONTAINS '{q}' OR lower(r.author) CONTAINS '{q}' "
                "RETURN r.id, r.title, r.author, r.location, r.available_copies LIMIT 5"
            )
            while res.has_next():
                row = res.get_next()
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "author": row[2],
                    "shelf_location": row[3] or "Main Library Stack A",
                    "available_copies": row[4] or 1,
                })
        except Exception as exc:
            logger.debug("Kuzu resource search notice: %s", exc)

    if not results:
        # Fallback response for demo queries
        results = [
            {
                "title": f"Principles of {q.title() if q else 'Computer Science'}",
                "author": "Institutional Academic Press",
                "shelf_location": "Floor 2, Stack 14B, Call #QA76.87",
                "available_copies": 3,
            }
        ]

    return jsonify({"query": q, "results": results}), 200


# ── E-Resources Credentials Endpoint ──────────────────────────────────────────
@app.route("/api/eresources", methods=["GET"])
def api_eresources() -> Response:
    """Return institutional links and access portals for IEEE, NDLI, Scopus."""
    try:
        from archipelago.inference.eresource_credentials import load_credentials
        creds = load_credentials()
    except Exception:
        creds = {}

    portals = [
        {"name": "National Digital Library of India (NDLI)", "url": "https://ndl.iitkgp.ac.in", "access": "Institutional SSO"},
        {"name": "IEEE Xplore Digital Library", "url": "https://ieeexplore.ieee.org", "access": "Campus IP / VPN Proxy"},
        {"name": "Scopus & ScienceDirect (Elsevier)", "url": "https://www.sciencedirect.com", "access": "Institutional Passkey"},
    ]
    return jsonify({"institutional_portals": portals, "overlay": creds}), 200


# ── Live PDF Ingestion Endpoint ───────────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def api_upload() -> Response:
    """Queue a PDF/Markdown/text upload through the canonical staged worker."""
    if "file" not in request.files and "pdf" not in request.files:
        return jsonify({"error": "No file uploaded. Expected 'file' or 'pdf' form field."}), 400

    uploaded_file = request.files.get("file") or request.files.get("pdf")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "Invalid filename"}), 400

    from werkzeug.utils import secure_filename
    from ingestion_worker import get_worker, job_store

    filename = secure_filename(Path(uploaded_file.filename).name)
    allowed = (".pdf", ".md", ".markdown", ".txt")
    if not filename.lower().endswith(allowed):
        return jsonify({"error": "Supported formats: PDF, Markdown (.md), plain text (.txt)"}), 400

    job = job_store.create_job(filename)
    upload_path = job_store.job_dir(job.job_id) / f"upload{Path(filename).suffix.lower()}"
    uploaded_file.save(str(upload_path))
    get_worker().enqueue(job.job_id)
    logger.info("Queued upload %s as ingestion job %s", filename, job.job_id)

    return jsonify({
        "status": "queued",
        "job_id": job.job_id,
        "filename": filename,
        "message": f"Document '{filename}' queued for staged ingestion.",
    }), 202


# ── Document Inventory Endpoint ───────────────────────────────────────────────
@app.route("/api/documents", methods=["GET"])
def api_documents() -> Response:
    """Return all indexed documents in the active library."""
    docs = []
    conn = get_kuzu_connection()
    if conn is not None:
        try:
            res = conn.execute("MATCH (d:Document) RETURN d.id, d.title LIMIT 50")
            while res.has_next():
                row = res.get_next()
                docs.append({"doc_id": row[0], "title": row[1] or row[0]})
        except Exception:
            pass

    if not docs:
        for f in PDF_DIR.glob("*.pdf"):
            docs.append({"doc_id": f.name, "title": f.stem.replace("_", " ")})

    return jsonify({"total_documents": len(docs), "documents": docs}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5051"))
    app.run(host="0.0.0.0", port=port, debug=False)
