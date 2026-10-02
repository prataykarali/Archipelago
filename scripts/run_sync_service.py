"""Entrypoint: periodically report graph size to the hosted inference API.

The library computer owns the corpus; the hosted API needs only its version and
shape so it can report honest readiness numbers. This sends counts, never
content.

Fails soft: a sync error is logged and retried on the next tick, because a
hosted-API outage must never stall local ingestion.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("archipelago.sync")

DEFAULT_INTERVAL_SEC = 300
DEFAULT_TIMEOUT_SEC = 15
GRAPH_JSON = Path(os.environ.get("ARCHIPELAGO_GRAPH_JSON", "okf_graph.json"))


def configure_logging() -> None:
    """Root logging plus credential redaction (the URL may carry a token)."""
    from archipelago.middleware.log_redaction import install_log_redaction

    logging.basicConfig(
        level=os.environ.get("ARCHIPELAGO_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    install_log_redaction()


def graph_stats(graph_path: Path = GRAPH_JSON) -> dict[str, Any]:
    """Node/edge/document counts read from the export.

    Missing or malformed stats yield zeros rather than an exception, so a
    mid-write export does not look like an emptied graph.
    """
    if not graph_path.is_file():
        return {"node_count": 0, "edge_count": 0, "document_count": 0}
    try:
        raw = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable graph export %s: %s", graph_path, exc)
        return {"node_count": 0, "edge_count": 0, "document_count": 0}

    stats = raw.get("stats") if isinstance(raw, dict) else {}
    stats = stats if isinstance(stats, dict) else {}
    visualization = raw.get("visualization") if isinstance(raw, dict) else {}
    nodes = visualization.get("nodes") if isinstance(visualization, dict) else None
    edges = visualization.get("edges") if isinstance(visualization, dict) else None
    return {
        "node_count": stats.get("total_concepts", len(nodes or [])),
        "edge_count": stats.get("total_edges", len(edges or [])),
        "document_count": stats.get("total_documents", 0),
    }


def push_once(api_url: str, timeout: int = DEFAULT_TIMEOUT_SEC) -> dict[str, Any]:
    """POST the current graph stats to the hosted API. Never raises."""
    stats = graph_stats()
    if not api_url:
        return {"ok": False, "reason": "ARCHIPELAGO_INFERENCE_URL not set", "stats": stats}

    endpoint = api_url.rstrip("/") + "/api/graph/stats"
    payload = json.dumps(stats).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=payload, headers={"Content-Type": "application/json"}
    )
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme not in ("http", "https"):
        return {"ok": False, "reason": f"refusing scheme {parsed.scheme!r}", "stats": stats}

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "stats": stats}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("Sync push to %s failed: %s", endpoint, exc)
        return {"ok": False, "reason": str(exc), "stats": stats}


def main() -> int:
    """Tick forever, logging stats and pushing them when an API is configured."""
    configure_logging()
    api_url = os.environ.get("ARCHIPELAGO_INFERENCE_URL", "").strip()
    interval = int(os.environ.get("SYNC_INTERVAL_SEC", DEFAULT_INTERVAL_SEC))

    logger.info("Sync service started (interval=%ds, api=%s)", interval, api_url or "not set")
    while True:
        result = push_once(api_url)
        stats = result["stats"]
        logger.info(
            "Graph: %s nodes, %s edges, %s documents (pushed=%s)",
            stats["node_count"],
            stats["edge_count"],
            stats["document_count"],
            result["ok"],
        )
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
