"""Flask routes: CORS, PDFs, readiness, ingestion API, diagnostics."""
from __future__ import annotations

import json
import os
import re
import secrets
import time
from pathlib import Path

from flask import jsonify, send_from_directory, request, redirect

import kuzu

from archipelago.inference.graph_lock import graph_lock
from ingestion_jobs import JobStatus
from ingestion_worker import job_store, get_worker
from archipelago.auth import require_librarian, librarian_token_expected
from archipelago.inference import state as st
import torch

@st.app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response


@st.app.route("/pdfs/<path:filename>")
def serve_pdf(filename):
    """Serve local papers/textbooks from the pdfs folder.

    When the file is not on disk (slim deployments that don't ship the corpus
    PDFs), redirect to the canonical public source (arXiv / mml-book) so the
    reading pane can still stream the full document.
    """
    local = Path(st.PDF_DIR) / filename
    if local.is_file():
        return send_from_directory(str(st.PDF_DIR), filename)
    remote = REMOTE_PDF_SOURCES.get(Path(filename).name)
    if remote:
        return redirect(remote, code=302)
    return jsonify({"error": f"PDF not found: {filename}"}), 404


# Canonical public URLs for the corpus documents (all openly licensed/hosted:
# arXiv preprints and the officially-free MML book). Used as a streaming
# fallback so full texts never need to live on this machine.
REMOTE_PDF_SOURCES = {
    "Vaswani2017_Attention_Is_All_You_Need.pdf": "https://arxiv.org/pdf/1706.03762",
    "Hu2021_LoRA.pdf": "https://arxiv.org/pdf/2106.09685",
    "Lewis2020_RAG.pdf": "https://arxiv.org/pdf/2005.11401",
    "Devlin2018_BERT.pdf": "https://arxiv.org/pdf/1810.04805",
    "Edge2024_GraphRAG.pdf": "https://arxiv.org/pdf/2404.16130",
    "Deisenroth_Math_For_ML.pdf": "https://mml-book.github.io/book/mml-book.pdf",
}


# ── Shared chats: tiny file-backed store (no DB, no auth beyond size caps) ──
SHARES_DIR = Path(st.BASE_DIR) / "shares"
_SHARE_MAX_BYTES = 512 * 1024
_SHARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")


@st.app.route("/api/share", methods=["POST"])
def create_share():
    """Persist a conversation snapshot and return a share id."""
    data = request.get_json(silent=True) or {}
    history = data.get("history")
    if not isinstance(history, list) or not history:
        return jsonify({"error": "history must be a non-empty list"}), 400
    clean = []
    for m in history[:200]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            clean.append({"role": role, "content": content[:20000]})
    if not clean:
        return jsonify({"error": "no valid messages in history"}), 400
    payload = {
        "title": str(data.get("title") or "")[:120],
        "history": clean,
        "created_at": time.time(),
    }
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode("utf-8")) > _SHARE_MAX_BYTES:
        return jsonify({"error": "conversation too large to share"}), 413
    share_id = secrets.token_urlsafe(9)
    SHARES_DIR.mkdir(exist_ok=True)
    (SHARES_DIR / f"{share_id}.json").write_text(raw, encoding="utf-8")
    return jsonify({"share_id": share_id, "url": f"/?share={share_id}"})


