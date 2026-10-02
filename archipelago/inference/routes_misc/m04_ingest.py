"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import threading
from pathlib import Path
from flask import jsonify, send_from_directory, request, redirect
from ingestion_jobs import JobStatus
from ingestion_worker import job_store, get_worker, graph_lock
from archipelago.auth import require_librarian, librarian_token_expected
from archipelago.inference import state as st
from archipelago import supabase_auth


@st.app.route("/api/ingest/capabilities", methods=["GET"])
def ingestion_capabilities():
    """Advertise upload API capabilities (librarian-only mutations)."""
    return jsonify({
        "upload_api_enabled": True,
        "delete_api_enabled": True,
        "librarian_only": True,
        "student_upload_enabled": False,
        "auth_required": bool(librarian_token_expected()) or supabase_auth.is_auth_required(),
        "list_documents_api": "/api/documents",
        "delete_document_api": "DELETE /api/documents/<doc_id>",
        "max_file_size_mb": 50,
        "supported_formats": ["pdf", "md", "markdown", "txt"],
        "note": (
            "Upload/delete is only available from the Graph UI Librarian "
            "console with a librarian token. Student chat cannot mutate the corpus."
        ),
    }), 200


@st.app.route("/api/ingest", methods=["POST"])
@require_librarian
def ingest_upload():
    """Librarian-only: accept a document upload (PDF/MD/TXT), create a job and enqueue it."""
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

    file_bytes = f.read()

    # Use the production staged worker used by the integration tests. The old
    # librarian worker had a separate schema, a 15-chunk cap, and reported a
    # successful staged job even when extraction returned zero concepts.
    job = job_store.create_job(filename)
    upload_path = job_store.job_dir(job.job_id) / f"upload{Path(filename).suffix.lower()}"
    upload_path.write_bytes(file_bytes)
    get_worker().enqueue(job.job_id)

    ext = Path(filename).suffix.lower().replace(".markdown", ".md") or ".pdf"
    return jsonify({
        "job_id": job.job_id,
        "status": "queued",
        "filename": filename,
        "format": ext.lstrip("."),
    }), 202


@st.app.route("/api/ingest/<job_id>", methods=["GET"])
def ingest_status(job_id):
    """Return only the canonical ingestion job status and result."""
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
        "status":          record.status.value.lower(),
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


class SlidingWindowLimiter:
    """Simple in-memory sliding window rate limiter."""
    def __init__(self):
        self._windows: dict = {}
        self._lock = threading.Lock()

    def check(self, key: str, per_min: int = 10, burst: int = 5) -> tuple:
        import time as _time
        now = _time.time()
        with self._lock:
            window = self._windows.setdefault(key, [])
            window[:] = [t for t in window if now - t < 60]
            if len(window) >= per_min:
                return False, {"remaining": 0, "retry_after": int(60 - (now - window[0]))}
            window.append(now)
            return True, {"remaining": per_min - len(window)}


_ingest_limiter = SlidingWindowLimiter()


@st.app.route("/api/ingest/index", methods=["POST"])
@require_librarian
def ingest_index():
    """TOC-only ingestion: create Document + Concept stubs without a physical PDF."""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
    allowed, meta = _ingest_limiter.check(f"ingest:{client_ip}", per_min=10, burst=5)
    if not allowed:
        return jsonify({"error": "rate_limit_exceeded", "detail": "Too many ingestion requests", **meta}), 429

    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id") or data.get("book_id") or ""
    title = data.get("title") or doc_id
    chapters = data.get("chapters") or []
    if not doc_id:
        return jsonify({"error": "doc_id is required"}), 400

    if not isinstance(chapters, list) or not chapters or len(chapters) > 1000:
        return jsonify({"error": "chapters must contain 1–1000 entries"}), 400

    try:
        job = job_store.create_job(source_filename=f"index:{doc_id}")
        from ingestion_worker import get_worker
        worker = get_worker()
        worker._process_index_job(job.job_id, {"doc_id": doc_id, "title": title, "chapters": chapters})
        current = job_store.get_job(job.job_id)
        if current is None or current.status != JobStatus.COMPLETE:
            return jsonify({"job_id": job.job_id, "status": "failed", "error": current.error if current else "Index ingestion failed"}), 500
        return jsonify({"job_id": job.job_id, "status": "complete", "doc_id": doc_id, "result": current.result}), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def estimate_ingestion_time(file_size_bytes: int, filename: str) -> dict[str, Any]:
    """Estimate ingestion time based on file size and extension."""
    ext = Path(filename).suffix.lower()
    size_mb = file_size_bytes / (1024 * 1024)
    if ext == ".pdf":
        secs = int(max(15, 10 + size_mb * 22))
    elif ext in (".md", ".markdown", ".txt"):
        secs = int(max(5, size_mb * 12))
    else:
        secs = int(max(10, size_mb * 15))

    if secs < 60:
        fmt = f"{secs} seconds"
    else:
        fmt = f"{secs // 60}m {secs % 60}s"

    return {
        "estimated_seconds": secs,
        "estimated_time_formatted": fmt,
    }
