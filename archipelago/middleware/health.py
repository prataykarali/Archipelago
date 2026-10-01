import os
import json
import time
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": time.time()})

@health_bp.route('/ready', methods=['GET'])
def ready():
    checks = {}
    status = "ready"
    
    # Check graph db
    db_path = os.environ.get("DB_PATH", "okf_graph.db")
    if os.path.exists(db_path) and os.access(db_path, os.R_OK):
        checks["graph_db"] = "ok"
    else:
        checks["graph_db"] = "missing_or_unreadable"
        status = "degraded"
        
    # Check json
    json_path = os.environ.get("JSON_PATH", "okf_graph.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                json.load(f)
            checks["graph_json"] = "ok"
        except Exception as e:
            checks["graph_json"] = "invalid"
            status = "degraded"
    else:
        checks["graph_json"] = "missing"
        status = "degraded"
        
    return jsonify({
        "status": status,
        "checks": checks,
        "timestamp": time.time()
    }), 200 if status == "ready" else 503