@st.app.route("/api/share/<share_id>", methods=["GET"])
def get_share(share_id):
    """Fetch a shared conversation snapshot by id."""
    if not _SHARE_ID_RE.match(share_id or ""):
        return jsonify({"error": "invalid share id"}), 400
    path = SHARES_DIR / f"{share_id}.json"
    if not path.is_file():
        return jsonify({"error": "share not found"}), 404
    try:
        return jsonify(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return jsonify({"error": "share unreadable"}), 500



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


@st.app.route("/api/ingest/capabilities", methods=["GET"])
def ingestion_capabilities():
    """Advertise upload API capabilities (librarian-only mutations)."""
    return jsonify({
        "upload_api_enabled": True,
        "delete_api_enabled": True,
        "librarian_only": True,
        "student_upload_enabled": False,
        "auth_required": bool(librarian_token_expected()),
        "list_documents_api": "/api/documents",
        "delete_document_api": "DELETE /api/documents/<doc_id>",
        "ranked_resources_api": "GET /api/rank/resources?q=&kind=&limit=",
        "max_file_size_mb": 50,
        "supported_formats": ["pdf", "md", "markdown", "txt"],
        "merge_mode": "full_rebuild_from_merged_okf_results",
        "metadata_fields": [
            "title", "authors", "kind", "shelf_location", "license_mode",
            "isbn", "subject", "year", "url",
        ],
        "note": (
            "Upload/delete is only available from the Graph UI Librarian "
            "console with a librarian token. Student chat cannot mutate the corpus. "
            "Each upload merges into okf_results and rebuilds the multi-doc live graph "
            "(peers are retained; a safety guard aborts if prior docs would be wiped)."
        ),
    }), 200


@st.app.route("/api/rank/resources", methods=["GET"])
def rank_resources_api():
    """Full or top-N ranked books/papers from inventory + librarian seeds."""
    from flask import request, jsonify
    from archipelago.inference.unified_ranking import list_all_ranked, rank_resources

    q = str(request.args.get("q") or request.args.get("topic") or "").strip()
    kind = request.args.get("kind") or None
    if kind:
        kind = str(kind).strip().lower() or None
    try:
        limit = int(request.args.get("limit") or 4)
    except (TypeError, ValueError):
        limit = 4
    full = str(request.args.get("full") or "").lower() in ("1", "true", "yes", "on")
    if not q:
        return jsonify({"error": "q (topic) is required", "results": []}), 400
    if full:
        results = list_all_ranked(q, kind=kind, limit=min(max(limit, 1), 200))
    else:
        results = rank_resources(q, kind=kind, limit=min(max(limit, 1), 4))
    return jsonify({
        "query": q,
        "kind": kind,
        "count": len(results),
        "results": results,
    }), 200


@st.app.route("/api/ingest", methods=["POST"])
@require_librarian
def ingest_upload():
    """Librarian-only: accept a document upload (PDF/MD/TXT), create a job and enqueue it."""
    import time
    from werkzeug.utils import secure_filename

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    f = request.files["file"]
    if not f or f.filename == "":
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(f.filename or "upload.pdf")
    lower = filename.lower()
    allowed = (".pdf", ".md", ".markdown", ".txt")
    if not any(lower.endswith(ext) for ext in allowed):
        return jsonify({
            "error": "Supported formats: PDF, Markdown (.md), plain text (.txt)",
        }), 400

    # Check file size (<= 50 MB)
    f.seek(0, 2)
    size_bytes = f.tell()
    f.seek(0)
    if size_bytes > 50 * 1024 * 1024:
        return jsonify({"error": "File exceeds 50 MB limit"}), 413

    # Create job and quarantine the upload (preserve extension for pipeline)
    job = job_store.create_job(filename)
    job_dir = job_store.job_dir(job.job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower().replace(".markdown", ".md") or ".pdf"
    if ext not in (".pdf", ".md", ".txt"):
        ext = ".pdf"
    upload_path = job_dir / f"upload{ext}"
    f.save(str(upload_path))
    # Marker so the worker always finds the quarantined source
    (job_dir / "upload_source_name.txt").write_text(filename, encoding="utf-8")

    # Optional librarian metadata for shelf / inventory / license policy.
    meta_keys = (
        "title", "authors", "kind", "shelf_location", "location",
        "license_mode", "isbn", "subject", "year", "url",
    )
    meta: dict = {}
    for key in meta_keys:
        val = request.form.get(key)
        if val is not None and str(val).strip():
            meta[key] = str(val).strip()
    if meta:
        import json as _json
        (job_dir / "meta.json").write_text(
            _json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Enqueue and start worker
    worker = get_worker()
    worker.enqueue(job.job_id)

    return jsonify({
        "job_id": job.job_id,
        "status": "queued",
        "filename": filename,
        "format": ext.lstrip("."),
        "merge_mode": "full_rebuild_from_merged_okf_results",
        "metadata": meta or None,
    }), 202


@st.app.route("/api/ingest/<job_id>", methods=["GET"])
def ingest_status(job_id):
    """Return job status, progress per stage, elapsed time, and result."""
    import time
    from datetime import datetime, timezone

    record = job_store.get_job(job_id)
    if record is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    # Compute elapsed seconds
    try:
        created = datetime.fromisoformat(record.created_at)
        elapsed = (datetime.now(timezone.utc) - created).total_seconds()
    except Exception:
        elapsed = None

    return jsonify({
        "job_id":          record.job_id,
        "status":          record.status.value,
        "source_filename": record.source_filename,
        "created_at":      record.created_at,
        "updated_at":      record.updated_at,
        "elapsed_seconds": elapsed,
        "progress":        record.progress,
        "error":           record.error,
        "result":          record.result,
        "graph_version":   record.graph_version,
    }), 200


@st.app.route("/api/ingest/<job_id>/cancel", methods=["GET", "POST"])
@require_librarian
def ingest_cancel(job_id):
    """Librarian-only: request cancellation of a running job."""
    record = job_store.cancel_job(job_id)
    if record is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404
    return jsonify({
        "job_id": record.job_id,
        "status": record.status.value,
        "cancelled": record.cancelled,
    }), 200


@st.app.route("/api/ingest", methods=["GET"])
def ingest_list():
    """List all ingestion jobs."""
    return jsonify({"jobs": job_store.list_jobs()}), 200


from archipelago.inference.routes_diagnostic import register_diagnostic_routes
from archipelago.inference.routes_librarian import register_librarian_routes

register_diagnostic_routes()
register_librarian_routes()


def estimate_ingestion_time(file_size_bytes: int, filename: str) -> dict[str, Any]:
    """Estimate ingestion time based on file size and extension (SCH-1)."""
    from typing import Any
    ext = Path(filename).suffix.lower()
    if ext in (".md", ".markdown", ".txt"):
        seconds = 5
    else:
        # PDF files: base of 20 seconds, plus 15 seconds per MB
        size_mb = file_size_bytes / (1024 * 1024)
        seconds = int(20 + size_mb * 15)

    return {
        "estimated_seconds": seconds,
        "estimated_time_formatted": f"{seconds} seconds",
    }


def pdf_available(doc_id: str) -> bool:
    """Check if the PDF file exists locally in the PDF directory."""
    local = Path(st.PDF_DIR) / doc_id
    return local.is_file()


def resolve_pdf_file(doc_id: str) -> Path | None:
    """Resolve a doc_id to a local PDF Path, or None if not found.

    Searches the PDF directory for the file. Accepts both bare filenames
    (``Hu2021_LoRA.pdf``) and nested paths (``textbooks/mml.pdf``).
    """
    if not doc_id:
        return None
    local = Path(st.PDF_DIR) / doc_id
    if local.is_file():
        return local
    # Try stripping leading slashes (defensive)
    local = Path(st.PDF_DIR) / doc_id.lstrip("/\\")
    if local.is_file():
        return local
    return None


