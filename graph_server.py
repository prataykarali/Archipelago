"""Staff-restricted Graph UI and API service."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote

import requests
from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory

from src.archipelago import supabase_auth

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "okf_graph.json"
STATIC_DIR = BASE_DIR / "graph_ui"
_ASSET_ROOTS = tuple(path for path in (BASE_DIR / "buttons", BASE_DIR / "ui" / "assets") if path.is_dir())
_PUBLIC_AUTH_PATHS = frozenset({"/api/auth/config", "/api/auth/me", "/api/readiness", "/api/health"})

app = Flask(__name__, static_folder=str(STATIC_DIR))


@app.before_request
def enforce_graph_auth():
    """Verify staff identity server-side before serving graph data or UI."""
    if request.method == "OPTIONS":
        return None
    if request.path.startswith(("/ui/assets/", "/buttons/")) or request.path in _PUBLIC_AUTH_PATHS:
        return None
    if not supabase_auth.is_auth_required():
        return None

    principal, error = supabase_auth.authenticate_request(request)
    if principal is not None and principal.role in {"librarian", "administrator"}:
        g.archipelago_principal = principal
        return None
    if principal is None and request.path in {"/", "/archipelago_graph.html"}:
        config = supabase_auth.public_config()
        chat_origin = config.get("chatUrl")
        graph_origin = config.get("graphUrl") or request.host_url.rstrip("/")
        if chat_origin:
            target = f"{graph_origin}{request.full_path.rstrip('?')}"
            return redirect(f"{chat_origin}/login?next={quote(target, safe='')}", code=302)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    return jsonify({"error": "forbidden", "detail": "Librarian or administrator role required"}), 403


@app.after_request
def add_cors_headers(response):
    allowed_origin = os.environ.get("ARCHIPELAGO_ALLOWED_ORIGIN", "*")
    response.headers["Access-Control-Allow-Origin"] = allowed_origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,HEAD,POST,OPTIONS"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


def load_graph() -> dict:
    """Load the canonical graph export for this response."""
    with DATA_FILE.open(encoding="utf-8") as graph_file:
        return json.load(graph_file)


@app.route("/api/auth/config", methods=["GET"])
def auth_config():
    return jsonify(supabase_auth.public_config())


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    if not supabase_auth.is_auth_required():
        return jsonify({"authenticated": False, "auth_required": False})
    principal, error = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    return jsonify({
        "authenticated": True,
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role,
    })


@app.route("/api/readiness", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def readiness():
    return jsonify({"ready": DATA_FILE.is_file()})


@app.route("/api/graph")
def api_graph():
    data = load_graph()
    visualization = data.get("visualization", {})
    nodes = visualization.get("nodes", data.get("nodes", []))
    raw_edges = data.get("edges", [])
    edges = [{
        "id": edge.get("id", f"e{index}"),
        "source": edge.get("from_id") or edge.get("source"),
        "target": edge.get("to_id") or edge.get("target"),
        "relation": edge.get("relation"),
        "edge_type": edge.get("edge_type"),
        "source_ref": edge.get("source", ""),
    } for index, edge in enumerate(raw_edges)]
    return jsonify({"nodes": nodes, "edges": edges, "stats": data.get("stats", {}), "clusters": visualization.get("clusters", {})})


@app.route("/api/schema")
def api_schema():
    data = load_graph()
    return jsonify(data.get("schema", {"version": "1.6", "nodes": [], "edges": []}))


@app.route("/api/node/<node_id>")
def api_node(node_id: str):
    graph = api_graph().get_json()
    nodes = graph["nodes"]
    edges = graph["edges"]
    node = next((item for item in nodes if item.get("id") == node_id), None)
    if node is None:
        return jsonify({"error": "node not found"}), 404
    return jsonify({"node": node, "edges": [edge for edge in edges if edge.get("source") == node_id or edge.get("target") == node_id]})


@app.route("/api/<path:api_path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def inference_api_proxy(api_path: str):
    """Forward authenticated graph-console API calls to the inference service."""
    base = os.environ.get("ARCHIPELAGO_INFERENCE_URL", "http://127.0.0.1:5151").rstrip("/")
    for suffix in ("/api/chat", "/api"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    target = f"{base}/api/{api_path}"
    principal = getattr(g, "archipelago_principal", None)
    headers = {}
    if principal is not None and principal.access_token:
        headers["Authorization"] = f"Bearer {principal.access_token}"
    content_type = request.headers.get("Content-Type")
    if content_type:
        headers["Content-Type"] = content_type
    try:
        if request.files:
            files = {
                key: (file.filename, file.stream, file.content_type)
                for key, file in request.files.items()
            }
            upstream = requests.request(
                request.method,
                target,
                params=request.args,
                data=request.form,
                files=files,
                headers={key: value for key, value in headers.items() if key != "Content-Type"},
                timeout=(10, 300),
                stream=True,
            )
        else:
            upstream = requests.request(
                request.method,
                target,
                params=request.args,
                data=request.get_data() or None,
                headers=headers,
                timeout=(10, 300),
                stream=True,
            )
    except requests.RequestException as exc:
        app.logger.warning("Inference API proxy failed for %s: %s", api_path, exc)
        return jsonify({"error": "inference service unavailable"}), 502

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() in {"content-type", "content-disposition", "cache-control"}
    }
    return Response(
        upstream.iter_content(chunk_size=64 * 1024),
        status=upstream.status_code,
        headers=response_headers,
        direct_passthrough=True,
    )


@app.route("/api/stats")
def api_stats():
    data = load_graph()
    visualization = data.get("visualization", {})
    nodes = visualization.get("nodes", data.get("nodes", []))
    edges = data.get("edges", [])
    return jsonify({
        "node_count": len(nodes),
        "edge_count": len(edges),
        "schema_version": data.get("schema", {}).get("version", "1.6"),
        "updated_at": data.get("updated_at"),
    })


@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/archipelago_graph.html")
def archipelago_graph():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/ui/assets/<path:filename>")
def media_assets(filename: str):
    safe = Path(filename)
    if ".." in safe.parts:
        return jsonify({"error": "not found"}), 404
    for root in _ASSET_ROOTS:
        if (root / filename).is_file():
            return send_from_directory(str(root), filename, conditional=True)
    return ("Not found", 404)


@app.route("/<path:filename>")
def static_files(filename: str):
    if filename.lower() in {"neon.html", "neon"}:
        return "Not Found", 404
    return send_from_directory(str(STATIC_DIR), filename)


if __name__ == "__main__":
    port = int(os.environ.get("ARCHIPELAGO_GRAPH_PORT", os.environ.get("PORT", "5150")))
    app.run(host=os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=port, debug=False)
