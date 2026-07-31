"""
Archipelago Graph Server
Serves real-time OKF graph data from okf_graph.json via REST API and hosts the UI.
Runs on port 5150.
"""

import json
import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
from dotenv import load_dotenv

load_dotenv()  # reads .env locally; no-op on Northflank

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = REPO_ROOT / "okf_graph.json"
STATIC_DIR = BASE_DIR / "graph_ui"
# Multi-root /ui/assets — same as chat server so graph tabs get button PNGs
_ASSET_ROOTS = tuple(
    p for p in (
        REPO_ROOT / "buttons",
        REPO_ROOT / "ui" / "assets",
        BASE_DIR / "ui" / "assets",
    )
    if p.is_dir()
)

app = Flask(__name__, static_folder=str(STATIC_DIR))


# ── Optional shared-token auth ────────────────────────────────────────────────
@app.before_request
def check_token():
    """If ARCHIPELAGO_TOKEN is set, require a matching X-Archipelago-Token
    header on every request; when unset this is a no-op (pilot default)."""
    token = os.environ.get("ARCHIPELAGO_TOKEN")
    if not token:
        return None
    if request.headers.get("X-Archipelago-Token") != token:
        return jsonify({"error": "unauthorized"}), 401
    return None


# ── CORS Configuration ────────────────────────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Archipelago-Token")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ── Load data (live-reload every request in dev) ──────────────────────────────
def load_graph():
    """Read okf_graph.json fresh on every call — real-time, no cache."""
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


# ── API endpoints ─────────────────────────────────────────────────────────────
@app.route("/api/graph")
def api_graph():
    """Return graph nodes and browser-ready edges."""
    data = load_graph()
    vis = data.get("visualization", {})
    nodes = vis.get("nodes", data.get("nodes", []))
    raw_edges = vis.get("links") or vis.get("edges") or data.get("edges", [])
    edges = [
        {
            **edge,
            "source_ref": edge.get("source_ref") or edge.get("source", ""),
            "source": edge.get("from_id") or edge.get("source"),
            "target": edge.get("to_id") or edge.get("target"),
        }
        for edge in raw_edges
    ]
    return jsonify({"nodes": nodes, "edges": edges})


@app.route("/api/schema")
def api_schema():
    """Returns the OKF v1.6 schema spec as JSON for the UI info panel."""
    data = load_graph()
    return jsonify(data.get("schema", {"version": "1.6", "nodes": [], "edges": []}))


@app.route("/api/node/<node_id>")
def api_node(node_id):
    """Return one node and its browser-ready edges."""
    graph = api_graph().get_json()
    nodes = graph["nodes"]
    edges = graph["edges"]
    node = next((item for item in nodes if item.get("id") == node_id), None)
    if not node:
        return jsonify({"error": "node not found"}), 404
    node_edges = [
        edge for edge in edges if edge.get("source") == node_id or edge.get("target") == node_id
    ]
    return jsonify({"node": node, "edges": node_edges})


@app.route("/api/stats")
def api_stats():
    data = load_graph()
    nodes = data.get("visualization", {}).get("nodes", data.get("nodes", []))
    links = (data.get("visualization", {}).get("links") or 
             data.get("visualization", {}).get("edges") or 
             data.get("edges", []))
    return jsonify({
        "node_count": len(nodes),
        "edge_count": len(links),
        "schema_version": data.get("schema", {}).get("version", "1.6"),
        "updated_at": data.get("updated_at"),
    })


# ── Serve the UI ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/archipelago_graph.html")
def archipelago_graph():
    """Original graph URL kept alive, but served from the live data viewer."""
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/ui/assets/<path:filename>")
def media_assets(filename):
    """Serve button icons (and other media) under /ui/assets/* for the graph UI.

    Graph HTML references ``/ui/assets/graph_btn.png`` etc. Without this route
    the catch-all only looks in graph_ui/ and every icon 404s.
    """
    safe = Path(filename)
    if ".." in safe.parts:
        return jsonify({"error": "not found"}), 404
    for root in _ASSET_ROOTS:
        candidate = root / filename
        if candidate.is_file() or candidate.is_symlink():
            return send_from_directory(str(root), filename, conditional=True)
    fallback = _ASSET_ROOTS[0] if _ASSET_ROOTS else (REPO_ROOT / "buttons")
    return send_from_directory(str(fallback), filename, conditional=True)


@app.route("/<path:filename>")
def static_files(filename):
    if filename.lower() in ("neon.html", "neon"):
        return send_from_directory(str(STATIC_DIR), "index.html")
    return send_from_directory(str(STATIC_DIR), filename)


if __name__ == "__main__":
    STATIC_DIR.mkdir(exist_ok=True)
    port = int(os.environ.get("ARCHIPELAGO_GRAPH_PORT", "5150"))
    app.run(host=os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=port, debug=False)