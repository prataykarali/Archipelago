"""Container health/readiness probes (docs/01 §26).

``/health`` is liveness: the process is up.  ``/ready`` is readiness: the
process plus every required dependency can actually serve traffic.  Kubernetes
and AntDeploy use these to decide whether to route requests.
"""
from __future__ import annotations

import logging
import os
import time

import kuzu
from flask import jsonify

from archipelago.inference import state as st
from archipelago.inference.graph_lock import graph_lock

logger = logging.getLogger("archipelago.inference.health")

STARTED_AT = time.time()
SERVICE_NAME = os.environ.get("ARCHIPELAGO_SERVICE_NAME", "archipelago-inference")


def _graph_status() -> dict:
    """Report graph reachability and concept count without claiming more."""
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            res = conn.execute("MATCH (c:Concept) RETURN count(c)")
            count = res.get_next()[0] if res.has_next() else 0
        return {"ready": True, "concept_count": int(count), "error": None}
    except Exception as exc:  # noqa: BLE001 - surfaced in the probe payload
        return {"ready": False, "concept_count": 0, "error": str(exc)}


def _inference_configured() -> bool:
    """True when an inference credential is present (never probes the network)."""
    return bool(os.environ.get("XKIRO_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip())


@st.app.route("/health", methods=["GET"])
def health():
    """Liveness probe: the process is running. Never touches a dependency."""
    return jsonify({
        "status": "alive",
        "service": SERVICE_NAME,
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
    }), 200


@st.app.route("/ready", methods=["GET"])
def ready():
    """Readiness probe: graph + concept index + inference config are usable."""
    graph = _graph_status()
    concepts_loaded = bool(st.CONCEPTS_DATA)
    checks = {
        "graph": graph["ready"],
        "concepts": concepts_loaded,
        "inference_configured": _inference_configured(),
    }
    is_ready = graph["ready"] and concepts_loaded
    return jsonify({
        "status": "ready" if is_ready else "not_ready",
        "ready": is_ready,
        "service": SERVICE_NAME,
        "checks": checks,
        "graph": graph,
        "concept_count": len(st.CONCEPTS_DATA),
    }), 200 if is_ready else 503


@st.app.route("/api/health", methods=["GET"])
def api_health():
    """Liveness alias under the /api prefix, matching the bootstrap allow-list."""
    return health()