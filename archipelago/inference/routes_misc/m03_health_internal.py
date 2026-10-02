"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from flask import jsonify, send_from_directory, request, redirect
import kuzu
from ingestion_worker import job_store, get_worker, graph_lock
from archipelago.auth import require_librarian, librarian_token_expected
from archipelago.inference import state as st


@st.app.route("/api/readiness", methods=["GET"])
def readiness():
    """Lightweight health contract for the UI and test harness.

    It reports what is available instead of claiming that a model is ready just
    because a background loader was started.  Ollama is intentionally reported
    as configured (not synchronously probed) so this endpoint remains fast.
    """
    graph_ok = False
    graph_error = None
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            res = conn.execute("MATCH (c:Concept) RETURN count(c)")
            graph_ok = res.has_next()
    except Exception as e:
        graph_error = str(e)

    payload = {
        "ready": bool(graph_ok and st.CONCEPTS_DATA),
        "graph": {"ready": graph_ok, "concept_count": len(st.CONCEPTS_DATA), "error": graph_error},
        "retrieval": {
            "embedding_ready": st.use_embeddings,
            "lexical_fallback": True,
            "semantic_threshold": st.SEMANTIC_ANCHOR_THRESHOLD,
            "lexical_threshold": st.LEXICAL_ANCHOR_THRESHOLD,
        },
        "synthesis": {
            "default_model": st.DEFAULT_OLLAMA_MODEL,
            "mode": "optional_after_retrieval",
            "aura_compatibility_loaded": st.aura_loaded,
        },
        "ingestion": {
            "upload_api_enabled": True,
            "delete_api_enabled": True,
            "librarian_only": True,
            "student_upload_enabled": False,
            "auth_required": bool(librarian_token_expected()),
            "worker_thread_alive": False,  # will be updated dynamically below
        },
        "roles": {
            "chat": "student",
            "graph_browse": "student",
            "graph_librarian": "librarian",
        },
    }
    try:
        from ingestion_worker import get_worker
        payload["ingestion"]["worker_thread_alive"] = get_worker().is_alive()
    except Exception:
        pass
    return jsonify(payload), (200 if payload["ready"] else 503)


@st.app.route("/api/internal/close-graph", methods=["POST", "OPTIONS"])
def close_graph_internal():
    """Localhost-only: drop the live Kùzu handle so another process can os.replace the file."""
    if request.method == "OPTIONS":
        return ("", 204)
    remote = request.remote_addr or ""
    if remote not in ("127.0.0.1", "::1"):
        return jsonify({"error": "localhost only"}), 403
    try:
        import archipelago.inference.state as _st
        old = getattr(_st, "_db", None)
        _st._db = None
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
        return jsonify({"ok": True, "closed": old is not None}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@st.app.route("/api/internal/reload-graph", methods=["POST", "OPTIONS"])
def reload_graph_internal():
    """Localhost-only: reopen Kùzu after an atomic swap and rebuild concept embeddings."""
    if request.method == "OPTIONS":
        return ("", 204)
    remote = request.remote_addr or ""
    if remote not in ("127.0.0.1", "::1"):
        return jsonify({"error": "localhost only"}), 403
    embeddings_only = str(request.args.get("embeddings_only") or "").lower() in (
        "1", "true", "yes",
    )
    if not embeddings_only:
        try:
            st.reload_db()
        except Exception as exc:
            return jsonify({"error": f"reload_db failed: {exc}"}), 500
    embeddings_rebuilt = False
    embed_warning = None
    try:
        from archipelago.inference.embeddings import build_concept_embeddings
        build_concept_embeddings()
        embeddings_rebuilt = True
    except Exception as exc:
        embed_warning = str(exc)
    return jsonify({
        "ok": True,
        "concepts": len(getattr(st, "CONCEPTS_DATA", {}) or {}),
        "embeddings_rebuilt": embeddings_rebuilt,
        "embed_warning": embed_warning,
    }), 200
