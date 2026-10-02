"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
import os
import requests as _requests
from .merged01_repo_root import BASE_DIR, _inference_auth_headers, app  # noqa: F401
from .merged06_chat_proxy import _inference_base  # noqa: F401


@app.route("/api/librarian/upload", methods=["POST", "OPTIONS"])
def librarian_upload():
    """Compatibility alias for the canonical staged ingestion pipeline."""
    if request.method == "OPTIONS":
        return ("", 204)
    return proxy_ingest_upload()


@app.route("/api/librarian/jobs/<job_id>", methods=["GET", "OPTIONS"])
def librarian_job_status(job_id: str):
    """Compatibility alias for canonical ingestion status."""
    if request.method == "OPTIONS":
        return ("", 204)
    return proxy_ingest_status(job_id)


@app.route("/api/librarian/staging/review", methods=["GET", "OPTIONS"])
def librarian_staging_review():
    """Retired review endpoint; canonical jobs publish only after full success."""
    if request.method == "OPTIONS":
        return ("", 204)
    return jsonify({"error": "staging review is retired", "use": "/api/ingest/<job_id>"}), 410


@app.route("/api/librarian/staging/publish", methods=["POST", "OPTIONS"])
def librarian_staging_publish():
    """Retired staging publish endpoint; uploads use the canonical worker."""
    if request.method == "OPTIONS":
        return ("", 204)
    return jsonify({"error": "manual staging publish is retired", "use": "/api/ingest"}), 410


@app.route("/api/graph/subgraph", methods=["GET", "OPTIONS"])
def graph_subgraph():
    """Serve bounded subgraph with styling metadata for interactive visualization."""
    if request.method == "OPTIONS":
        return ("", 204)

    target_id = request.args.get("target_id") or request.args.get("concept_id") or "linear_algebra"
    secondary_target_id = request.args.get("secondary_target_id")
    mode = request.args.get("mode") or "mode_c"
    max_nodes = int(request.args.get("max_nodes", 10))
    min_nodes = int(request.args.get("min_nodes", 5))

    from archipelago.graph.subgraph import generate_bounded_subgraph
    from archipelago.graph.engine import KuzuGraphEngine

    db_path = BASE_DIR / "okf_graph.db"
    conn = None
    engine = None
    if db_path.exists():
        try:
            engine = KuzuGraphEngine(db_path=db_path, read_only=True)
            conn = engine.conn
        except Exception:
            pass

    try:
        subgraph = generate_bounded_subgraph(
            target_id=target_id,
            secondary_target_id=secondary_target_id,
            mode=mode,
            max_nodes=max_nodes,
            min_nodes=min_nodes,
            kuzu_conn=conn,
        )
        data = subgraph.to_dict()

        # Enrich nodes with difficulty color and badge
        diff_colors = {
            "foundational": "#10b981",  # emerald green
            "intermediate": "#3b82f6",  # blue
            "advanced": "#8b5cf6",      # purple
            "expert": "#ec4899",        # pink
        }
        for n in data.get("nodes", []):
            diff = (n.get("difficulty") or "intermediate").lower()
            n["color"] = diff_colors.get(diff, "#3b82f6")
            n["badge"] = f"[{diff.capitalize()}]"

        # Enrich edge semantics
        edge_styles = {
            "REQUIRES": {"style": "solid", "color": "#f59e0b", "label": "REQUIRES (Prerequisite)"},
            "UNLOCKS": {"style": "dashed", "color": "#10b981", "label": "UNLOCKS (Progression)"},
            "RELATED": {"style": "dotted", "color": "#9ca3af", "label": "RELATED (Association)"},
            "PROVIDES_TEXT": {"style": "dashed", "color": "#06b6d4", "label": "PROVIDES_TEXT"},
            "MENTIONS": {"style": "dotted", "color": "#64748b", "label": "MENTIONS"},
        }
        for e in data.get("edges", []):
            rel = (e.get("relation") or "REQUIRES").upper()
            style_info = edge_styles.get(rel, {"style": "solid", "color": "#f59e0b", "label": rel})
            e["style"] = style_info["style"]
            e["color"] = style_info["color"]
            e["label"] = style_info["label"]

        return data, 200
    except Exception as exc:
        app.logger.warning("Error generating subgraph: %s", exc)
        return {"error": f"Subgraph generation failed: {exc}"}, 500
    finally:
        if engine:
            try:
                engine.close()
            except Exception:
                pass


@app.route("/api/ingest", methods=["POST", "OPTIONS"])
def proxy_ingest_upload():
    """Proxy multipart file upload to inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        files = {k: (v.filename, v.stream, v.content_type) for k, v in request.files.items()}
        headers = {}
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
        upstream = _requests.post(f"{base}/api/ingest", files=files, data=request.form, headers=headers, timeout=60)
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502


@app.route("/api/ingest/<job_id>", methods=["GET", "OPTIONS"])
def proxy_ingest_status(job_id):
    """Proxy ingestion job status."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        upstream = _requests.get(
            f"{base}/api/ingest/{job_id}",
            headers=_inference_auth_headers(),
            timeout=10,
        )
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502


@app.route("/api/ingest/<job_id>/cancel", methods=["POST", "GET", "OPTIONS"])
def proxy_ingest_cancel(job_id):
    """Proxy ingestion job cancellation."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        headers = {}
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
        upstream = _requests.post(f"{base}/api/ingest/{job_id}/cancel", headers=headers, timeout=10)
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502


@app.route("/api/documents", methods=["GET", "OPTIONS"])
def proxy_documents_list():
    """Proxy document list."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        upstream = _requests.get(f"{base}/api/documents", headers=_inference_auth_headers(), timeout=10)
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502


@app.route("/api/documents/<path:doc_id>", methods=["DELETE", "OPTIONS"])
def proxy_document_delete(doc_id):
    """Proxy document deletion."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        headers = {}
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
        upstream = _requests.delete(f"{base}/api/documents/{doc_id}", headers=headers, params=request.args, timeout=30)
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502


if __name__ == "__main__":
    port = int(os.environ.get("ARCHIPELAGO_CHAT_PORT", os.environ.get("PORT", "5152")))
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Archipelago Chat UI Server                      ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Landing:      http://localhost:{port}/            ║")
    print(f"║  Chat:         http://localhost:{port}/chat        ║")
    print(f"║  Library:      http://localhost:{port}/library     ║")
    print(f"║  Performance:  http://localhost:{port}/performance ║")
    print(f"║  Safety:       http://localhost:{port}/safety      ║")
    print("╚══════════════════════════════════════════════════╝\n")
    app.run(host=os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=port, debug=False)
